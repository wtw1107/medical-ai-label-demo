from functools import lru_cache
from pathlib import Path
from re import match

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import TaskType


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    database_url: str = Field(default="sqlite:///./data/demo.db", alias="DATABASE_URL")
    data_root: Path = Field(default=Path("./data"), alias="DATA_ROOT")
    media_base_url: str = Field(default="http://localhost:8000/media", alias="MEDIA_BASE_URL")
    label_studio_url: str = Field(default="http://localhost:8080", alias="LABEL_STUDIO_URL")
    label_studio_api_token: str = Field(default="", alias="LABEL_STUDIO_API_TOKEN")
    model_service_url: str = Field(default="http://localhost:9000", alias="MODEL_SERVICE_URL")
    default_user_id: str = Field(default="local_demo_user", alias="DEFAULT_USER_ID")
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])

    def ensure_data_root(self) -> Path:
        if not self.data_root.is_absolute():
            self.data_root = (self.project_root / self.data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        return self.data_root

    def get_database_url(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.removeprefix("sqlite:///")
            if raw_path and not raw_path.startswith("/") and not match(r"^[A-Za-z]:", raw_path):
                resolved_path = (self.project_root / raw_path).resolve()
                return f"sqlite:///{resolved_path.as_posix()}"
        return self.database_url

    def get_label_config_path(self, task_type: str) -> Path:
        config_dir = self.project_root / "configs" / "label_configs"
        mapping = {
            TaskType.BBOX.value: config_dir / "bbox.xml",
            TaskType.POLYGON.value: config_dir / "polygon.xml",
            TaskType.BBOX_POLYGON.value: config_dir / "bbox_polygon.xml",
        }
        try:
            return mapping[task_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported task_type: {task_type}") from exc


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_data_root()
    return settings
