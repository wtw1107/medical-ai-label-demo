from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.task import (
    AnnotationTaskCreate,
    AnnotationTaskCreateResponse,
    AnnotationTaskDetailResponse,
    AnnotationTaskListResponse,
    AnnotationTaskUrlResponse,
)
from app.services.label_studio_service import LabelStudioService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=AnnotationTaskListResponse)
def list_annotation_tasks(
    db: Session = Depends(get_db),
) -> AnnotationTaskListResponse:
    settings = get_settings()
    service = LabelStudioService(settings)
    return service.list_annotation_tasks(db=db)


@router.post("", response_model=AnnotationTaskCreateResponse)
def create_annotation_task(
    payload: AnnotationTaskCreate,
    db: Session = Depends(get_db),
) -> AnnotationTaskCreateResponse:
    settings = get_settings()
    service = LabelStudioService(settings)
    return service.create_annotation_task(db=db, payload=payload)


@router.get("/{task_id}/label-studio-url", response_model=AnnotationTaskUrlResponse)
def get_label_studio_url(
    task_id: str,
    db: Session = Depends(get_db),
) -> AnnotationTaskUrlResponse:
    settings = get_settings()
    service = LabelStudioService(settings)
    return service.get_label_studio_url(db=db, task_id=task_id)


@router.get("/{task_id}", response_model=AnnotationTaskDetailResponse)
def get_annotation_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> AnnotationTaskDetailResponse:
    settings = get_settings()
    service = LabelStudioService(settings)
    return service.get_annotation_task(db=db, task_id=task_id)
