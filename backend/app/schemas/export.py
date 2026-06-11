from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
