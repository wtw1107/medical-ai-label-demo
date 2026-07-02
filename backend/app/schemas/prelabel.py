from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PrelabelJobBase(BaseModel):
    task_id: str


class PrelabelJobCreate(PrelabelJobBase):
    pass


class PrelabelJobRead(PrelabelJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    pending_confirm: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PrelabelRunResponse(BaseModel):
    job_id: str
    task_id: str
    status: str
    total_count: int
    success_count: int
    failed_count: int


class PrelabelRunRequest(BaseModel):
    detection_model_id: str | None = None
    segmentation_model_id: str | None = None


class PrelabelJobStatusResponse(BaseModel):
    job_id: str
    task_id: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    error_message: str | None = None


class TaskImageStatusItem(BaseModel):
    image_id: str
    filename: str
    status: str
    has_prediction: bool
    has_annotation: bool
    prediction_status: str = "none"
    annotation_status: str = "unsaved"
    label_studio_task_id: int | None = None
    label_studio_task_url: str | None = None


class TaskImageStatusResponse(BaseModel):
    task_id: str
    images: list[TaskImageStatusItem]


class LabelStudioStatusSyncResponse(BaseModel):
    task_id: str
    synced_count: int
    prediction_written_count: int
    annotation_saved_count: int
    images: list[TaskImageStatusItem]


class PredictionPreviewValue(BaseModel):
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    points: list[list[float]] = []


class PredictionPreviewItem(BaseModel):
    type: str
    label: str
    score: float | None = None
    model_id: str | None = None
    model_version: str | None = None
    model_type: str | None = None
    created_at: str | None = None
    meta: dict[str, object] | None = None
    value: PredictionPreviewValue


class PredictionPreviewResponse(BaseModel):
    task_id: str
    image_id: str
    filename: str
    image_url: str
    image_width: int | None = None
    image_height: int | None = None
    label_studio_task_id: int | None = None
    label_studio_task_url: str | None = None
    has_prediction: bool
    model_id: str | None = None
    model_version: str | None = None
    model_type: str | None = None
    predictions: list[PredictionPreviewItem]
    raw_prediction_count: int
