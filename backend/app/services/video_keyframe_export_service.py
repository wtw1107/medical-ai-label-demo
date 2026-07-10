from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.converters.label_studio_parser import parse_keyframe_annotation_task
from app.converters.mask_converter import write_mask_png
from app.core.config import Settings
from app.core.constants import BLineGrade, VideoAnnotationStatus, VideoQuality
from app.db.models import Dataset, KeyFrame, VideoItem, VideoReview
from app.services.label_studio_service import LabelStudioService


@dataclass
class ExportedKeyframeRecord:
    dataset_id: str
    video_id: str
    patient_uid: str | None
    lung_zone: str | None
    filename: str
    frame_index: int
    timestamp_ms: int
    image_rel_path: str
    mask_rel_path: str
    quality: str
    bline_grade: str
    uncertain_flag: bool
    include_in_training: bool
    review_comment: str | None
    annotation_status: str
    label_studio_task_id: int | None


class VideoKeyframeExportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.label_studio_service = LabelStudioService(settings)

    def export_dataset(self, *, db: Session, dataset_id: str) -> dict[str, object]:
        dataset = db.get(Dataset, dataset_id)
        if dataset is None or dataset.data_type != "video":
            raise HTTPException(status_code=404, detail=f"Video dataset not found: {dataset_id}")

        videos = (
            db.query(VideoItem)
            .filter(VideoItem.dataset_id == dataset.id)
            .order_by(VideoItem.created_at.asc())
            .all()
        )
        if not videos:
            raise HTTPException(status_code=400, detail="Video dataset contains no videos.")

        export_id = uuid4().hex
        export_root = self.settings.ensure_data_root() / "exports" / "video_bline" / export_id
        bundle_root = export_root / "bline_keyframe_export"
        images_dir = bundle_root / "images"
        masks_dir = bundle_root / "masks"
        images_dir.mkdir(parents=True, exist_ok=True)
        masks_dir.mkdir(parents=True, exist_ok=True)

        remote_lookups: dict[int, dict[int, dict[str, object]]] = {}
        manifest: list[ExportedKeyframeRecord] = []
        skipped: list[dict[str, object]] = []

        for video in videos:
            latest_review = self._get_latest_review(video.reviews)
            keyframes = (
                db.query(KeyFrame)
                .filter(KeyFrame.video_id == video.id)
                .order_by(KeyFrame.frame_index.asc())
                .all()
            )
            for keyframe in keyframes:
                if keyframe.label_studio_project_id is None or keyframe.label_studio_task_id is None:
                    keyframe.annotation_status = VideoAnnotationStatus.PENDING.value
                    skipped.append(self._build_skipped_record(video=video, keyframe=keyframe, reason="label_studio_task_not_initialized"))
                    continue

                project_lookup = remote_lookups.get(keyframe.label_studio_project_id)
                if project_lookup is None:
                    project_lookup = self.label_studio_service.get_project_task_lookup(keyframe.label_studio_project_id)
                    remote_lookups[keyframe.label_studio_project_id] = project_lookup

                remote_task = project_lookup.get(keyframe.label_studio_task_id)
                if remote_task is None:
                    keyframe.annotation_status = VideoAnnotationStatus.PENDING.value
                    skipped.append(self._build_skipped_record(video=video, keyframe=keyframe, reason="label_studio_task_not_found"))
                    continue

                width = self._resolve_keyframe_width(video)
                height = self._resolve_keyframe_height(video)
                if width is None or height is None:
                    raise HTTPException(status_code=400, detail=f"Keyframe dimensions are missing for video {video.id}.")

                parsed = parse_keyframe_annotation_task(
                    remote_task=remote_task,
                    keyframe_id=keyframe.id,
                    filename=Path(keyframe.image_path).name,
                    width=width,
                    height=height,
                )
                if parsed is None:
                    keyframe.annotation_status = VideoAnnotationStatus.PENDING.value
                    skipped.append(self._build_skipped_record(video=video, keyframe=keyframe, reason="unlabeled"))
                    continue

                image_name = f"{video.id}_{keyframe.frame_index}.png"
                mask_name = f"{video.id}_{keyframe.frame_index}_mask.png"
                image_rel_path = str(Path("images") / image_name).replace("\\", "/")
                mask_rel_path = str(Path("masks") / mask_name).replace("\\", "/")

                Image.open(keyframe.image_path).save(images_dir / image_name, format="PNG")
                write_mask_png(parsed, masks_dir / mask_name, fill_value=1)

                keyframe.annotation_status = VideoAnnotationStatus.ANNOTATED.value
                manifest.append(
                    ExportedKeyframeRecord(
                        dataset_id=dataset.id,
                        video_id=video.id,
                        patient_uid=video.patient.patient_uid if video.patient is not None else None,
                        lung_zone=video.lung_zone,
                        filename=video.filename,
                        frame_index=keyframe.frame_index,
                        timestamp_ms=keyframe.timestamp_ms,
                        image_rel_path=image_rel_path,
                        mask_rel_path=mask_rel_path,
                        quality=latest_review.quality if latest_review is not None else VideoQuality.UNKNOWN.value,
                        bline_grade=latest_review.bline_grade if latest_review is not None else BLineGrade.UNKNOWN.value,
                        uncertain_flag=latest_review.uncertain_flag if latest_review is not None else False,
                        include_in_training=latest_review.include_in_training if latest_review is not None else True,
                        review_comment=latest_review.comment if latest_review is not None else None,
                        annotation_status=keyframe.annotation_status,
                        label_studio_task_id=keyframe.label_studio_task_id,
                    )
                )

        if not manifest:
            raise HTTPException(
                status_code=400,
                detail="No labeled keyframes were found. Export only includes keyframes with saved B-line annotations.",
            )

        self._write_manifest_files(bundle_root=bundle_root, manifest=manifest)
        self._write_skipped_file(bundle_root=bundle_root, skipped=skipped)
        self._write_readme(bundle_root=bundle_root)

        zip_path = export_root / f"{export_id}.zip"
        self._build_zip(export_root=export_root, bundle_root=bundle_root, zip_path=zip_path)
        db.commit()

        api_base = self.settings.media_base_url.rsplit("/media", 1)[0]
        return {
            "export_id": export_id,
            "dataset_id": dataset.id,
            "total_labeled_count": len(manifest),
            "skipped_count": len(skipped),
            "file_path": str(zip_path),
            "download_url": f"{api_base}/api/video-exports/{export_id}/download",
        }

    def get_download_path(self, export_id: str) -> Path:
        export_root = self.settings.ensure_data_root() / "exports" / "video_bline" / export_id
        zip_path = export_root / f"{export_id}.zip"
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="Video export file is not ready.")
        return zip_path

    def _get_latest_review(self, reviews: list[VideoReview]) -> VideoReview | None:
        if not reviews:
            return None
        return max(reviews, key=lambda item: item.created_at)

    def _resolve_keyframe_width(self, video: VideoItem) -> int | None:
        return video.width

    def _resolve_keyframe_height(self, video: VideoItem) -> int | None:
        return video.height

    def _build_skipped_record(self, *, video: VideoItem, keyframe: KeyFrame, reason: str) -> dict[str, object]:
        return {
            "video_id": video.id,
            "frame_index": keyframe.frame_index,
            "timestamp_ms": keyframe.timestamp_ms,
            "annotation_status": keyframe.annotation_status,
            "label_studio_task_id": keyframe.label_studio_task_id,
            "reason": reason,
        }

    def _write_manifest_files(self, *, bundle_root: Path, manifest: list[ExportedKeyframeRecord]) -> None:
        manifest_json = bundle_root / "manifest.json"
        manifest_csv = bundle_root / "manifest.csv"

        json_payload = [
            {
                "dataset_id": item.dataset_id,
                "video_id": item.video_id,
                "patient_uid": item.patient_uid,
                "lung_zone": item.lung_zone,
                "filename": item.filename,
                "frame_index": item.frame_index,
                "timestamp_ms": item.timestamp_ms,
                "image_path": item.image_rel_path,
                "mask_path": item.mask_rel_path,
                "quality": item.quality,
                "bline_grade": item.bline_grade,
                "uncertain_flag": item.uncertain_flag,
                "include_in_training": item.include_in_training,
                "review_comment": item.review_comment,
                "annotation_status": item.annotation_status,
                "label_studio_task_id": item.label_studio_task_id,
            }
            for item in manifest
        ]
        manifest_json.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with manifest_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "dataset_id",
                    "video_id",
                    "patient_uid",
                    "lung_zone",
                    "filename",
                    "frame_index",
                    "timestamp_ms",
                    "image_path",
                    "mask_path",
                    "quality",
                    "bline_grade",
                    "uncertain_flag",
                    "include_in_training",
                    "review_comment",
                    "annotation_status",
                    "label_studio_task_id",
                ],
            )
            writer.writeheader()
            for item in json_payload:
                writer.writerow(item)

    def _write_skipped_file(self, *, bundle_root: Path, skipped: list[dict[str, object]]) -> None:
        skipped_path = bundle_root / "skipped.json"
        skipped_path.write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_readme(self, *, bundle_root: Path) -> None:
        readme = bundle_root / "README.txt"
        readme.write_text(
            "\n".join(
                [
                    "B-line keyframe export",
                    "",
                    "- images/ contains exported keyframe PNG images.",
                    "- masks/ contains binary PNG masks with pixel values 0 or 1.",
                    "- manifest.json and manifest.csv include keyframe metadata.",
                    "- skipped.json lists keyframes that were not exported because they were unlabeled or missing Label Studio tasks.",
                    "- This export does not modify the existing image-task mask export behavior (0/255).",
                ]
            ),
            encoding="utf-8",
        )

    def _build_zip(self, *, export_root: Path, bundle_root: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in bundle_root.rglob("*"):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(export_root))
