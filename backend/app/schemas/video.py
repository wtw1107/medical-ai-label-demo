from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    BLineGrade,
    DatasetSplit,
    DeidentificationStatus,
    KeyFrameReason,
    VideoAnnotationStatus,
    VideoQuality,
)


class VideoUploadWarning(BaseModel):
    filename: str
    message: str


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    patient_uid: str
    split: str = DatasetSplit.UNASSIGNED.value
    site: str | None = None
    device_group: str | None = None


class VideoItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    patient_id: str | None = None
    patient_uid: str | None = None
    filename: str
    file_path: str
    file_url: str
    duration_sec: float | None = None
    fps: float | None = None
    frame_count: int | None = None
    width: int | None = None
    height: int | None = None
    preview_image_path: str | None = None
    preview_image_url: str | None = None
    lung_zone: str | None = None
    probe: str | None = None
    orientation: str | None = None
    device: str | None = None
    depth: str | None = None
    deid_status: str = DeidentificationStatus.UNKNOWN.value
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class VideoDatasetUploadResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    video_count: int
    patient_count: int
    videos: list[VideoItemRead]
    warnings: list[VideoUploadWarning] = Field(default_factory=list)


class SplitSummaryItem(BaseModel):
    split: str
    patient_count: int
    video_count: int


class ReviewSummaryItem(BaseModel):
    quality: str
    count: int


class VideoDatasetSummaryResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    data_type: str
    video_count: int
    patient_count: int
    keyframe_count: int
    split_summary: list[SplitSummaryItem]
    review_status_summary: list[ReviewSummaryItem]


class VideoListResponse(BaseModel):
    dataset_id: str
    videos: list[VideoItemRead]
    total: int


class VideoReviewUpdateRequest(BaseModel):
    quality: VideoQuality = Field(default=VideoQuality.UNKNOWN.value)
    bline_grade: BLineGrade = Field(default=BLineGrade.UNKNOWN.value)
    uncertain_flag: bool = False
    include_in_training: bool = True
    comment: str | None = None
    reviewed_by: str | None = None


class VideoReviewResponse(BaseModel):
    video_id: str
    quality: str
    bline_grade: str
    uncertain_flag: bool
    include_in_training: bool
    comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class KeyFrameExtractRequest(BaseModel):
    frame_indices: list[int] = Field(default_factory=list)
    interval: int | None = Field(default=None, ge=1)
    reasons: list[KeyFrameReason] = Field(default_factory=list)


class KeyFrameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    frame_index: int
    timestamp_ms: int
    selection_reason: str = KeyFrameReason.MANUAL.value
    image_path: str
    image_url: str
    annotation_status: str = VideoAnnotationStatus.PENDING.value
    review_status: str
    created_at: datetime
    updated_at: datetime


class KeyFrameExtractResponse(BaseModel):
    video_id: str
    extracted_count: int
    keyframes: list[KeyFrameRead]


class KeyFrameListResponse(BaseModel):
    video_id: str
    keyframes: list[KeyFrameRead]
    total: int
