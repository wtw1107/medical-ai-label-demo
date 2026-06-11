from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ExportFormat, ExportRange


class ExportRecordBase(BaseModel):
    task_id: str
    format: str
    range: str
    created_by: str


class ExportRecordCreate(ExportRecordBase):
    pass


class ExportRecordRead(ExportRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    file_path: str | None = None
    download_url: str | None = None
    total_count: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExportRequest(BaseModel):
    format: str = Field(default=ExportFormat.SIMPLE_JSON.value)
    range: str = Field(default=ExportRange.CONFIRMED_ONLY.value)


class ExportResponse(BaseModel):
    export_id: str
    task_id: str
    format: str
    status: str
    file_path: str
    download_url: str
