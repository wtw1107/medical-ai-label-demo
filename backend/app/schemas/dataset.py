from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import DataType


class DatasetBase(BaseModel):
    name: str
    description: str | None = None
    data_type: str = Field(default=DataType.IMAGE.value)
    root_dir: str
    created_by: str


class DatasetCreate(DatasetBase):
    pass


class DatasetRead(DatasetBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    image_count: int
    status: str


class ImageItemBase(BaseModel):
    dataset_id: str
    filename: str
    file_path: str
    file_url: str
    width: int | None = None
    height: int | None = None


class ImageItemCreate(ImageItemBase):
    pass


class ImageItemRead(ImageItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    error_message: str | None = None


class UploadWarning(BaseModel):
    filename: str
    message: str


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    image_count: int
    images: list[ImageItemRead]
    warnings: list[UploadWarning] = Field(default_factory=list)
