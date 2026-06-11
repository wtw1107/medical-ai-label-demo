from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.routers.datasets import router as datasets_router
from app.routers.tasks import router as tasks_router
from app.services.label_studio_service import ensure_annotation_task_schema

settings = get_settings()

app = FastAPI(
    title="Medical AI Label Demo Backend",
    version="0.1.0",
    description="Backend skeleton for the local medical image AI-assisted labeling demo.",
)

app.mount("/media", StaticFiles(directory=str(settings.data_root)), name="media")
app.include_router(datasets_router)
app.include_router(tasks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    # Keep startup lightweight; create tables only for the foundation phase.
    Base.metadata.create_all(bind=engine)
    ensure_annotation_task_schema()
