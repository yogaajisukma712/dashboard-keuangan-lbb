#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

APP_DIR="${APP_DIR:-/opt/apps/lembaga/aplikasi-lembaga}"
BACKUP_DIR="${BACKUP_DIR:-}"
ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-aplikasilembaga}"
FORCE_RESTORE="${FORCE_RESTORE:-false}"
RESTORE_DATABASE="${RESTORE_DATABASE:-true}"
RESTORE_WHATSAPP="${RESTORE_WHATSAPP:-true}"
DB_CONTAINER="${DB_CONTAINER:-billing_supersmart_db}"

log() {
  printf '[restore] %s\n' "$*"
}

die() {
  printf '[restore][ERROR] %s\n' "$*" >&2
  exit 1
}

compose() {
  env COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" \
    docker compose --env-file "$ENV_FILE" "$@"
}

wait_for_database() {
  local health=""
  for _ in $(seq 1 60); do
    health="$(docker inspect "$DB_CONTAINER" \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      2>/dev/null || true)"
    [ "$health" = "healthy" ] && return 0
    sleep 2
  done
  die "Database tidak healthy; status=${health:-missing}"
}

restore_database() {
  local database_archive="$1"
  local table_count extracted_sql create_table_count

  table_count="$(docker exec "$DB_CONTAINER" psql -U postgres -d lbb_db -Atqc \
    "select count(*) from information_schema.tables where table_schema='public'")"
  if [ "${table_count:-0}" != "0" ]; then
    [ "$FORCE_RESTORE" = "true" ] || \
      die "Database sudah berisi ${table_count} tabel. Set FORCE_RESTORE=true untuk menimpa."
    log "Membuat ulang lbb_db sebelum restore."
    docker exec "$DB_CONTAINER" dropdb -U postgres --force --if-exists lbb_db
    docker exec "$DB_CONTAINER" createdb -U postgres -O postgres lbb_db
  fi

  extracted_sql="$(mktemp --tmpdir lbb-db-only.XXXXXX.sql.gz)"
  gzip -dc "$database_archive" |
    awk '
      /^\\connect lbb_db$/ { capture = 1 }
      /^DROP DATABASE postgres;$/ { capture = 0 }
      capture { print }
    ' |
    gzip -9 >"$extracted_sql"

  gzip -t "$extracted_sql"
  create_table_count="$(gzip -dc "$extracted_sql" | grep -c '^CREATE TABLE' || true)"
  [ "$create_table_count" -gt 0 ] || die "Bagian lbb_db tidak ditemukan dalam dump."

  log "Restore lbb_db (${create_table_count} definisi tabel)."
  gzip -dc "$extracted_sql" |
    docker exec -i "$DB_CONTAINER" \
      psql -v ON_ERROR_STOP=1 -U postgres -d postgres
  rm -f "$extracted_sql"
}

restore_whatsapp() {
  local whatsapp_archive="$1"
  local auth_volume backup_volume auth_entries archive_name

  auth_volume="${COMPOSE_PROJECT_NAME}_whatsapp_bot_auth"
  backup_volume="${COMPOSE_PROJECT_NAME}_whatsapp_bot_backups"
  archive_name="$(basename "$whatsapp_archive")"

  docker stop billing_supersmart_whatsapp_bot >/dev/null 2>&1 || true
  docker volume create "$auth_volume" >/dev/null
  docker volume create "$backup_volume" >/dev/null

  auth_entries="$(docker run --rm -v "$auth_volume:/data" alpine \
    sh -c "find /data -mindepth 1 -maxdepth 1 | wc -l")"
  if [ "${auth_entries:-0}" != "0" ]; then
    [ "$FORCE_RESTORE" = "true" ] || \
      die "Volume WhatsApp auth tidak kosong. Set FORCE_RESTORE=true untuk menimpa."
    docker run --rm -v "$auth_volume:/data" alpine \
      sh -c "find /data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +"
  fi

  log "Restore sesi WhatsApp ke volume ${auth_volume}."
  docker run --rm \
    -v "$auth_volume:/restore" \
    -v "$BACKUP_DIR:/backup:ro" \
    alpine tar -xzf "/backup/${archive_name}" -C /restore

  docker run --rm \
    -v "$backup_volume:/restore" \
    -v "$BACKUP_DIR:/backup:ro" \
    alpine cp "/backup/${archive_name}" "/restore/${archive_name}"
}

main() {
  local database_archive whatsapp_archive tables auth_files

  [ -n "$BACKUP_DIR" ] || die "BACKUP_DIR wajib diisi."
  [ -d "$APP_DIR" ] || die "Direktori aplikasi tidak ditemukan: $APP_DIR"
  [ -d "$BACKUP_DIR" ] || die "Direktori backup tidak ditemukan: $BACKUP_DIR"

  database_archive="$(find "$BACKUP_DIR" -maxdepth 1 \
    -name 'postgres-cluster-*.sql.gz' -print -quit)"
  whatsapp_archive="$(find "$BACKUP_DIR" -maxdepth 1 \
    -name 'wa-session-*.tar.gz' -print -quit)"
  [ -f "$database_archive" ] || die "Arsip database hasil dekripsi tidak ditemukan."
  [ -f "$whatsapp_archive" ] || die "Arsip WhatsApp hasil dekripsi tidak ditemukan."

  cd "$APP_DIR"
  compose config --quiet
  compose up -d db >/dev/null
  wait_for_database

  if [ "$RESTORE_DATABASE" = "true" ]; then
    restore_database "$database_archive"
  else
    log "Restore database dilewati."
  fi

  if [ "$RESTORE_WHATSAPP" = "true" ]; then
    restore_whatsapp "$whatsapp_archive"
  else
    log "Restore WhatsApp dilewati."
  fi

  tables="$(docker exec "$DB_CONTAINER" psql -U postgres -d lbb_db -Atqc \
    "select count(*) from information_schema.tables where table_schema='public'")"
  auth_files="$(docker run --rm \
    -v "${COMPOSE_PROJECT_NAME}_whatsapp_bot_auth:/data:ro" \
    alpine sh -c "find /data -type f | wc -l")"

  log "Selesai. tables=${tables}; whatsapp_auth_files=${auth_files}"
  log "Service web/bot belum dinyalakan oleh skrip ini."
}

main "$@"
