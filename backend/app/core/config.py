from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    def ensure_data_root(self) -> Path:
        self.data_root.mkdir(parents=True, exist_ok=True)
        return self.data_root


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_data_root()
    return settings
