from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.constants import KeyFrameReason, KeyFrameReviewStatus, VideoAnnotationStatus
from app.db.models import KeyFrame, VideoItem
from app.schemas.video import KeyFrameExtractResponse, KeyFrameRead
from app.utils.file_utils import safe_join


def _load_opencv():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Keyframe extraction requires OpenCV. Install backend dependencies with "
                "`pip install -r backend/requirements.txt`."
            ),
        ) from exc
    return cv2


class KeyFrameService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def extract_keyframes(
        self,
        *,
        db: Session,
        video_id: str,
        frame_indices: list[int],
        interval: int | None,
        reasons: list[str],
    ) -> KeyFrameExtractResponse:
        video = db.get(VideoItem, video_id)
        if video is None:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        if video.frame_count is None or video.frame_count <= 0:
            raise HTTPException(status_code=400, detail="Video metadata is incomplete; cannot extract keyframes.")

        targets = self._resolve_targets(
            frame_count=video.frame_count,
            frame_indices=frame_indices,
            interval=interval,
            reasons=reasons,
        )
        if not targets:
            raise HTTPException(status_code=400, detail="Provide frame_indices or interval for keyframe extraction.")

        cv2 = _load_opencv()
        capture = cv2.VideoCapture(video.file_path)
        if not capture.isOpened():
            capture.release()
            raise HTTPException(status_code=400, detail=f"Failed to open video: {video.filename}")

        dataset_root = Path(video.dataset.root_dir)
        keyframe_dir = dataset_root / "keyframes" / video.id
        keyframe_dir.mkdir(parents=True, exist_ok=True)

        created_keyframes: list[KeyFrame] = []
        existing_by_frame = {
            item.frame_index: item
            for item in db.query(KeyFrame).filter(KeyFrame.video_id == video.id).all()
        }

        try:
            for frame_index, reason in targets:
                if frame_index in existing_by_frame:
                    created_keyframes.append(existing_by_frame[frame_index])
                    continue

                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ok, frame = capture.read()
                if not ok or frame is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to read frame {frame_index} from video {video.filename}.",
                    )

                timestamp_ms = self._compute_timestamp_ms(frame_index=frame_index, fps=video.fps)
                image_filename = f"frame_{frame_index:06d}.jpg"
                image_path = safe_join(keyframe_dir, image_filename)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                Image.fromarray(frame_rgb).save(image_path, format="JPEG", quality=90)

                relative_url = f"/video_datasets/{video.dataset_id}/keyframes/{video.id}/{image_filename}"
                image_url = self._build_media_url(relative_url)
                keyframe = KeyFrame(
                    video_id=video.id,
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    selection_reason=reason,
                    image_path=str(image_path),
                    image_url=image_url,
                    annotation_status=VideoAnnotationStatus.PENDING.value,
                    review_status=KeyFrameReviewStatus.UNREVIEWED.value,
                )
                db.add(keyframe)
                db.flush()
                created_keyframes.append(keyframe)
        finally:
            capture.release()

        db.commit()
        for keyframe in created_keyframes:
            db.refresh(keyframe)

        return KeyFrameExtractResponse(
            video_id=video.id,
            extracted_count=len(created_keyframes),
            keyframes=[self.serialize_keyframe(item) for item in created_keyframes],
        )

    def list_keyframes(self, *, db: Session, video_id: str) -> list[KeyFrame]:
        video = db.get(VideoItem, video_id)
        if video is None:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
        return (
            db.query(KeyFrame)
            .filter(KeyFrame.video_id == video.id)
            .order_by(KeyFrame.frame_index.asc())
            .all()
        )

    def serialize_keyframe(self, keyframe: KeyFrame) -> KeyFrameRead:
        return KeyFrameRead.model_validate(keyframe)

    def _resolve_targets(
        self,
        *,
        frame_count: int,
        frame_indices: list[int],
        interval: int | None,
        reasons: list[str],
    ) -> list[tuple[int, str]]:
        targets: list[tuple[int, str]] = []
        seen: set[int] = set()

        normalized_indices = sorted({index for index in frame_indices if index >= 0})
        if normalized_indices:
            if len(reasons) not in {0, 1, len(normalized_indices)}:
                raise HTTPException(
                    status_code=400,
                    detail="reasons must be empty, a single value, or match frame_indices length.",
                )
            for idx, frame_index in enumerate(normalized_indices):
                if frame_index >= frame_count:
                    raise HTTPException(
                        status_code=400,
                        detail=f"frame_index {frame_index} exceeds video frame_count {frame_count}.",
                    )
                reason = (
                    reasons[idx]
                    if len(reasons) == len(normalized_indices)
                    else reasons[0]
                    if len(reasons) == 1
                    else KeyFrameReason.MANUAL.value
                )
                if frame_index not in seen:
                    seen.add(frame_index)
                    targets.append((frame_index, reason))

        if interval is not None:
            interval_reason = (
                reasons[0]
                if len(reasons) == 1 and not normalized_indices
                else KeyFrameReason.INTERVAL_SAMPLE.value
            )
            for frame_index in range(0, frame_count, interval):
                if frame_index not in seen:
                    seen.add(frame_index)
                    targets.append((frame_index, interval_reason))

        return sorted(targets, key=lambda item: item[0])

    def _compute_timestamp_ms(self, *, frame_index: int, fps: float | None) -> int:
        if fps is None or fps <= 0:
            return 0
        return int(round((frame_index / fps) * 1000))

    def _build_media_url(self, relative_url: str) -> str:
        if self.settings.media_base_url:
            return f"{self.settings.media_base_url.rstrip('/')}{relative_url}"
        return f"/media{relative_url}"
