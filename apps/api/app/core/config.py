from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./lernyra.db"
    api_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    remotive_enabled: bool = True
    upload_dir: str = "uploads"
    youtube_api_key: str = ""
    google_books_api_key: str = ""
    github_token: str = ""
    public_site_url: str = "https://getbeacon.duckdns.org"
    google_site_verification: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def site_url(self) -> str:
        return self.public_site_url.rstrip("/")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
