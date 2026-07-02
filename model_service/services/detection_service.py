from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from schemas import DetectionPredictRequest, DetectionPredictResponse, DetectionResult
from services.roboflow_thyroid_detection_service import RoboflowThyroidDetectionService
from utils.geometry import clamp_bbox, default_detection_bbox
from utils.image_loader import try_load_image_info


class MockDetectionService:
    model_version = "v0.1"
    model_type = "detection"

    def predict(
        self,
        request: DetectionPredictRequest,
    ) -> DetectionPredictResponse:
        image_info = try_load_image_info(request.image_url)
        bbox = default_detection_bbox(image_info.width, image_info.height)
        bbox = clamp_bbox(bbox, image_info.width, image_info.height)

        return DetectionPredictResponse(
            model_id=request.model_id,
            model_version=self.model_version,
            model_type=self.model_type,
            results=[
                DetectionResult(
                    label="病灶",
                    bbox=bbox,
                    score=0.91,
                )
            ],
        )


class DetectionService:
    def __init__(self) -> None:
        self.mock_service = MockDetectionService()
        self.roboflow_service = RoboflowThyroidDetectionService()

    def predict(self, request: DetectionPredictRequest) -> DetectionPredictResponse:
        if request.model_id == "mock_detection":
            return self.mock_service.predict(request)
        if request.model_id == "real_detection_v1":
            return self._predict_roboflow(request)
        raise RuntimeError(f"Unsupported detection model_id: {request.model_id}")

    def _predict_roboflow(self, request: DetectionPredictRequest) -> DetectionPredictResponse:
        with self._download_image_to_tempfile(request.image_url) as image_path:
            result = self.roboflow_service.predict_image(image_path)

        detections = []
        for prediction in result.get("predictions", []):
            if not isinstance(prediction, dict):
                continue
            bbox = prediction.get("bbox", {})
            if not isinstance(bbox, dict):
                continue
            detections.append(
                DetectionResult(
                    label=str(prediction.get("label", "thyroid_nodule")),
                    bbox=[
                        int(bbox.get("x", 0)),
                        int(bbox.get("y", 0)),
                        int(bbox.get("width", 0)),
                        int(bbox.get("height", 0)),
                    ],
                    score=float(prediction.get("score", 0.0)),
                    meta=prediction.get("meta") if isinstance(prediction.get("meta"), dict) else None,
                )
            )

        return DetectionPredictResponse(
            model_id=str(result.get("model_id", request.model_id)),
            model_version=str(result.get("model_version", self.roboflow_service.model_version)),
            model_type=str(result.get("model_type", self.roboflow_service.model_type)),
            results=detections,
        )

    def _download_image_to_tempfile(self, image_url: str):
        suffix = Path(urlparse(image_url).path).suffix or ".png"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = Path(temp_file.name)
        temp_file.close()

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True, trust_env=False) as client:
                response = client.get(image_url)
                response.raise_for_status()
            temp_path.write_bytes(response.content)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        class _TempFileContext:
            def __enter__(self_nonlocal) -> Path:
                return temp_path

            def __exit__(self_nonlocal, exc_type, exc, tb) -> None:
                if temp_path.exists():
                    temp_path.unlink()

        return _TempFileContext()
