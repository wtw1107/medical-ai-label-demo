from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import requests
from PIL import Image

from mmdet.apis import inference_detector, init_detector

from model_service.schemas import (
    DetectionPredictRequest,
    DetectionPredictResponse,
    DetectionResult,
)


class DinoDetectionService:
    """TN5000 DINO-family detection service.

    The service is intentionally small and dependency-light for demo usage. It
    loads the best TN5000 DINO-based uncertainty checkpoint and returns a short
    ranked list of detections. If the underlying model exposes an uncertainty
    tensor (e.g. box_unc), it is preserved in the raw payload returned by
    `predict_raw`.
    """

    model_version = "uq-dino-variance-20260515"
    model_type = "detection"
    label_map = {
        0: "benign thyroid nodule",
        1: "malignant thyroid nodule",
    }

    def __init__(
        self,
        config_path: str | Path | None = None,
        checkpoint_path: str | Path | None = None,
        device: str = "cuda:0",
        max_results: int = 10,
        score_thr: float = 0.05,
    ) -> None:
        self.root = Path(__file__).resolve().parents[2]
        self.config_path = Path(config_path) if config_path else self.root / "models" / "configs" / "dino_detection" / "dino_config.py"
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else self.root / "models" / "weights" / "dino_detection" / "best.pth"
        self.device = device
        self.max_results = max_results
        self.score_thr = score_thr
        self.model = None

    def load(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {self.checkpoint_path}")
        self.model = init_detector(str(self.config_path), str(self.checkpoint_path), device=self.device)

    def _ensure_model(self) -> None:
        if self.model is None:
            self.load()

    @staticmethod
    def _load_image(image_url: str) -> np.ndarray:
        parsed = urlparse(image_url)
        if parsed.scheme in {"http", "https"}:
            resp = requests.get(image_url, timeout=30)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            return np.array(img)
        path = Path(image_url)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_url}")
        img = Image.open(path).convert("RGB")
        return np.array(img)

    @staticmethod
    def _to_list(value: Any) -> list:
        if value is None:
            return []
        if hasattr(value, "detach"):
            return value.detach().cpu().tolist()
        if hasattr(value, "tolist"):
            return value.tolist()
        return list(value)

    def predict_raw(self, image_url: str, score_thr: float | None = None) -> dict:
        self._ensure_model()
        image = self._load_image(image_url)
        result = inference_detector(self.model, image)
        pred = result.pred_instances
        scores = self._to_list(getattr(pred, "scores", None))
        labels = self._to_list(getattr(pred, "labels", None))
        bboxes = self._to_list(getattr(pred, "bboxes", None))
        box_unc = self._to_list(getattr(pred, "box_unc", None))
        threshold = self.score_thr if score_thr is None else score_thr

        order = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)
        detections = []
        for idx in order:
            score = float(scores[idx])
            if score < threshold:
                continue
            det = {
                "label_id": int(labels[idx]),
                "label_name": self.label_map.get(int(labels[idx]), str(int(labels[idx]))),
                "score": score,
                "bbox_xyxy": [int(round(v)) for v in bboxes[idx]],
            }
            if box_unc:
                det["box_unc"] = float(box_unc[idx])
            detections.append(det)
            if len(detections) >= self.max_results:
                break

        return {
            "model_version": self.model_version,
            "model_type": self.model_type,
            "config_path": str(self.config_path),
            "checkpoint_path": str(self.checkpoint_path),
            "image_url": image_url,
            "score_thr": threshold,
            "num_detections": len(detections),
            "detections": detections,
        }

    def predict(self, request: DetectionPredictRequest) -> DetectionPredictResponse:
        raw = self.predict_raw(request.image_url)
        results = [
            DetectionResult(label=item["label_name"], bbox=item["bbox_xyxy"], score=item["score"])
            for item in raw["detections"]
        ]
        return DetectionPredictResponse(
            model_id=request.model_id,
            model_version=self.model_version,
            model_type=self.model_type,
            results=results,
        )

    def predict_to_file(self, request: DetectionPredictRequest, output_path: str | Path) -> Path:
        payload = self.predict_raw(request.image_url)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out


if __name__ == "__main__":
    service = DinoDetectionService()
    sample = service.root / "samples" / "dino_detection" / "sample_001.png"
    print(json.dumps(service.predict_raw(str(sample)), ensure_ascii=False, indent=2))
