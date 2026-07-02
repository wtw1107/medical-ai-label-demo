from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.export import ExportRequest, ExportResponse, ExportStatusResponse
from app.services.export_service import ExportService

router = APIRouter(prefix="/api", tags=["exports"])


@router.post("/tasks/{task_id}/exports", response_model=ExportResponse)
def create_export(
    task_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
) -> ExportResponse:
    service = ExportService(get_settings())
    return service.create_export(db=db, task_id=task_id, payload=payload)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    service = ExportService(get_settings())
    path = service.get_download_path(db=db, export_id=export_id)
    return FileResponse(path, media_type="application/zip", filename=path.name)


@router.get("/exports/{export_id}", response_model=ExportStatusResponse)
def get_export_status(
    export_id: str,
    db: Session = Depends(get_db),
) -> ExportStatusResponse:
    service = ExportService(get_settings())
    return service.get_export_status(db=db, export_id=export_id)
