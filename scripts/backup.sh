#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${1:-"$ROOT_DIR/backups/$(date +%Y%m%d-%H%M%S)"}"

mkdir -p "$BACKUP_DIR"
cd "$ROOT_DIR"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > "$BACKUP_DIR/database.sql"
docker compose exec -T backend tar czf - -C /app/uploads . \
  > "$BACKUP_DIR/uploads.tar.gz"

printf 'Backup written to %s\n' "$BACKUP_DIR"
