from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import DataType, VideoQuality
from app.db.models import KeyFrame, Patient, VideoItem, VideoReview
from app.db.session import get_db
from app.schemas.video import (
    KeyFrameExtractRequest,
    KeyFrameExtractResponse,
    KeyFrameListResponse,
    ReviewSummaryItem,
    SplitSummaryItem,
    VideoDatasetSummaryResponse,
    VideoDatasetUploadResponse,
    VideoListResponse,
    VideoReviewResponse,
    VideoReviewUpdateRequest,
)
from app.services.keyframe_service import KeyFrameService
from app.services.video_storage_service import VideoStorageService

router = APIRouter(prefix="/api", tags=["videos"])


@router.post("/video-datasets/upload", response_model=VideoDatasetUploadResponse)
def upload_video_dataset(
    dataset_name: str = Form(...),
    patient_uid: str = Form(...),
    lung_zone: str | None = Form(default=None),
    probe: str | None = Form(default=None),
    device: str | None = Form(default=None),
    depth: str | None = Form(default=None),
    orientation: str | None = Form(default=None),
    deid_status: str | None = Form(default=None),
    site: str | None = Form(default=None),
    device_group: str | None = Form(default=None),
    files: list[UploadFile] = File(
        ...,
        json_schema_extra={"items": {"type": "string", "format": "binary"}},
    ),
    db: Session = Depends(get_db),
) -> VideoDatasetUploadResponse:
    service = VideoStorageService(get_settings())
    return service.upload_video_dataset(
        db=db,
        dataset_name=dataset_name,
        patient_uid=patient_uid,
        files=files,
        lung_zone=lung_zone,
        probe=probe,
        device=device,
        depth=depth,
        orientation=orientation,
        deid_status=deid_status,
        site=site,
        device_group=device_group,
    )


@router.get("/video-datasets/{dataset_id}", response_model=VideoDatasetSummaryResponse)
def get_video_dataset_summary(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> VideoDatasetSummaryResponse:
    service = VideoStorageService(get_settings())
    dataset = service.get_dataset_summary(db=db, dataset_id=dataset_id)

    videos = db.query(VideoItem).filter(VideoItem.dataset_id == dataset.id).all()
    patients = db.query(Patient).filter(Patient.dataset_id == dataset.id).all()
    keyframe_count = (
        db.query(KeyFrame)
        .join(VideoItem, KeyFrame.video_id == VideoItem.id)
        .filter(VideoItem.dataset_id == dataset.id)
        .count()
    )
    reviews = (
        db.query(VideoReview)
        .join(VideoItem, VideoReview.video_id == VideoItem.id)
        .filter(VideoItem.dataset_id == dataset.id)
        .all()
    )

    videos_by_patient = defaultdict(int)
    for video in videos:
        if video.patient_id:
            videos_by_patient[video.patient_id] += 1

    split_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"patient_count": 0, "video_count": 0})
    for patient in patients:
        split_counts[patient.split]["patient_count"] += 1
        split_counts[patient.split]["video_count"] += videos_by_patient.get(patient.id, 0)

    review_counts: dict[str, int] = defaultdict(int)
    for review in reviews:
        review_counts[review.quality] += 1
    if not review_counts:
        review_counts[VideoQuality.UNKNOWN.value] = 0

    return VideoDatasetSummaryResponse(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        data_type=dataset.data_type,
        video_count=len(videos),
        patient_count=len(patients),
        keyframe_count=keyframe_count,
        split_summary=[
            SplitSummaryItem(
                split=split,
                patient_count=counts["patient_count"],
                video_count=counts["video_count"],
            )
            for split, counts in sorted(split_counts.items())
        ],
        review_status_summary=[
            ReviewSummaryItem(quality=quality, count=count)
            for quality, count in sorted(review_counts.items())
        ],
    )


@router.get("/video-datasets/{dataset_id}/videos", response_model=VideoListResponse)
def list_video_dataset_videos(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> VideoListResponse:
    service = VideoStorageService(get_settings())
    videos = service.list_dataset_videos(db=db, dataset_id=dataset_id)
    return VideoListResponse(
        dataset_id=dataset_id,
        videos=[service.serialize_video_item(video) for video in videos],
        total=len(videos),
    )


@router.patch("/videos/{video_id}/review", response_model=VideoReviewResponse)
def update_video_review(
    video_id: str,
    payload: VideoReviewUpdateRequest,
    db: Session = Depends(get_db),
) -> VideoReviewResponse:
    settings = get_settings()
    video = db.get(VideoItem, video_id)
    if video is None or video.dataset.data_type != DataType.VIDEO.value:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    review = (
        db.query(VideoReview)
        .filter(VideoReview.video_id == video.id)
        .order_by(VideoReview.created_at.desc())
        .first()
    )
    if review is None:
        review = VideoReview(video_id=video.id)
        db.add(review)

    from datetime import datetime, timezone

    review.quality = payload.quality
    review.bline_grade = payload.bline_grade
    review.uncertain_flag = payload.uncertain_flag
    review.include_in_training = payload.include_in_training
    review.comment = payload.comment
    review.reviewed_by = payload.reviewed_by or settings.default_user_id
    review.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(review)
    return VideoReviewResponse(
        video_id=video.id,
        quality=review.quality,
        bline_grade=review.bline_grade,
        uncertain_flag=review.uncertain_flag,
        include_in_training=review.include_in_training,
        comment=review.comment,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at,
    )


@router.post("/videos/{video_id}/keyframes/extract", response_model=KeyFrameExtractResponse)
def extract_keyframes(
    video_id: str,
    payload: KeyFrameExtractRequest,
    db: Session = Depends(get_db),
) -> KeyFrameExtractResponse:
    service = KeyFrameService(get_settings())
    return service.extract_keyframes(
        db=db,
        video_id=video_id,
        frame_indices=payload.frame_indices,
        interval=payload.interval,
        reasons=payload.reasons,
    )


@router.get("/videos/{video_id}/keyframes", response_model=KeyFrameListResponse)
def list_keyframes(
    video_id: str,
    db: Session = Depends(get_db),
) -> KeyFrameListResponse:
    service = KeyFrameService(get_settings())
    keyframes = service.list_keyframes(db=db, video_id=video_id)
    return KeyFrameListResponse(
        video_id=video_id,
        keyframes=[service.serialize_keyframe(item) for item in keyframes],
        total=len(keyframes),
    )
