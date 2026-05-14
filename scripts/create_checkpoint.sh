#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/apps/lembaga/aplikasi-lembaga}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/apps/lembaga/checkpoints}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-aplikasilembaga}"
DB_CONTAINER="${DB_CONTAINER:-billing_supersmart_db}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-lbb_db}"
LABEL="${1:-manual}"

timestamp="$(date +%Y%m%d-%H%M%S)"
safe_label="$(printf '%s' "$LABEL" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-//; s/-$//')"
checkpoint_dir="$BACKUP_ROOT/${timestamp}-${safe_label:-manual}"

mkdir -p "$checkpoint_dir"

{
  echo "checkpoint=$timestamp"
  echo "label=$LABEL"
  echo "app_dir=$APP_DIR"
  echo "host=$(hostname)"
  echo "created_at=$(date -Is)"
} > "$checkpoint_dir/MANIFEST.txt"

if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" rev-parse HEAD > "$checkpoint_dir/git-head.txt" || true
  git -C "$APP_DIR" status --short > "$checkpoint_dir/git-status.txt" || true
  git -C "$APP_DIR" log -1 --oneline > "$checkpoint_dir/git-last-commit.txt" || true
fi

docker ps --format '{{.Names}} {{.Image}} {{.Status}}' > "$checkpoint_dir/docker-ps.txt" || true
docker compose -p "$COMPOSE_PROJECT" -f "$APP_DIR/docker-compose.yml" ps > "$checkpoint_dir/docker-compose-ps.txt" || true

docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc \
  > "$checkpoint_dir/${DB_NAME}.dump"

if [ -d "$APP_DIR/uploads" ]; then
  tar -C "$APP_DIR" -czf "$checkpoint_dir/uploads.tgz" uploads
fi

if [ -d "$APP_DIR/whatsapp-bot" ]; then
  tar -C "$APP_DIR" \
    --exclude='whatsapp-bot/node_modules' \
    --exclude='whatsapp-bot/.wwebjs_cache' \
    -czf "$checkpoint_dir/whatsapp-bot-data.tgz" whatsapp-bot
fi

if [ -d "$APP_DIR/state" ]; then
  tar -C "$APP_DIR" -czf "$checkpoint_dir/state.tgz" state
fi

find "$checkpoint_dir" -maxdepth 1 -type f -printf '%f %s bytes\n' \
  | sort > "$checkpoint_dir/files.txt"

echo "$checkpoint_dir"
