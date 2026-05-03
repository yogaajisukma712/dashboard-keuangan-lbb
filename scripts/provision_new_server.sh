#!/usr/bin/env bash
set -Eeuo pipefail

# Provision/migration script for LBB Super Smart billing app on a fresh server.
#
# Usage on the new server:
#   bash scripts/provision_new_server.sh
#
# Or run without an existing checkout:
#   REPO_URL=https://github.com/yogaajisukma712/dashboard-keuangan-lbb.git \
#   APP_DIR=/opt/billing-supersmart \
#   bash provision_new_server.sh
#
# Optional restore inputs:
#   DB_BACKUP=/path/to/postgres.sql        # or .sql.gz
#   UPLOADS_ARCHIVE=/path/to/uploads.tgz
#   WHATSAPP_AUTH_ARCHIVE=/path/to/wa.tgz
#   FORCE_RESTORE=true                    # required if DB is not empty
#
# Optional app settings:
#   APP_BASE_URL=https://billing.example.com
#   POSTGRES_PORT=5433
#   CREATE_ADMIN=true                     # runs create_admin.py after boot

REPO_URL="${REPO_URL:-https://github.com/yogaajisukma712/dashboard-keuangan-lbb.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-$HOME/apps/billing-supersmart}"
ENV_FILE="${ENV_FILE:-.env.docker}"
OVERRIDE_FILE="${OVERRIDE_FILE:-docker-compose.server.override.yml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-billing_supersmart}"
APP_BASE_URL="${APP_BASE_URL:-https://billing.supersmart.click}"
POSTGRES_PORT="${POSTGRES_PORT:-5433}"
CREATE_ADMIN="${CREATE_ADMIN:-false}"
DB_BACKUP="${DB_BACKUP:-}"
UPLOADS_ARCHIVE="${UPLOADS_ARCHIVE:-}"
WHATSAPP_AUTH_ARCHIVE="${WHATSAPP_AUTH_ARCHIVE:-}"
FORCE_RESTORE="${FORCE_RESTORE:-false}"

log() {
  printf '[provision] %s\n' "$*"
}

die() {
  printf '[provision][ERROR] %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Command '$1' belum tersedia."
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  else
    die "Butuh openssl atau python3 untuk membuat secret."
  fi
}

env_get() {
  local key="$1"
  local fallback="${2:-}"
  if [ ! -f "$ENV_FILE" ]; then
    printf '%s' "$fallback"
    return
  fi
  local line
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
  if [ -z "$line" ]; then
    printf '%s' "$fallback"
    return
  fi
  line="${line#*=}"
  line="${line%\"}"
  line="${line#\"}"
  line="${line%\'}"
  line="${line#\'}"
  printf '%s' "$line"
}

env_set_if_missing_or_placeholder() {
  local key="$1"
  local value="$2"
  local current
  current="$(env_get "$key" "")"
  if [ -z "$current" ]; then
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    return
  fi
  case "$current" in
    change-this-*|ganti-*|postgres|admin123456)
      sed -i.bak -E "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
      ;;
  esac
}

compose() {
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" \
    docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" "$@"
}

wait_for_db() {
  log "Menunggu PostgreSQL sehat..."
  for _ in $(seq 1 90); do
    local status
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' billing_supersmart_db 2>/dev/null || true)"
    if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
      log "Database siap."
      return
    fi
    sleep 2
  done
  compose ps
  die "Database belum siap setelah timeout."
}

restore_archive() {
  local archive="$1"
  local target_dir="$2"
  local label="$3"
  [ -z "$archive" ] && return
  [ -f "$archive" ] || die "$label archive tidak ditemukan: $archive"
  log "Restore $label ke $target_dir"
  mkdir -p "$target_dir"
  tar -xzf "$archive" -C "$target_dir"
}

restore_database_if_requested() {
  [ -z "$DB_BACKUP" ] && return
  [ -f "$DB_BACKUP" ] || die "DB_BACKUP tidak ditemukan: $DB_BACKUP"

  local pg_user pg_db table_count
  pg_user="$(env_get POSTGRES_USER postgres)"
  pg_db="$(env_get POSTGRES_DB lbb_db)"
  table_count="$(compose exec -T db psql -U "$pg_user" -d "$pg_db" -tAc "select count(*) from information_schema.tables where table_schema='public';" | tr -d '[:space:]')"

  if [ "${table_count:-0}" != "0" ] && [ "$FORCE_RESTORE" != "true" ]; then
    die "Database tidak kosong (${table_count} tabel). Set FORCE_RESTORE=true jika yakin ingin restore ke DB ini."
  fi

  log "Restore database dari $DB_BACKUP"
  if [[ "$DB_BACKUP" = *.gz ]]; then
    gzip -dc "$DB_BACKUP" | compose exec -T db psql -U "$pg_user" -d "$pg_db"
  else
    compose exec -T db psql -U "$pg_user" -d "$pg_db" < "$DB_BACKUP"
  fi
}

smoke_check() {
  log "Smoke check HTTP aplikasi..."
  if ! command -v python3 >/dev/null 2>&1; then
    log "python3 tidak tersedia, skip smoke check HTTP."
    return
  fi
  python3 - <<'PY'
import os
import sys
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

base = os.environ.get("APP_BASE_URL_FOR_SMOKE", "http://127.0.0.1:6001").rstrip("/")
paths = ["/auth/login", "/master/students"]
for _ in range(30):
    ok = True
    results = []
    for path in paths:
        try:
            with urlopen(base + path, timeout=5) as response:
                results.append((path, response.status))
        except HTTPError as exc:
            results.append((path, exc.code))
        except URLError:
            ok = False
            break
    if ok:
        print("[provision] Smoke:", ", ".join(f"{p}={s}" for p, s in results))
        sys.exit(0)
    time.sleep(2)
print("[provision][WARN] Smoke check belum berhasil. Cek docker compose logs web.")
PY
}

main() {
  need_cmd git
  need_cmd docker
  docker compose version >/dev/null 2>&1 || die "Docker Compose plugin belum tersedia."

  if [ -d "$APP_DIR/.git" ]; then
    log "Repo sudah ada. Pull update: $APP_DIR"
    cd "$APP_DIR"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git pull --ff-only origin "$BRANCH"
  else
    if [ -e "$APP_DIR" ] && [ "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)" != "0" ]; then
      die "APP_DIR sudah ada dan tidak kosong: $APP_DIR"
    fi
    log "Clone repo $REPO_URL branch $BRANCH ke $APP_DIR"
    mkdir -p "$(dirname "$APP_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
  fi

  log "Siapkan folder mount dan backup."
  mkdir -p logs uploads backups whatsapp-auth deploy
  chmod 775 logs uploads backups whatsapp-auth deploy || true

  if [ ! -f "$ENV_FILE" ]; then
    if [ -f .env.docker.example ]; then
      cp .env.docker.example "$ENV_FILE"
    elif [ -f .env.example ]; then
      cp .env.example "$ENV_FILE"
    else
      touch "$ENV_FILE"
    fi
    log "Membuat $ENV_FILE dari template."
  else
    log "$ENV_FILE sudah ada, hanya melengkapi key yang kosong/placeholder."
  fi

  env_set_if_missing_or_placeholder SECRET_KEY "$(random_secret)"
  env_set_if_missing_or_placeholder POSTGRES_DB "lbb_db"
  env_set_if_missing_or_placeholder POSTGRES_USER "postgres"
  env_set_if_missing_or_placeholder POSTGRES_PASSWORD "$(random_secret)"
  env_set_if_missing_or_placeholder POSTGRES_PORT "$POSTGRES_PORT"
  env_set_if_missing_or_placeholder WHATSAPP_BOT_TOKEN "$(random_secret)"
  env_set_if_missing_or_placeholder WWEBJS_CLIENT_ID "billing-supersmart"
  env_set_if_missing_or_placeholder WHATSAPP_EXCLUDED_GROUP_NAMES "VPS / RDP MURAH III"
  env_set_if_missing_or_placeholder APP_BASE_URL "$APP_BASE_URL"
  env_set_if_missing_or_placeholder PAGINATION_PER_PAGE "20"
  env_set_if_missing_or_placeholder GUNICORN_WORKERS "4"
  env_set_if_missing_or_placeholder LOG_LEVEL "INFO"

  cat > "$OVERRIDE_FILE" <<'YAML'
# Generated by scripts/provision_new_server.sh.
# Purpose: keep runtime data outside images so migration/rebuild is safe.
services:
  web:
    volumes:
      - ./logs:/app/logs
      - ./uploads:/app/uploads
  whatsapp_bot:
    volumes:
      - ./whatsapp-auth:/app/.wwebjs_auth
YAML

  restore_archive "$UPLOADS_ARCHIVE" uploads "uploads"
  restore_archive "$WHATSAPP_AUTH_ARCHIVE" whatsapp-auth "WhatsApp auth"

  log "Build image dan start database."
  compose build --pull
  compose up -d db
  wait_for_db
  restore_database_if_requested

  log "Start semua service."
  compose up -d
  compose ps

  APP_BASE_URL_FOR_SMOKE="http://127.0.0.1:6001" smoke_check

  if [ "$CREATE_ADMIN" = "true" ]; then
    log "Membuat admin pertama via create_admin.py. Segera ganti password setelah login."
    compose exec -T web python create_admin.py || true
  fi

  cat <<EOF

[provision] Selesai.

Folder penting:
  Repo aplikasi     : $APP_DIR
  Env produksi      : $APP_DIR/$ENV_FILE
  Logs              : $APP_DIR/logs
  Uploads           : $APP_DIR/uploads
  WhatsApp session  : $APP_DIR/whatsapp-auth
  Backup lokal      : $APP_DIR/backups
  DB volume Docker  : ${COMPOSE_PROJECT_NAME}_billing_postgres_data

Perintah operasional:
  cd "$APP_DIR"
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" ps
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" logs -f web
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" logs -f whatsapp_bot

Catatan:
  - Jangan jalankan 'docker compose down -v' kecuali siap menghapus database.
  - Backup DB lama bisa direstore dengan DB_BACKUP=/path/file.sql.gz FORCE_RESTORE=true.
  - Backup upload/WA session bisa direstore dengan UPLOADS_ARCHIVE dan WHATSAPP_AUTH_ARCHIVE.
EOF
}

main "$@"
