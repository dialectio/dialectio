from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://dialectio:dialectio@127.0.0.1:5432/dialectio"
    cors_origins: list[str] = ["http://localhost:3000"]
    # Shared secret for the word editor; editing is disabled when empty.
    editor_token: str = ""
    # Signs control cards (app/api/gold.py); set a long random value in production
    secret_key: str = "dev-only-secret-change-me"
    # Generated files (e.g. TTS audio), served by the API under MEDIA_URL_PREFIX.
    media_dir: Path = REPO_DIR / "data" / "media"


settings = Settings()

MEDIA_DIR = settings.media_dir
MEDIA_URL_PREFIX = "/media"
