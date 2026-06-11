from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.dataset import DatasetUploadResponse
from app.services.storage_service import upload_dataset

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
)
def upload_dataset_endpoint(
    name: str = Form(...),
    description: str | None = Form(default=None),
    created_by: str | None = Form(default=None),
    files: list[UploadFile] = File(
        ...,
        json_schema_extra={"items": {"type": "string", "format": "binary"}},
    ),
    db: Session = Depends(get_db),
) -> DatasetUploadResponse:
    settings = get_settings()
    return upload_dataset(
        db=db,
        name=name,
        description=description,
        created_by=created_by or settings.default_user_id,
        settings=settings,
        files=files,
    )
