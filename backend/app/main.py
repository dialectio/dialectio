from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api import (
    accounts,
    community,
    contribute,
    dialect_words,
    dialects,
    editor,
    false_friends,
    feedback,
    gold,
    lexicon,
    regions,
    stats,
)
from app.config import MEDIA_DIR, MEDIA_URL_PREFIX, settings
from app.db.session import engine

app = FastAPI(title="Dialectio API", version="0.1.0")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount(MEDIA_URL_PREFIX, StaticFiles(directory=MEDIA_DIR), name="media")
app.include_router(regions.router)
app.include_router(lexicon.router)
app.include_router(editor.router)
app.include_router(contribute.router)
app.include_router(stats.router)
app.include_router(dialects.router)
app.include_router(dialect_words.router)
app.include_router(feedback.router)
app.include_router(gold.router)
app.include_router(accounts.router)
app.include_router(false_friends.router)
app.include_router(community.router)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # the session cookie of signed-in members
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    """For uptime monitoring: also checks that the database answers."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "database unavailable"}
    return {"status": "ok"}
