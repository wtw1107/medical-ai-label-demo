from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.prelabel import (
    LabelStudioStatusSyncResponse,
    PredictionPreviewResponse,
    PrelabelJobStatusResponse,
    PrelabelRunResponse,
    TaskImageStatusResponse,
)
from app.services.prelabel_service import PrelabelService

router = APIRouter(prefix="/api", tags=["prelabel"])


@router.post("/tasks/{task_id}/prelabel", response_model=PrelabelRunResponse)
def run_prelabel(
    task_id: str,
    db: Session = Depends(get_db),
) -> PrelabelRunResponse:
    service = PrelabelService(get_settings())
    return service.run_prelabel(db=db, task_id=task_id)


@router.get("/prelabel-jobs/{job_id}", response_model=PrelabelJobStatusResponse)
def get_prelabel_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> PrelabelJobStatusResponse:
    service = PrelabelService(get_settings())
    return service.get_prelabel_job(db=db, job_id=job_id)


@router.get("/tasks/{task_id}/images", response_model=TaskImageStatusResponse)
def list_task_images(
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskImageStatusResponse:
    service = PrelabelService(get_settings())
    return service.list_task_images(db=db, task_id=task_id)


@router.post("/tasks/{task_id}/sync-label-studio-status", response_model=LabelStudioStatusSyncResponse)
def sync_label_studio_status(
    task_id: str,
    db: Session = Depends(get_db),
) -> LabelStudioStatusSyncResponse:
    service = PrelabelService(get_settings())
    return service.sync_label_studio_status(db=db, task_id=task_id)


@router.get("/tasks/{task_id}/images/{image_id}/prediction-preview", response_model=PredictionPreviewResponse)
def get_prediction_preview(
    task_id: str,
    image_id: str,
    db: Session = Depends(get_db),
) -> PredictionPreviewResponse:
    service = PrelabelService(get_settings())
    return service.get_prediction_preview(db=db, task_id=task_id, image_id=image_id)
