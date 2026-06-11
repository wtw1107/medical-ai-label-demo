from fastapi import FastAPI

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

settings = get_settings()

app = FastAPI(
    title="Medical AI Label Demo Backend",
    version="0.1.0",
    description="Backend skeleton for the local medical image AI-assisted labeling demo.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    # Keep startup lightweight; create tables only for the foundation phase.
    Base.metadata.create_all(bind=engine)
