from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import contribute, dialect_words, dialects, editor, feedback, lexicon, regions, stats
from app.config import MEDIA_DIR, MEDIA_URL_PREFIX, settings

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

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
