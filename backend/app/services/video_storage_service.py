from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import (
    DataType,
    DatasetSplit,
    DatasetStatus,
    DeidentificationStatus,
    VideoItemStatus,
)
from app.db.models import Dataset, Patient, VideoItem
from app.schemas.video import (
    PatientRead,
    VideoDatasetUploadResponse,
    VideoItemRead,
    VideoUploadWarning,
)
from app.utils.file_utils import build_unique_filename, normalize_filename, safe_join


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


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
        created_at=video.created_at,
        updated_at=video.updated_at,
    )


class VideoStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def upload_video_dataset(
        self,
        *,
        db: Session,
        dataset_name: str,
        patient_uid: str,
        files: list[UploadFile],
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
        if not patient_uid.strip():
            raise HTTPException(status_code=400, detail="patient_uid is required.")

        dataset = Dataset(
            id=uuid4().hex,
            name=dataset_name.strip(),
            description="video_bline_segmentation dataset",
            data_type=DataType.VIDEO.value,
            image_count=0,
            root_dir="",
            status=DatasetStatus.UPLOADED.value,
            created_by=self.settings.default_user_id,
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

        patient = Patient(
            dataset_id=dataset.id,
            patient_uid=patient_uid.strip(),
            split=DatasetSplit.UNASSIGNED.value,
            site=site.strip() if site else None,
            device_group=device_group.strip() if device_group else None,
        )

        try:
            dataset.root_dir = str(dataset_root.resolve())
            dataset.status = DatasetStatus.READY.value
            db.add(dataset)
            db.flush()

            patient.dataset_id = dataset.id
            db.add(patient)
            db.flush()

            video_items: list[VideoItem] = []
            normalized_deid_status = (
                deid_status.strip() if deid_status else DeidentificationStatus.UNKNOWN.value
            )
            for stored_video in stored_videos:
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
                    lung_zone=lung_zone.strip() if lung_zone else None,
                    probe=probe.strip() if probe else None,
                    orientation=orientation.strip() if orientation else None,
                    device=device.strip() if device else None,
                    depth=depth.strip() if depth else None,
                    deid_status=normalized_deid_status,
                    status=VideoItemStatus.READY.value,
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
            patient_count=1,
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
