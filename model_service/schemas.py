from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class PredictionRequestBase(BaseModel):
    image_url: str = Field(..., description="Publicly accessible image URL.")
    image_id: str = Field(..., description="Image identifier from the backend.")
    model_id: str = Field(..., description="Requested mock model identifier.")


class DetectionPredictRequest(PredictionRequestBase):
    pass


class SegmentationPrompt(BaseModel):
    bbox: list[int] | None = Field(
        default=None,
        description="Optional bbox prompt in [x1, y1, x2, y2] format.",
        min_length=4,
        max_length=4,
    )


class SegmentationPredictRequest(PredictionRequestBase):
    prompts: SegmentationPrompt | None = Field(
        default=None,
        description="Optional prompt payload for segmentation.",
    )


class DetectionResult(BaseModel):
    label: str
    bbox: list[int] = Field(..., min_length=4, max_length=4)
    score: float


class SegmentationResult(BaseModel):
    label: str
    polygon: list[list[int]]
    score: float


class DetectionPredictResponse(BaseModel):
    model_id: str
    model_version: str
    results: list[DetectionResult]


class SegmentationPredictResponse(BaseModel):
    model_id: str
    model_version: str
    results: list[SegmentationResult]


class ImageInfo(BaseModel):
    width: int
    height: int
    source: str


class LoadImageError(BaseModel):
    message: str
    image_url: str
    detail: Any | None = None
