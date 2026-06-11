from fastapi import FastAPI

from schemas import (
    DetectionPredictRequest,
    DetectionPredictResponse,
    HealthResponse,
    SegmentationPredictRequest,
    SegmentationPredictResponse,
)
from services.detection_service import MockDetectionService
from services.segmentation_service import MockSegmentationService

app = FastAPI(
    title="Mock Model Service",
    version="0.1.0",
    description="Mock model service for local detection and segmentation demos.",
)

detection_service = MockDetectionService()
segmentation_service = MockSegmentationService()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="mock-model-service")


@app.post("/predict/detection", response_model=DetectionPredictResponse)
def predict_detection(
    request: DetectionPredictRequest,
) -> DetectionPredictResponse:
    return detection_service.predict(request)


@app.post("/predict/segmentation", response_model=SegmentationPredictResponse)
def predict_segmentation(
    request: SegmentationPredictRequest,
) -> SegmentationPredictResponse:
    return segmentation_service.predict(request)
