from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://santa:santa@localhost:5432/santa"
    app_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    email_backend: str = "console"
    email_from: str = "Secret Santa <santa@localhost>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    resend_api_key: str = ""

    rate_limit_group_create: int = 10
    rate_limit_email_send: int = 20
    rate_limit_link_preview: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
