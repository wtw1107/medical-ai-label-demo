from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import TaskType


class AnnotationTaskBase(BaseModel):
    dataset_id: str
    name: str
    task_type: str = Field(default=TaskType.BBOX.value)
    label_name: str
    det_model_id: str | None = None
    seg_model_id: str | None = None
    require_human_confirm: bool = True


class AnnotationTaskCreate(AnnotationTaskBase):
    pass


class AnnotationTaskRead(AnnotationTaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label_studio_project_id: int | None = None
    status: str
    error_message: str | None = None
