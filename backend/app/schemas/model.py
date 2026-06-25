from pydantic import BaseModel


class ModelInfoResponse(BaseModel):
    model_id: str
    model_name: str
    model_type: str
    model_version: str
    status: str
    description: str


class ModelListResponse(BaseModel):
    items: list[ModelInfoResponse]
