#!/bin/sh
# Daily backup on the server (cron): database dumps and media, kept for 14 days.
#   0 3 * * * /srv/dialectio/deploy/backup.sh >> /srv/dialectio/backups/backup.log 2>&1
set -eu
cd "$(dirname "$0")/.."
set -a; . ./.env.prod; set +a
BACKUPS=backups
STAMP=$(date +%Y-%m-%d)
mkdir -p "$BACKUPS"
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
for db in dialectio umami; do
  $COMPOSE exec -T db pg_dump -U "${POSTGRES_USER:-dialectio}" -Fc "$db" > "$BACKUPS/$db-$STAMP.dump"
done
tar -czf "$BACKUPS/media-$STAMP.tar.gz" data/media
find "$BACKUPS" -name '*.dump' -mtime +14 -delete
find "$BACKUPS" -name 'media-*.tar.gz' -mtime +14 -delete
echo "$(date -Is) backup done"
