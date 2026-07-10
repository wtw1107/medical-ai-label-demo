from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.converters.label_studio_parser import extract_latest_saved_annotation
from app.core.config import Settings
from app.core.constants import (
    KeyFrameReviewStatus,
    LabelStudioFieldName,
    TaskType,
    VideoAnnotationStatus,
)
from app.db.models import KeyFrame, VideoItem
from app.schemas.video import (
    KeyFrameLabelStudioInitResponse,
    KeyFrameLabelStudioSyncResponse,
    KeyFrameRead,
    ReviewStatusSummaryItem,
)
from app.services.keyframe_service import KeyFrameService
from app.services.label_studio_service import LabelStudioService


class VideoKeyframeLabelStudioService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.label_studio_service = LabelStudioService(settings)
        self.keyframe_service = KeyFrameService(settings)

    def init_keyframe_tasks(
        self,
        *,
        db: Session,
        video_id: str,
        keyframe_ids: list[str],
        project_title: str | None,
    ) -> KeyFrameLabelStudioInitResponse:
        video = self._get_video(db=db, video_id=video_id)
        keyframes = self._get_keyframes_for_video(db=db, video=video, keyframe_ids=keyframe_ids)
        if not keyframes:
            raise HTTPException(status_code=400, detail="No keyframes available for Label Studio initialization.")

        existing_project_id = next((item.label_studio_project_id for item in keyframes if item.label_studio_project_id), None)
        if existing_project_id is not None:
            for keyframe in keyframes:
                if keyframe.label_studio_project_id not in {None, existing_project_id}:
                    raise HTTPException(status_code=400, detail="Selected keyframes belong to different Label Studio projects.")

        if existing_project_id is None:
            project = self.label_studio_service.create_project(
                title=project_title.strip() if project_title and project_title.strip() else self._default_project_title(video),
                description=f"Video dataset: {video.dataset.name} / video: {video.filename}",
                task_type=TaskType.VIDEO_BLINE_SEGMENTATION.value,
            )
            project_id = project.project_id
            project_url = project.project_url
        else:
            project_id = existing_project_id
            project_url = self.label_studio_service._project_url(existing_project_id)

        pending_keyframes = [item for item in keyframes if item.label_studio_task_id is None]
        reused_count = len(keyframes) - len(pending_keyframes)

        if pending_keyframes:
            tasks = [self._build_task_payload(video=video, keyframe=item) for item in pending_keyframes]
            self.label_studio_service.import_tasks(project_id=project_id, tasks=tasks)

        self._sync_project_task_mappings(db=db, project_id=project_id, project_url=project_url, keyframes=keyframes)
        synced_keyframes = self._sync_status_in_memory(project_url=project_url, keyframes=keyframes)
        db.commit()
        for keyframe in synced_keyframes:
            db.refresh(keyframe)

        return KeyFrameLabelStudioInitResponse(
            video_id=video.id,
            label_studio_project_id=project_id,
            label_studio_project_url=project_url,
            initialized_count=len(pending_keyframes),
            reused_count=reused_count,
            keyframes=[self._serialize(item) for item in synced_keyframes],
        )

    def sync_keyframe_status(self, *, db: Session, video_id: str) -> KeyFrameLabelStudioSyncResponse:
        video = self._get_video(db=db, video_id=video_id)
        keyframes = self._get_keyframes_for_video(db=db, video=video, keyframe_ids=[])
        grouped: dict[int, list[KeyFrame]] = defaultdict(list)
        for keyframe in keyframes:
            if keyframe.label_studio_project_id is not None:
                grouped[keyframe.label_studio_project_id].append(keyframe)

        for project_id, project_keyframes in grouped.items():
            project_url = self.label_studio_service._project_url(project_id)
            self._sync_project_task_mappings(
                db=db,
                project_id=project_id,
                project_url=project_url,
                keyframes=project_keyframes,
            )
            self._sync_status_in_memory(project_url=project_url, keyframes=project_keyframes)

        db.commit()
        for keyframe in keyframes:
            db.refresh(keyframe)

        labeled_count = sum(1 for item in keyframes if item.annotation_status == VideoAnnotationStatus.ANNOTATED.value)
        review_counts: dict[str, int] = defaultdict(int)
        for keyframe in keyframes:
            review_counts[keyframe.review_status] += 1

        return KeyFrameLabelStudioSyncResponse(
            video_id=video.id,
            total_keyframes=len(keyframes),
            labeled_count=labeled_count,
            unlabeled_count=len(keyframes) - labeled_count,
            review_status_summary=[
                ReviewStatusSummaryItem(review_status=status, count=count)
                for status, count in sorted(review_counts.items())
            ],
            keyframes=[self._serialize(item) for item in keyframes],
        )

    def _get_video(self, *, db: Session, video_id: str) -> VideoItem:
        video = db.get(VideoItem, video_id)
        if video is None:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        return video

    def _get_keyframes_for_video(
        self,
        *,
        db: Session,
        video: VideoItem,
        keyframe_ids: list[str],
    ) -> list[KeyFrame]:
        query = db.query(KeyFrame).filter(KeyFrame.video_id == video.id)
        if keyframe_ids:
            query = query.filter(KeyFrame.id.in_(keyframe_ids))
        keyframes = query.order_by(KeyFrame.frame_index.asc()).all()
        if keyframe_ids and len(keyframes) != len(set(keyframe_ids)):
            raise HTTPException(status_code=404, detail="Some keyframe_ids were not found for the current video.")
        return keyframes

    def _default_project_title(self, video: VideoItem) -> str:
        return f"video-bline-{video.dataset.name}-{video.id[:8]}"

    def _build_task_payload(self, *, video: VideoItem, keyframe: KeyFrame) -> dict[str, object]:
        return {
            "data": {
                "image": keyframe.image_url,
            },
            "meta": {
                "keyframe_id": keyframe.id,
                "video_id": video.id,
                "dataset_id": video.dataset_id,
                "filename": video.filename,
                "frame_index": keyframe.frame_index,
                "timestamp_ms": keyframe.timestamp_ms,
                "patient_uid": video.patient.patient_uid if video.patient is not None else None,
                "lung_zone": video.lung_zone,
            },
        }

    def _sync_project_task_mappings(
        self,
        *,
        db: Session,
        project_id: int,
        project_url: str,
        keyframes: list[KeyFrame],
    ) -> None:
        keyframe_map = {item.id: item for item in keyframes}
        for remote_task in self.label_studio_service.list_project_tasks(project_id):
            remote_task_id = remote_task.get("id")
            meta = remote_task.get("meta", {})
            if not isinstance(remote_task_id, int) or not isinstance(meta, dict):
                continue
            keyframe_id = meta.get("keyframe_id")
            if not isinstance(keyframe_id, str):
                continue
            keyframe = keyframe_map.get(keyframe_id)
            if keyframe is None:
                continue
            keyframe.label_studio_project_id = project_id
            keyframe.label_studio_task_id = remote_task_id
            keyframe.label_studio_task_url = self.label_studio_service.build_task_url(project_url, remote_task_id)
            db.add(keyframe)

    def _sync_status_in_memory(self, *, project_url: str, keyframes: list[KeyFrame]) -> list[KeyFrame]:
        if not keyframes:
            return []
        project_id = keyframes[0].label_studio_project_id
        if project_id is None:
            return keyframes

        remote_lookup = self.label_studio_service.get_project_task_lookup(project_id)
        for keyframe in keyframes:
            keyframe.label_studio_task_url = self.label_studio_service.build_task_url(project_url, keyframe.label_studio_task_id)
            keyframe.annotation_status = VideoAnnotationStatus.PENDING.value
            keyframe.review_status = KeyFrameReviewStatus.UNREVIEWED.value
            keyframe.annotation_updated_at = None

            if keyframe.label_studio_task_id is None:
                continue
            remote_task = remote_lookup.get(keyframe.label_studio_task_id)
            if remote_task is None:
                continue
            annotation = extract_latest_saved_annotation(remote_task)
            if annotation is None:
                continue

            if self._has_bline_polygon(annotation):
                keyframe.annotation_status = VideoAnnotationStatus.ANNOTATED.value
            keyframe.review_status = self._extract_review_status(annotation) or keyframe.review_status
            keyframe.annotation_updated_at = self._extract_annotation_datetime(annotation)
        return keyframes

    def _has_bline_polygon(self, annotation: dict[str, object]) -> bool:
        results = annotation.get("result", [])
        if not isinstance(results, list):
            return False
        return any(
            isinstance(result, dict)
            and result.get("type") == "polygonlabels"
            and result.get("from_name") == LabelStudioFieldName.BLINE_POLYGON.value
            for result in results
        )

    def _extract_review_status(self, annotation: dict[str, object]) -> str | None:
        results = annotation.get("result", [])
        if not isinstance(results, list):
            return None
        for result in results:
            if not isinstance(result, dict):
                continue
            if result.get("from_name") != LabelStudioFieldName.REVIEW_STATUS.value:
                continue
            value = result.get("value", {})
            if not isinstance(value, dict):
                continue
            choices = value.get("choices", [])
            if isinstance(choices, list) and choices:
                choice = choices[0]
                if isinstance(choice, str) and choice:
                    return choice
        return None

    def _extract_annotation_datetime(self, annotation: dict[str, object]) -> datetime | None:
        for field in ("updated_at", "created_at"):
            raw_value = annotation.get(field)
            if not isinstance(raw_value, str) or not raw_value:
                continue
            normalized = raw_value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                continue
        return None

    def _serialize(self, keyframe: KeyFrame) -> KeyFrameRead:
        return self.keyframe_service.serialize_keyframe(keyframe)
