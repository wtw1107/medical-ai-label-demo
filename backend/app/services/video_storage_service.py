from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import (
    BLineGrade,
    DataType,
    DatasetSplit,
    DatasetStatus,
    DeidentificationStatus,
    VideoQuality,
    VideoItemStatus,
)
from app.db.models import Dataset, Patient, VideoItem
from app.db.session import engine
from app.schemas.video import (
    PatientRead,
    VideoDatasetUploadResponse,
    VideoItemRead,
    VideoUploadMetadata,
    VideoUploadWarning,
)
from app.utils.file_utils import build_unique_filename, normalize_filename, safe_join


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def ensure_video_schema() -> None:
    with engine.begin() as connection:
        if connection.dialect.name != "sqlite":
            return
        dataset_columns = connection.execute(text("PRAGMA table_info(datasets)")).mappings().all()
        dataset_column_names = {column["name"] for column in dataset_columns}
        if dataset_columns:
            if "annotation_backend" not in dataset_column_names:
                connection.execute(text("ALTER TABLE datasets ADD COLUMN annotation_backend VARCHAR(32)"))
            if "cvat_project_id" not in dataset_column_names:
                connection.execute(text("ALTER TABLE datasets ADD COLUMN cvat_project_id INTEGER"))
            if "cvat_project_url" not in dataset_column_names:
                connection.execute(text("ALTER TABLE datasets ADD COLUMN cvat_project_url VARCHAR(512)"))

        video_columns = connection.execute(text("PRAGMA table_info(video_items)")).mappings().all()
        video_column_names = {column["name"] for column in video_columns}
        if video_columns:
            if "cvat_task_id" not in video_column_names:
                connection.execute(text("ALTER TABLE video_items ADD COLUMN cvat_task_id INTEGER"))
            if "cvat_job_id" not in video_column_names:
                connection.execute(text("ALTER TABLE video_items ADD COLUMN cvat_job_id INTEGER"))
            if "cvat_task_url" not in video_column_names:
                connection.execute(text("ALTER TABLE video_items ADD COLUMN cvat_task_url VARCHAR(512)"))
            if "cvat_job_url" not in video_column_names:
                connection.execute(text("ALTER TABLE video_items ADD COLUMN cvat_job_url VARCHAR(512)"))
            if "cvat_status" not in video_column_names:
                connection.execute(text("ALTER TABLE video_items ADD COLUMN cvat_status VARCHAR(64)"))
            if "cvat_annotation_updated_at" not in video_column_names:
                connection.execute(text("ALTER TABLE video_items ADD COLUMN cvat_annotation_updated_at DATETIME"))

        columns = connection.execute(text("PRAGMA table_info(key_frames)")).mappings().all()
        if not columns:
            return
        column_names = {column["name"] for column in columns}
        if "label_studio_project_id" not in column_names:
            connection.execute(text("ALTER TABLE key_frames ADD COLUMN label_studio_project_id INTEGER"))
        if "label_studio_task_id" not in column_names:
            connection.execute(text("ALTER TABLE key_frames ADD COLUMN label_studio_task_id INTEGER"))
        if "label_studio_task_url" not in column_names:
            connection.execute(text("ALTER TABLE key_frames ADD COLUMN label_studio_task_url VARCHAR(512)"))
        if "annotation_updated_at" not in column_names:
            connection.execute(text("ALTER TABLE key_frames ADD COLUMN annotation_updated_at DATETIME"))


@dataclass
class StoredVideo:
    filename: str
    file_path: str
    file_url: str
    preview_image_path: str | None
    preview_image_url: str | None
    duration_sec: float
    fps: float
    frame_count: int
    width: int
    height: int


def _get_video_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def is_allowed_video_file(filename: str) -> bool:
    return _get_video_extension(filename) in ALLOWED_VIDEO_EXTENSIONS


def _save_bytes_to_path(content: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def _build_media_url(*, media_base_url: str, relative_url: str) -> str:
    if media_base_url:
        return f"{media_base_url.rstrip('/')}{relative_url}"
    return f"/media{relative_url}"


def _load_opencv():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Video parsing requires OpenCV. Install backend dependencies with "
                "`pip install -r backend/requirements.txt`."
            ),
        ) from exc
    return cv2


def _parse_video_metadata(video_path: Path) -> tuple[float, int, int, int, int, object]:
    cv2 = _load_opencv()
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise HTTPException(status_code=400, detail=f"Failed to open video file: {video_path.name}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration_sec = float(frame_count / fps) if fps > 0 and frame_count > 0 else 0.0

    if frame_count <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise HTTPException(status_code=400, detail=f"Video metadata is invalid for file: {video_path.name}")

    return fps, frame_count, width, height, duration_sec, capture


def _write_preview_image(capture: object, preview_path: Path) -> None:
    cv2 = _load_opencv()
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise HTTPException(status_code=400, detail="Failed to extract first-frame preview from video.")
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    Image.fromarray(frame_rgb).save(preview_path, format="JPEG", quality=90)


def _store_video_bytes(
    *,
    video_bytes: bytes,
    original_filename: str,
    dataset_id: str,
    videos_dir: Path,
    media_base_url: str,
    preview_dir: Path,
) -> StoredVideo:
    suffix = _get_video_extension(original_filename) or ".mp4"
    saved_filename = f"{uuid4().hex[:8]}_{build_unique_filename(original_filename, suffix)}"
    video_path = safe_join(videos_dir, saved_filename)
    preview_filename = f"{Path(saved_filename).stem}.preview.jpg"
    preview_path = safe_join(preview_dir, preview_filename)

    try:
        _save_bytes_to_path(video_bytes, video_path)
        fps, frame_count, width, height, duration_sec, capture = _parse_video_metadata(video_path)
        _write_preview_image(capture, preview_path)
    except Exception:
        video_path.unlink(missing_ok=True)
        preview_path.unlink(missing_ok=True)
        raise

    relative_video_url = f"/video_datasets/{dataset_id}/videos/{saved_filename}"
    relative_preview_url = f"/video_datasets/{dataset_id}/previews/{preview_filename}"
    return StoredVideo(
        filename=normalize_filename(original_filename),
        file_path=str(video_path),
        file_url=_build_media_url(media_base_url=media_base_url, relative_url=relative_video_url),
        preview_image_path=str(preview_path),
        preview_image_url=_build_media_url(media_base_url=media_base_url, relative_url=relative_preview_url),
        duration_sec=round(duration_sec, 4),
        fps=round(fps, 4),
        frame_count=frame_count,
        width=width,
        height=height,
    )


def _serialize_video_item(video: VideoItem) -> VideoItemRead:
    latest_review = None
    if video.reviews:
        latest_review = max(video.reviews, key=lambda item: item.created_at)
    return VideoItemRead(
        id=video.id,
        dataset_id=video.dataset_id,
        patient_id=video.patient_id,
        patient_uid=video.patient.patient_uid if video.patient is not None else None,
        filename=video.filename,
        file_path=video.file_path,
        file_url=video.file_url,
        duration_sec=video.duration_sec,
        fps=video.fps,
        frame_count=video.frame_count,
        width=video.width,
        height=video.height,
        preview_image_path=video.preview_image_path,
        preview_image_url=video.preview_image_url,
        lung_zone=video.lung_zone,
        probe=video.probe,
        orientation=video.orientation,
        device=video.device,
        depth=video.depth,
        deid_status=video.deid_status,
        status=video.status,
        error_message=video.error_message,
        quality=latest_review.quality if latest_review is not None else VideoQuality.UNKNOWN.value,
        bline_grade=latest_review.bline_grade if latest_review is not None else BLineGrade.UNKNOWN.value,
        uncertain_flag=latest_review.uncertain_flag if latest_review is not None else False,
        include_in_training=latest_review.include_in_training if latest_review is not None else True,
        review_comment=latest_review.comment if latest_review is not None else None,
        reviewed_by=latest_review.reviewed_by if latest_review is not None else None,
        reviewed_at=latest_review.reviewed_at if latest_review is not None else None,
        keyframe_count=len(video.keyframes),
        cvat_task_id=video.cvat_task_id,
        cvat_job_id=video.cvat_job_id,
        cvat_task_url=video.cvat_task_url,
        cvat_job_url=video.cvat_job_url,
        cvat_status=video.cvat_status,
        cvat_annotation_updated_at=video.cvat_annotation_updated_at,
        created_at=video.created_at,
        updated_at=video.updated_at,
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _build_legacy_metadata(
    *,
    files: list[UploadFile],
    patient_uid: str | None,
    lung_zone: str | None,
    probe: str | None,
    device: str | None,
    depth: str | None,
    orientation: str | None,
    deid_status: str | None,
    site: str | None,
    device_group: str | None,
) -> list[VideoUploadMetadata]:
    if not patient_uid or not patient_uid.strip():
        raise HTTPException(status_code=400, detail="patient_uid is required.")
    return [
        VideoUploadMetadata(
            filename=normalize_filename(upload_file.filename or "upload"),
            patient_uid=patient_uid.strip(),
            lung_zone=(lung_zone or "").strip(),
            probe=_clean_optional(probe),
            device=_clean_optional(device),
            depth=_clean_optional(depth),
            orientation=_clean_optional(orientation),
            deid_status=(deid_status or DeidentificationStatus.UNKNOWN.value).strip(),
            site=_clean_optional(site),
            device_group=_clean_optional(device_group),
        )
        for upload_file in files
    ]


def _build_metadata_lookup(metadata_items: list[VideoUploadMetadata]) -> dict[str, VideoUploadMetadata]:
    lookup: dict[str, VideoUploadMetadata] = {}
    duplicate_filenames: set[str] = set()
    for item in metadata_items:
        filename = normalize_filename(item.filename)
        if filename in lookup:
            duplicate_filenames.add(filename)
        lookup[filename] = item
    if duplicate_filenames:
        raise HTTPException(
            status_code=400,
            detail=f"Duplicate metadata filenames are not supported: {', '.join(sorted(duplicate_filenames))}",
        )
    return lookup


class VideoStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def upload_video_dataset(
        self,
        *,
        db: Session,
        dataset_name: str,
        files: list[UploadFile],
        patient_uid: str | None = None,
        video_metadata: list[VideoUploadMetadata] | None = None,
        annotation_backend: str | None = None,
        lung_zone: str | None = None,
        probe: str | None = None,
        device: str | None = None,
        depth: str | None = None,
        orientation: str | None = None,
        deid_status: str | None = None,
        site: str | None = None,
        device_group: str | None = None,
    ) -> VideoDatasetUploadResponse:
        if not files:
            raise HTTPException(status_code=400, detail="At least one video file is required.")
        normalized_backend = (annotation_backend or "native").strip()
        if normalized_backend not in {"native", "cvat", "label_studio"}:
            raise HTTPException(status_code=400, detail="annotation_backend must be native, cvat, or label_studio.")
        metadata_items = video_metadata or _build_legacy_metadata(
            files=files,
            patient_uid=patient_uid,
            lung_zone=lung_zone,
            probe=probe,
            device=device,
            depth=depth,
            orientation=orientation,
            deid_status=deid_status,
            site=site,
            device_group=device_group,
        )
        metadata_lookup = _build_metadata_lookup(metadata_items)

        dataset = Dataset(
            id=uuid4().hex,
            name=dataset_name.strip(),
            description="video_bline_segmentation dataset",
            data_type=DataType.VIDEO.value,
            image_count=0,
            root_dir="",
            status=DatasetStatus.UPLOADED.value,
            created_by=self.settings.default_user_id,
            annotation_backend=normalized_backend,
        )

        dataset_root = self.settings.ensure_data_root() / "video_datasets" / dataset.id
        videos_dir = dataset_root / "videos"
        preview_dir = dataset_root / "previews"
        videos_dir.mkdir(parents=True, exist_ok=True)
        preview_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[VideoUploadWarning] = []
        stored_videos: list[StoredVideo] = []

        for upload_file in files:
            filename = normalize_filename(upload_file.filename or "upload")
            if not is_allowed_video_file(filename):
                warnings.append(
                    VideoUploadWarning(filename=filename, message="Skipped unsupported video file.")
                )
                continue
            metadata = metadata_lookup.get(filename)
            if metadata is None:
                raise HTTPException(status_code=400, detail=f"Missing metadata for video file: {filename}")
            if not metadata.patient_uid.strip():
                raise HTTPException(status_code=400, detail=f"patient_uid is required for video file: {filename}")
            if not metadata.lung_zone.strip():
                raise HTTPException(status_code=400, detail=f"lung_zone is required for video file: {filename}")

            try:
                stored_videos.append(
                    _store_video_bytes(
                        video_bytes=upload_file.file.read(),
                        original_filename=filename,
                        dataset_id=dataset.id,
                        videos_dir=videos_dir,
                        media_base_url=self.settings.media_base_url,
                        preview_dir=preview_dir,
                    )
                )
            except HTTPException:
                self._cleanup_empty_dataset_dir(dataset_root)
                raise
            except Exception as exc:
                warnings.append(VideoUploadWarning(filename=filename, message=str(exc)))

        if not stored_videos:
            self._cleanup_empty_dataset_dir(dataset_root)
            raise HTTPException(status_code=400, detail="No valid video files were found in the upload.")

        try:
            dataset.root_dir = str(dataset_root.resolve())
            dataset.status = DatasetStatus.READY.value
            db.add(dataset)
            db.flush()

            patients_by_uid: dict[str, Patient] = {}
            for metadata in metadata_items:
                patient_key = metadata.patient_uid.strip()
                if patient_key in patients_by_uid:
                    continue
                patient = Patient(
                    dataset_id=dataset.id,
                    patient_uid=patient_key,
                    split=DatasetSplit.UNASSIGNED.value,
                    site=_clean_optional(metadata.site),
                    device_group=_clean_optional(metadata.device_group),
                )
                db.add(patient)
                patients_by_uid[patient_key] = patient
            db.flush()

            video_items: list[VideoItem] = []
            for stored_video in stored_videos:
                metadata = metadata_lookup[stored_video.filename]
                patient = patients_by_uid[metadata.patient_uid.strip()]
                video_item = VideoItem(
                    dataset_id=dataset.id,
                    patient_id=patient.id,
                    filename=stored_video.filename,
                    file_path=stored_video.file_path,
                    file_url=stored_video.file_url,
                    duration_sec=stored_video.duration_sec,
                    fps=stored_video.fps,
                    frame_count=stored_video.frame_count,
                    width=stored_video.width,
                    height=stored_video.height,
                    preview_image_path=stored_video.preview_image_path,
                    preview_image_url=stored_video.preview_image_url,
                    lung_zone=metadata.lung_zone.strip(),
                    probe=_clean_optional(metadata.probe),
                    orientation=_clean_optional(metadata.orientation),
                    device=_clean_optional(metadata.device),
                    depth=_clean_optional(metadata.depth),
                    deid_status=(metadata.deid_status or DeidentificationStatus.UNKNOWN.value).strip(),
                    status=VideoItemStatus.READY.value,
                    cvat_status="not_initialized",
                )
                db.add(video_item)
                video_items.append(video_item)

            db.commit()
            for video_item in video_items:
                db.refresh(video_item)
        except Exception as exc:
            db.rollback()
            self._cleanup_empty_dataset_dir(dataset_root)
            raise HTTPException(status_code=500, detail=f"Failed to persist video dataset records: {exc}") from exc

        return VideoDatasetUploadResponse(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            video_count=len(video_items),
            patient_count=len(patients_by_uid),
            videos=[_serialize_video_item(video) for video in video_items],
            warnings=warnings,
        )

    def get_dataset_summary(self, *, db: Session, dataset_id: str):
        dataset = db.get(Dataset, dataset_id)
        if dataset is None or dataset.data_type != DataType.VIDEO.value:
            raise HTTPException(status_code=404, detail=f"Video dataset not found: {dataset_id}")
        return dataset

    def list_dataset_videos(self, *, db: Session, dataset_id: str) -> list[VideoItem]:
        dataset = self.get_dataset_summary(db=db, dataset_id=dataset_id)
        videos = (
            db.query(VideoItem)
            .filter(VideoItem.dataset_id == dataset.id)
            .order_by(VideoItem.created_at.asc())
            .all()
        )
        return videos

    def serialize_video_item(self, video: VideoItem) -> VideoItemRead:
        return _serialize_video_item(video)

    def serialize_patient(self, patient: Patient) -> PatientRead:
        return PatientRead.model_validate(patient)

    def _cleanup_empty_dataset_dir(self, dataset_root: Path) -> None:
        for child in sorted(dataset_root.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink(missing_ok=True)
            else:
                try:
                    child.rmdir()
                except OSError:
                    pass
        try:
            dataset_root.rmdir()
        except OSError:
            pass
