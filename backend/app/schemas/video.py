from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    BLineGrade,
    DataType,
    DatasetSplit,
    DeidentificationStatus,
    KeyFrameReviewStatus,
    KeyFrameReason,
    TaskType,
    VideoAnnotationStatus,
    VideoQuality,
)


class VideoUploadWarning(BaseModel):
    filename: str
    message: str


class VideoUploadMetadata(BaseModel):
    filename: str
    patient_uid: str
    lung_zone: str
    probe: str | None = None
    device: str | None = None
    depth: str | None = None
    orientation: str | None = None
    deid_status: str = DeidentificationStatus.UNKNOWN.value
    site: str | None = None
    device_group: str | None = None


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
    quality: str = VideoQuality.UNKNOWN.value
    bline_grade: str = BLineGrade.UNKNOWN.value
    uncertain_flag: bool = False
    include_in_training: bool = True
    review_comment: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    keyframe_count: int = 0
    cvat_task_id: int | None = None
    cvat_job_id: int | None = None
    cvat_task_url: str | None = None
    cvat_job_url: str | None = None
    cvat_status: str | None = None
    cvat_annotation_updated_at: datetime | None = None
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
    annotation_backend: str | None = None
    cvat_project_id: int | None = None
    cvat_project_url: str | None = None
    video_count: int
    patient_count: int
    keyframe_count: int
    split_summary: list[SplitSummaryItem]
    review_status_summary: list[ReviewSummaryItem]


class VideoDatasetListItemResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    data_type: str = DataType.VIDEO.value
    task_type: str = TaskType.VIDEO_BLINE_SEGMENTATION.value
    annotation_backend: str | None = None
    patient_count: int
    video_count: int
    keyframe_count: int
    annotated_count: int
    reviewed_count: int
    initialized_video_count: int = 0
    uninitialized_video_count: int = 0
    selected_keyframe_count: int = 0
    unresolved_issue_count: int = 0
    cvat_status_summary: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class VideoDatasetListResponse(BaseModel):
    items: list[VideoDatasetListItemResponse]
    total: int


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
    label_studio_project_id: int | None = None
    label_studio_task_id: int | None = None
    label_studio_task_url: str | None = None
    annotation_status: str = VideoAnnotationStatus.PENDING.value
    review_status: str = KeyFrameReviewStatus.UNREVIEWED.value
    annotation_updated_at: datetime | None = None
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


class KeyFrameLabelStudioInitRequest(BaseModel):
    keyframe_ids: list[str] = Field(default_factory=list)
    project_title: str | None = None


class KeyFrameLabelStudioInitResponse(BaseModel):
    video_id: str
    label_studio_project_id: int
    label_studio_project_url: str
    initialized_count: int
    reused_count: int
    keyframes: list[KeyFrameRead]


class ReviewStatusSummaryItem(BaseModel):
    review_status: str
    count: int


class KeyFrameLabelStudioSyncResponse(BaseModel):
    video_id: str
    total_keyframes: int
    labeled_count: int
    unlabeled_count: int
    review_status_summary: list[ReviewStatusSummaryItem]
    keyframes: list[KeyFrameRead]


class VideoKeyframeExportResponse(BaseModel):
    export_id: str
    dataset_id: str
    total_labeled_count: int
    skipped_count: int
    file_path: str
    download_url: str


class CvatHealthResponse(BaseModel):
    configured: bool
    reachable: bool
    authenticated: bool
    server_version: str | None = None
    authenticated_username: str | None = None
    default_assignee_username: str | None = None
    organization_slug: str | None = None
    review_supported: bool | None = None
    issue_supported: bool | None = None
    consensus_supported: bool | None = None
    error: str | None = None


class CvatVideoMappingItem(BaseModel):
    video_id: str
    cvat_task_id: int | None = None
    cvat_job_id: int | None = None
    cvat_task_url: str | None = None
    cvat_job_url: str | None = None
    status: str | None = None
    keyframe_tag_count: int = 0
    positive_frame_count: int = 0
    negative_frame_count: int = 0
    uncertain_frame_count: int = 0
    polygon_count: int = 0
    issue_count: int = 0
    unresolved_issue_count: int = 0
    resolved_issue_count: int = 0
    error: str | None = None


class CvatInitResponse(BaseModel):
    dataset_id: str
    cvat_project_id: int | None = None
    cvat_project_url: str | None = None
    created_task_count: int
    reused_task_count: int
    repaired_task_count: int = 0
    failed_task_count: int = 0
    videos: list[CvatVideoMappingItem]
    owner_username: str | None = None
    assignee_username: str | None = None
    organization_slug: str | None = None
    warning: str | None = None
    error: str | None = None


class CvatSyncResponse(BaseModel):
    dataset_id: str
    total_videos: int
    counts: dict[str, int]
    issues_count: int
    videos: list[CvatVideoMappingItem]
    error: str | None = None


class CvatAnnotationSummaryResponse(BaseModel):
    video_id: str
    frame_count: int | None = None
    selected_keyframe_count: int = 0
    pending_frame_count: int = 0
    keyframe_tag_count: int = 0
    positive_frame_count: int = 0
    negative_frame_count: int = 0
    uncertain_frame_count: int = 0
    polygon_count: int = 0
    issue_count: int = 0
    unresolved_issue_count: int = 0
    resolved_issue_count: int = 0
    cvat_task_status: str | None = None
    cvat_job_state: str | None = None
    cvat_job_stage: str | None = None
    annotation_updated_at: datetime | None = None
    review_status: str | None = None
    error: str | None = None


class CvatAccessResponse(BaseModel):
    video_id: str
    initialized: bool
    task_exists: bool
    job_exists: bool
    owner_username: str | None = None
    assignee_username: str | None = None
    organization_slug: str | None = None
    job_url: str | None = None
    access_ready: bool
    warning: str | None = None
