#!/bin/sh
# Load a database dump (made with pg_dump -Fc) into the production database.
#   deploy/restore-db.sh dialectio.dump
# PostGIS extensions already exist in the image's database, so "already exists" notices
# about them are expected and harmless.
set -eu
cd "$(dirname "$0")/.."
set -a; . ./.env.prod; set +a
DUMP=$1
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
$COMPOSE exec -T db pg_restore -U "${POSTGRES_USER:-dialectio}" -d "${POSTGRES_DB:-dialectio}" \
  --clean --if-exists --no-owner < "$DUMP" || true
$COMPOSE exec -T db psql -U "${POSTGRES_USER:-dialectio}" -d "${POSTGRES_DB:-dialectio}" \
  -c "SELECT count(*) AS forms FROM form"
