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
    # Session cookies only over HTTPS (true in production)
    cookie_secure: bool = False
    # Public addresses: the API (Google returns here) and the site (members land back here)
    api_url: str = "http://localhost:8000"
    site_url: str = "http://localhost:3000"
    # "Sign in with Google" (OAuth client of the Google Cloud project); off when empty
    google_client_id: str = ""
    google_client_secret: str = ""
    # Email (Brevo transactional API); without a key, emails are written to the log
    brevo_api_key: str = ""
    mail_from: str = "noreply@dialectio.org"
    # Where the weekly report goes (python -m app.report)
    report_to: str = "dialectio.team@gmail.com"
    # Write emails to the log even with a key (local testing with made-up addresses)
    mail_to_log: bool = False
    # Cloudflare Turnstile ("are you human?") on sign-up, emailed links and contributions;
    # off when empty
    turnstile_secret: str = ""
    # Generated files (e.g. TTS audio), served by the API under MEDIA_URL_PREFIX.
    media_dir: Path = REPO_DIR / "data" / "media"


settings = Settings()

MEDIA_DIR = settings.media_dir
MEDIA_URL_PREFIX = "/media"
