from pydantic import BaseModel


class ModelRequirementsResponse(BaseModel):
    api_key: bool | None = None
    network: bool | None = None
    gpu: bool | None = None
    local_weights: bool | None = None


class ModelRuntimeResponse(BaseModel):
    api_key_env: str | None = None
    api_url_env: str | None = None
    confidence_env: str | None = None


class ModelMetricsResponse(BaseModel):
    source: str | None = None
    scanned_image_count: int | None = None
    tested_count: int | None = None
    images_with_detections: int | None = None
    total_detections: int | None = None


class ModelInfoResponse(BaseModel):
    model_id: str
    model_name: str
    model_type: str
    model_version: str
    status: str
    description: str
    deployment_type: str | None = None
    provider: str | None = None
    task_types: list[str] | None = None
    anatomy: list[str] | None = None
    modality: list[str] | None = None
    outputs: list[str] | None = None
    requires: ModelRequirementsResponse | None = None
    runtime: ModelRuntimeResponse | None = None
    metrics: ModelMetricsResponse | None = None
    limitations: list[str] | None = None


class ModelListResponse(BaseModel):
    items: list[ModelInfoResponse]
