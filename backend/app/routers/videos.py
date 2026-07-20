from __future__ import annotations

import json
from collections import defaultdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import DataType, VideoAnnotationStatus, VideoQuality
from app.db.models import Dataset, KeyFrame, Patient, VideoItem, VideoReview
from app.db.session import get_db
from app.schemas.video import (
    KeyFrameExtractRequest,
    KeyFrameExtractResponse,
    KeyFrameLabelStudioInitRequest,
    KeyFrameLabelStudioInitResponse,
    KeyFrameLabelStudioSyncResponse,
    KeyFrameListResponse,
    CvatAccessResponse,
    CvatAnnotationSummaryResponse,
    CvatHealthResponse,
    CvatInitResponse,
    CvatSyncResponse,
    ReviewSummaryItem,
    SplitSummaryItem,
    VideoDatasetListItemResponse,
    VideoDatasetListResponse,
    VideoDatasetSummaryResponse,
    VideoDatasetUploadResponse,
    VideoKeyframeExportResponse,
    VideoListResponse,
    VideoReviewResponse,
    VideoReviewUpdateRequest,
    VideoUploadMetadata,
)
from app.services.cvat_service import CvatService
from app.services.video_keyframe_export_service import VideoKeyframeExportService
from app.services.video_keyframe_label_studio_service import VideoKeyframeLabelStudioService
from app.services.keyframe_service import KeyFrameService
from app.services.video_storage_service import VideoStorageService

router = APIRouter(prefix="/api", tags=["videos"])


@router.post("/video-datasets/upload", response_model=VideoDatasetUploadResponse)
def upload_video_dataset(
    dataset_name: str = Form(...),
    patient_uid: str | None = Form(default=None),
    metadata_json: str | None = Form(default=None),
    annotation_backend: str | None = Form(default=None),
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
    normalized_backend = (annotation_backend or "native").strip()
    if normalized_backend == "cvat":
        cvat_health = CvatService(get_settings()).health()
        if not cvat_health.reachable or not cvat_health.authenticated:
            raise HTTPException(
                status_code=503,
                detail=f"CVAT is only available for legacy video tasks and is not ready: {cvat_health.error}",
            )
    video_metadata = None
    if metadata_json:
        try:
            raw_items = json.loads(metadata_json)
            if not isinstance(raw_items, list):
                raise ValueError("metadata_json must be a JSON list.")
            video_metadata = [VideoUploadMetadata.model_validate(item) for item in raw_items]
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid metadata_json: {exc}") from exc
        errors: list[str] = []
        for item in video_metadata:
            missing: list[str] = []
            if not item.patient_uid.strip():
                missing.append("patient_uid")
            if not item.lung_zone.strip():
                missing.append("lung_zone")
            if not item.deid_status.strip() or item.deid_status.strip() == "unknown":
                missing.append("deid_status")
            if missing:
                errors.append(f"{item.filename}: missing {', '.join(missing)}")
        if errors:
            raise HTTPException(status_code=400, detail="Invalid video metadata. " + "; ".join(errors))
    return service.upload_video_dataset(
        db=db,
        dataset_name=dataset_name,
        patient_uid=patient_uid,
        video_metadata=video_metadata,
        annotation_backend=normalized_backend,
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


@router.get("/video-datasets", response_model=VideoDatasetListResponse)
def list_video_datasets(
    db: Session = Depends(get_db),
) -> VideoDatasetListResponse:
    datasets = (
        db.query(Dataset)
        .filter(Dataset.data_type == DataType.VIDEO.value)
        .order_by(Dataset.updated_at.desc())
        .all()
    )

    items: list[VideoDatasetListItemResponse] = []
    for dataset in datasets:
        patient_count = db.query(Patient).filter(Patient.dataset_id == dataset.id).count()
        videos = db.query(VideoItem).filter(VideoItem.dataset_id == dataset.id).all()
        video_count = len(videos)
        initialized_video_count = sum(1 for video in videos if video.cvat_task_id is not None and video.cvat_job_id is not None)
        uninitialized_video_count = max(video_count - initialized_video_count, 0)
        cvat_status_summary: dict[str, int] = defaultdict(int)
        for video in videos:
            cvat_status_summary[video.cvat_status or "not_initialized"] += 1
        effective_annotation_backend = dataset.annotation_backend
        if effective_annotation_backend is None and (dataset.cvat_project_id is not None or initialized_video_count > 0):
            effective_annotation_backend = "cvat"
        keyframe_count = (
            db.query(KeyFrame)
            .join(VideoItem, KeyFrame.video_id == VideoItem.id)
            .filter(VideoItem.dataset_id == dataset.id)
            .count()
        )
        annotated_count = (
            db.query(KeyFrame)
            .join(VideoItem, KeyFrame.video_id == VideoItem.id)
            .filter(
                VideoItem.dataset_id == dataset.id,
                KeyFrame.annotation_status == VideoAnnotationStatus.ANNOTATED.value,
            )
            .count()
        )
        reviewed_count = (
            db.query(VideoReview)
            .join(VideoItem, VideoReview.video_id == VideoItem.id)
            .filter(VideoItem.dataset_id == dataset.id)
            .count()
        )

        items.append(
            VideoDatasetListItemResponse(
                dataset_id=dataset.id,
                dataset_name=dataset.name,
                data_type=dataset.data_type,
                annotation_backend=effective_annotation_backend,
                patient_count=patient_count,
                video_count=video_count,
                keyframe_count=keyframe_count,
                annotated_count=annotated_count,
                reviewed_count=reviewed_count,
                initialized_video_count=initialized_video_count,
                uninitialized_video_count=uninitialized_video_count,
                selected_keyframe_count=keyframe_count,
                unresolved_issue_count=0,
                cvat_status_summary=dict(cvat_status_summary),
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
            )
        )

    return VideoDatasetListResponse(items=items, total=len(items))


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
        annotation_backend=dataset.annotation_backend,
        cvat_project_id=dataset.cvat_project_id,
        cvat_project_url=dataset.cvat_project_url,
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


@router.get("/integrations/cvat/health", response_model=CvatHealthResponse)
def get_cvat_health() -> CvatHealthResponse:
    service = CvatService(get_settings())
    return service.health()


@router.post("/video-datasets/{dataset_id}/cvat/init", response_model=CvatInitResponse)
def init_video_dataset_cvat(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> CvatInitResponse:
    service = CvatService(get_settings())
    return service.init_dataset(db=db, dataset_id=dataset_id)


@router.post("/video-datasets/{dataset_id}/cvat/sync", response_model=CvatSyncResponse)
def sync_video_dataset_cvat(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> CvatSyncResponse:
    service = CvatService(get_settings())
    return service.sync_dataset(db=db, dataset_id=dataset_id)


@router.get("/videos/{video_id}/cvat/annotations-summary", response_model=CvatAnnotationSummaryResponse)
def get_video_cvat_annotations_summary(
    video_id: str,
    db: Session = Depends(get_db),
) -> CvatAnnotationSummaryResponse:
    service = CvatService(get_settings())
    return service.get_annotations_summary(db=db, video_id=video_id)


@router.get("/videos/{video_id}/cvat/access", response_model=CvatAccessResponse)
def get_video_cvat_access(
    video_id: str,
    db: Session = Depends(get_db),
) -> CvatAccessResponse:
    service = CvatService(get_settings())
    return service.get_video_access(db=db, video_id=video_id)


@router.post("/video-datasets/{dataset_id}/exports/cvat-bline-test", response_model=VideoKeyframeExportResponse)
def export_cvat_bline_test(
    dataset_id: str,
) -> VideoKeyframeExportResponse:
    service = CvatService(get_settings())
    return service.export_bline_test(dataset_id=dataset_id)


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


@router.post("/videos/{video_id}/keyframes/label-studio/init", response_model=KeyFrameLabelStudioInitResponse)
def init_keyframe_label_studio_tasks(
    video_id: str,
    payload: KeyFrameLabelStudioInitRequest,
    db: Session = Depends(get_db),
) -> KeyFrameLabelStudioInitResponse:
    service = VideoKeyframeLabelStudioService(get_settings())
    return service.init_keyframe_tasks(
        db=db,
        video_id=video_id,
        keyframe_ids=payload.keyframe_ids,
        project_title=payload.project_title,
    )


@router.post("/videos/{video_id}/keyframes/sync-label-studio-status", response_model=KeyFrameLabelStudioSyncResponse)
def sync_keyframe_label_studio_status(
    video_id: str,
    db: Session = Depends(get_db),
) -> KeyFrameLabelStudioSyncResponse:
    service = VideoKeyframeLabelStudioService(get_settings())
    return service.sync_keyframe_status(db=db, video_id=video_id)


@router.post("/video-datasets/{dataset_id}/exports/bline-keyframes", response_model=VideoKeyframeExportResponse)
def export_bline_keyframes(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> VideoKeyframeExportResponse:
    service = VideoKeyframeExportService(get_settings())
    payload = service.export_dataset(db=db, dataset_id=dataset_id)
    return VideoKeyframeExportResponse(**payload)


@router.get("/video-exports/{export_id}/download")
def download_video_export(
    export_id: str,
) -> FileResponse:
    service = VideoKeyframeExportService(get_settings())
    try:
        path = service.get_download_path(export_id)
    except HTTPException:
        settings = get_settings()
        path = settings.ensure_data_root() / "exports" / "cvat_bline" / export_id / f"{export_id}.zip"
        if not path.exists():
            raise
    return FileResponse(path, media_type="application/zip", filename=path.name)
