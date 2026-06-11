from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.core.config import Settings


class ModelServiceClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.model_service_url.rstrip("/")

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.post(url, json=payload, timeout=30.0, trust_env=False)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=503,
                detail="Could not connect to model_service. Please make sure it is running.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"model_service request failed: {exc.response.text}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"model_service request failed: {exc}") from exc

        body = response.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=502, detail="model_service returned an invalid response payload.")
        return body

    def predict_detection(
        self,
        *,
        image_url: str,
        image_id: str,
        model_id: str,
    ) -> dict[str, object]:
        return self._post(
            "/predict/detection",
            {
                "image_url": image_url,
                "image_id": image_id,
                "model_id": model_id,
            },
        )

    def predict_segmentation(
        self,
        *,
        image_url: str,
        image_id: str,
        model_id: str,
        bbox_prompt: list[int] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "image_url": image_url,
            "image_id": image_id,
            "model_id": model_id,
        }
        if bbox_prompt is not None:
            payload["prompts"] = {"bbox": bbox_prompt}
        return self._post("/predict/segmentation", payload)
