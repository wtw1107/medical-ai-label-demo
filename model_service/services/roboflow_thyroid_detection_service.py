from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class RoboflowThyroidDetectionService:
    model_type = "detection"

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model_id: str | None = None,
        confidence: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ROBOFLOW_API_KEY", "").strip()
        self.api_url = api_url or os.getenv(
            "ROBOFLOW_API_URL",
            "https://serverless.roboflow.com",
        ).strip()
        self.roboflow_model_id = model_id or os.getenv(
            "ROBOFLOW_THYROID_MODEL_ID",
            "thyroid-nodules-detection-test/3",
        ).strip()
        self.confidence = confidence or self._read_confidence()

    @property
    def model_version(self) -> str:
        slug = self.roboflow_model_id.replace("/", "-")
        return f"roboflow-{slug}"

    def _read_confidence(self) -> float:
        raw_confidence = os.getenv("ROBOFLOW_CONFIDENCE", "0.25").strip() or "0.25"
        try:
            return float(raw_confidence)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid ROBOFLOW_CONFIDENCE value: {raw_confidence}. Expected a numeric value."
            ) from exc

    def _build_client(self) -> Any:
        if not self.api_key:
            raise RuntimeError(
                "ROBOFLOW_API_KEY is not set. Please set it before running Roboflow thyroid detection."
            )

        try:
            from inference_sdk import InferenceHTTPClient
        except ImportError as exc:
            raise RuntimeError(
                "inference_sdk is not installed. Please install model_service dependencies before running Roboflow thyroid detection."
            ) from exc

        return InferenceHTTPClient(
            api_url=self.api_url,
            api_key=self.api_key,
        )

    def _run_inference(self, image_path: Path) -> dict[str, Any]:
        client = self._build_client()
        return client.infer(str(image_path), model_id=self.roboflow_model_id)

    def _normalize_prediction(self, prediction: dict[str, Any]) -> dict[str, Any]:
        center_x = float(prediction.get("x", 0))
        center_y = float(prediction.get("y", 0))
        width = float(prediction.get("width", 0))
        height = float(prediction.get("height", 0))
        raw_confidence = float(prediction.get("confidence", prediction.get("score", 0.0)))

        left = center_x - (width / 2)
        top = center_y - (height / 2)

        label = str(
            prediction.get("class")
            or prediction.get("label")
            or prediction.get("class_name")
            or "thyroid_nodule"
        )
        class_id = prediction.get("class_id")
        if class_id is None:
            class_id = prediction.get("classId")

        return {
            "label": label,
            "score": raw_confidence,
            "bbox": {
                "x": int(round(left)),
                "y": int(round(top)),
                "width": int(round(width)),
                "height": int(round(height)),
            },
            "meta": {
                "source": "roboflow",
                "roboflow_model_id": self.roboflow_model_id,
                "class": label,
                "class_id": class_id,
                "raw_confidence": raw_confidence,
                "local_confidence_threshold": self.confidence,
            },
        }

    def _build_platform_response(self, predictions: list[dict[str, Any]]) -> dict[str, Any]:
        parsed_predictions = [
            self._normalize_prediction(prediction)
            for prediction in predictions
            if float(prediction.get("confidence", prediction.get("score", 0.0)))
            >= self.confidence
        ]
        return {
            "model_id": "real_detection_v1",
            "model_version": self.model_version,
            "model_type": self.model_type,
            "predictions": parsed_predictions,
        }

    def predict_raw(self, image_path: str | Path) -> dict[str, Any]:
        path = Path(image_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")

        return self._run_inference(image_path=path)

    def predict_image(
        self,
        image_path: str | Path,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        raw_result = self.predict_raw(image_path=image_path)
        predictions = raw_result.get("predictions", [])
        platform_result = self._build_platform_response(predictions=predictions)

        if include_raw:
            platform_result["raw"] = raw_result
            platform_result["debug"] = {
                "confidence": self.confidence,
                "raw_prediction_count": len(predictions),
                "parsed_prediction_count": len(platform_result["predictions"]),
            }

        return platform_result
