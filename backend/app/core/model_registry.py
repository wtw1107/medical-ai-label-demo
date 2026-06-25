from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.core.constants import TaskType


@dataclass(frozen=True)
class ModelRegistryItem:
    model_id: str
    model_name: str
    model_type: str
    model_version: str
    status: str
    description: str


MODEL_REGISTRY: dict[str, ModelRegistryItem] = {
    "mock_detection": ModelRegistryItem(
        model_id="mock_detection",
        model_name="Mock Detection Model",
        model_type="detection",
        model_version="mock-v1",
        status="available",
        description="本地 mock 检测模型，用于演示 bbox 预标注流程。",
    ),
    "mock_segmentation": ModelRegistryItem(
        model_id="mock_segmentation",
        model_name="Mock Segmentation Model",
        model_type="segmentation",
        model_version="mock-v1",
        status="available",
        description="本地 mock 分割模型，用于演示 polygon 预标注流程。",
    ),
    "real_detection_v1": ModelRegistryItem(
        model_id="real_detection_v1",
        model_name="Real Detection Model v1",
        model_type="detection",
        model_version="v1.0",
        status="not_configured",
        description="真实检测模型占位配置，后续接入。",
    ),
    "real_segmentation_v1": ModelRegistryItem(
        model_id="real_segmentation_v1",
        model_name="Real Segmentation Model v1",
        model_type="segmentation",
        model_version="v1.0",
        status="not_configured",
        description="真实分割模型占位配置，后续接入。",
    ),
}


def list_models() -> list[ModelRegistryItem]:
    return list(MODEL_REGISTRY.values())


def get_model(model_id: str) -> ModelRegistryItem | None:
    return MODEL_REGISTRY.get(model_id)


def get_default_model_id(task_type: str, model_type: str) -> str:
    if task_type == TaskType.BBOX.value:
        if model_type == "detection":
            return "mock_detection"
    elif task_type == TaskType.POLYGON.value:
        if model_type == "segmentation":
            return "mock_segmentation"
    elif task_type == TaskType.BBOX_POLYGON.value:
        if model_type == "detection":
            return "mock_detection"
        if model_type == "segmentation":
            return "mock_segmentation"
    raise ValueError(f"Unsupported task_type/model_type combination: {task_type}/{model_type}")


def require_model(model_id: str, expected_model_type: str) -> ModelRegistryItem:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=400, detail=f"Unknown model_id: {model_id}")
    if model.model_type != expected_model_type:
        raise HTTPException(
            status_code=400,
            detail=f"Model {model_id} is not a {expected_model_type} model.",
        )
    if model.status != "available":
        raise HTTPException(
            status_code=400,
            detail=f"Model {model_id} is not configured yet. Please choose an available model.",
        )
    return model
