import httpx
from fastapi import FastAPI, HTTPException

from schemas import (
    DetectionPredictRequest,
    DetectionPredictResponse,
    HealthResponse,
    SegmentationPredictRequest,
    SegmentationPredictResponse,
)
from services.detection_service import DetectionService
from services.segmentation_service import MockSegmentationService

app = FastAPI(
    title="Model Service",
    version="0.1.0",
    description="Local model service for mock and real-model integration demos.",
)

detection_service = DetectionService()
segmentation_service = MockSegmentationService()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="model-service")


@app.post("/predict/detection", response_model=DetectionPredictResponse)
def predict_detection(
    request: DetectionPredictRequest,
) -> DetectionPredictResponse:
    try:
        return detection_service.predict(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image for detection: {exc}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Failed to download image for detection: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/predict/segmentation", response_model=SegmentationPredictResponse)
def predict_segmentation(
    request: SegmentationPredictRequest,
) -> SegmentationPredictResponse:
    return segmentation_service.predict(request)
