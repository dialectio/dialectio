# Dialectio

Web app: enter a word → see on a map how it is written, pronounced (IPA) and sounds in different languages and dialects.
Full plan and decisions: [docs/plan.md](docs/plan.md). Communicate with the user in Ukrainian.

## Layout
- `backend/` — FastAPI (Python 3.11+, managed with uv), SQLAlchemy + Alembic, PostgreSQL/PostGIS
- `frontend/` — Next.js (TypeScript) + MapLibre GL, i18n (uk, en)
- `backend/app/importers/` — import scripts for open data (run as `uv run python -m app.importers.<name>`); downloads go to git-ignored `data/raw/`
- `docs/` — plan and design notes

## Conventions
- Data is organized around `Concept` (meaning), not raw word strings.
- Varieties are identified by `Variety.code`: ISO 639-3 for languages, `<language>-<name>` for dialects (`ukr-hutsul`). Dialect territories are oblasts (`app/importers/dialects.py`); the map shows oblast labels instead of the country label from zoom 5.
- Every imported record must keep its `Source` (name, url, license).
- Synthetic (TTS) audio must be flagged `is_synthetic`.
- Forms have `status`: `approved` or `pending` (drafts from `app.importers.suggestions`, source "Dialectio suggestions (draft)"). Both are public (`PUBLIC_STATUSES`); drafts are marked unverified ("≈") until approved in the editor. Public queries must filter on `PUBLIC_STATUSES`.
- Visitors check words with anonymous votes (`vote`) and error reports (`report`), see `app/api/feedback.py`. Votes never change a word: enough yes-votes give the "👥 confirmed by speakers" mark (`community_status` in `app/models/feedback.py`), which stays below an editor's approval; editors see votes and reports in the editor ("Голоси й помилки").
- Word search matches `search_key(spelling)` (SQL function from the migrations: no accents via `unaccent`, Cyrillic romanized), so "Worterbuch" finds "Wörterbuch" and "kartoplia" finds "картопля"; the trigram index is on that expression
- Only one uvicorn may listen on port 8000: an orphaned old server keeps serving stale code. If changes don't show up, check `Get-NetTCPConnection -LocalPort 8000` and stop stray processes.
- Concept slugs (`/[locale]/word/[slug]`) are permanent once assigned (`app/slugs.py`); never recompute them, URLs are indexed by search engines.
- Use only free/open data sources and libraries; no Google Maps.
- UI strings live in `frontend/messages/{uk,en,pl,de,es,fr}.json` (the editor section stays English in pl/de/es/fr); names of concepts, languages and regions in pl/de/es/fr come from the JSON `names` / `glosses` / `descriptions` columns (`app/locales.py`), picked with `localized(locale, en, uk, names)` (next-intl); routes are prefixed with the locale (`/uk`, `/en`), default `uk`. Never hardcode UI text in components.
- Do not `git push` without discussing with the user first.

## Commands
- Start DB: `docker compose up -d db`
- The dev database listens on 127.0.0.1 only (its password is public); connect via `127.0.0.1`, not `localhost`: on Windows `localhost` tries IPv6 first and each connection waits ~30 s
- Analytics (optional): `docker compose --profile analytics up -d umami` → http://localhost:3001 (Umami, its own `umami` database); the site sends page views only when `NEXT_PUBLIC_UMAMI_SRC` and `NEXT_PUBLIC_UMAMI_WEBSITE_ID` are set in `frontend/.env.local`
- Backend (from `backend/`): `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`, `uv run ruff check .`
- Data import order (from `backend/`, all re-runnable): `natural_earth` (countries) → `natural_earth_admin1` (oblasts) → `wikidata_lexemes` → `descriptions` (our Ukrainian descriptions where Wikidata has none) → `glosses` (our concept names; they win over Wikidata labels, homonyms get a hint in brackets) → `wiktionary` (translation tables of the 5 000 most frequent English words from English Wiktionary via kaikki.org, ~3.3 GB download to `data/raw/wiktionary/`; run with `uv run --group import ...` so wordfreq can push rare translations back) → `dialects` → `localize` (names in the extra UI languages pl/de/es/fr: concept names from each language's main word, CLDR language names, Natural Earth region names, `data/dialect_names.json`; run last and after any import, `uv run --group import ...`) → `suggestions` / `suggestions --machine` → `tts`, each as `uv run python -m app.importers.<name>`; restart the API after region imports (vector tiles are cached in memory)
- Machine words (from `backend/`): `uv run python -m app.importers.suggestions --machine <iso> ...` loads `data/machine/<iso>.json`; real Wikidata data replaces them on the next import
- Word editor: `/uk/editor`, token = `EDITOR_TOKEN` in `.env`; editor words use source "Dialectio editors" and survive Wikidata re-imports
- Import words (from `backend/`, after countries): `uv run python -m app.importers.wikidata_lexemes` (~10 min, re-runnable); word lists and exclusions live in `backend/app/importers/data/`
- TTS (from `backend/`): `uv tool install piper-tts` once, then `uv run python -m app.importers.tts [iso ...]` after every Wikidata import and after approving words (only approved primary words without recordings get synthetic audio). Piper is GPL: run it only as an external program, never import it. Only voices whose license allows commercial use go into `VOICES`.
- Migrations (from `backend/`): `uv run alembic revision --autogenerate -m "..."`, `uv run alembic upgrade head`
- Frontend (from `frontend/`): `npm install`, `npm run dev`, `npm run lint`, `npm run build`
- `uvicorn --reload` on Windows sometimes misses file changes: if the API serves old code, restart it
- Production: `docker-compose.prod.yml` (db, backend, frontend, umami, Caddy) with `.env.prod`; full steps in [docs/deploy.md](docs/deploy.md). Pages that fetch the API outside a dynamic route call `await connection()` so `next build` (in Docker, without the API) does not prerender them
- Next.js 16 has breaking changes vs older versions: check `frontend/node_modules/next/dist/docs/` before writing frontend code.
