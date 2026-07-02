from fastapi import APIRouter

from app.core.model_registry import list_models
from app.schemas.model import ModelInfoResponse, ModelListResponse

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=ModelListResponse)
def get_models() -> ModelListResponse:
    items = [
        ModelInfoResponse(
            model_id=model.model_id,
            model_name=model.model_name,
            model_type=model.model_type,
            model_version=model.model_version,
            status=model.status,
            description=model.description,
            deployment_type=model.deployment_type,
            provider=model.provider,
            task_types=list(model.task_types) or None,
            anatomy=list(model.anatomy) or None,
            modality=list(model.modality) or None,
            outputs=list(model.outputs) or None,
            requires=model.requires,
            runtime=model.runtime,
            metrics=model.metrics,
            limitations=list(model.limitations) or None,
        )
        for model in list_models()
    ]
    return ModelListResponse(items=items)
