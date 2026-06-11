from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PrelabelJobBase(BaseModel):
    task_id: str


class PrelabelJobCreate(PrelabelJobBase):
    pass


class PrelabelJobRead(PrelabelJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    pending_confirm: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
