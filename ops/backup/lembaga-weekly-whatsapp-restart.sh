#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

readonly BOT_CONTAINER="billing_supersmart_whatsapp_bot"
readonly BOT_SESSION_URL="http://127.0.0.1:6002/session"
readonly BACKUP_ROOT="/root/daily-backups/lembaga"
readonly MAX_BACKUP_AGE_SECONDS=7200
readonly HEALTH_TIMEOUT_SECONDS=300
readonly LOCK_FILE="/run/lock/lembaga-weekly-whatsapp-restart.lock"

check_only=false
if [[ "${1:-}" == "--check-only" ]]; then
  check_only=true
elif [[ $# -gt 0 ]]; then
  echo "Argumen tidak dikenal: $1" >&2
  exit 2
fi

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Restart mingguan lain masih berjalan; keluar."
  exit 0
fi

for command in docker python3 sha256sum stat; do
  command -v "${command}" >/dev/null || {
    echo "Perintah wajib tidak tersedia: ${command}" >&2
    exit 1
  }
done

latest_backup="$({
  find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d \
    -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-
} || true)"

if [[ -z "${latest_backup}" || ! -f "${latest_backup}/SHA256SUMS" ]]; then
  echo "Restart dibatalkan: backup harian terbaru tidak tersedia." >&2
  exit 1
fi

backup_age=$(( $(date +%s) - $(stat -c %Y "${latest_backup}/SHA256SUMS") ))
if (( backup_age < 0 || backup_age > MAX_BACKUP_AGE_SECONDS )); then
  echo "Restart dibatalkan: backup terbaru berumur ${backup_age} detik." >&2
  exit 1
fi

echo "[1/4] Verifikasi checksum backup terbaru"
(
  cd "${latest_backup}"
  sha256sum -c SHA256SUMS >/dev/null
)

session_ready() {
  python3 - "${BOT_SESSION_URL}" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=10) as response:
    payload = json.load(response)

session = payload.get("session", {})
if not (
    payload.get("ok")
    and session.get("status") == "ready"
    and session.get("authenticated") is True
    and session.get("ready") is True
):
    raise SystemExit(1)
PY
}

if [[ "$(docker inspect "${BOT_CONTAINER}" --format '{{.State.Health.Status}}')" != "healthy" ]] \
  || ! session_ready; then
  echo "Restart dibatalkan: bot belum healthy/ready sebelum pemeliharaan." >&2
  exit 1
fi

if [[ "${check_only}" == true ]]; then
  echo "Pemeriksaan aman lulus; restart tidak dijalankan."
  exit 0
fi

echo "[2/4] Restart container WhatsApp"
docker restart --time 30 "${BOT_CONTAINER}" >/dev/null

echo "[3/4] Tunggu container dan sesi kembali siap"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT_SECONDS ))
while (( $(date +%s) < deadline )); do
  health="$(docker inspect "${BOT_CONTAINER}" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' 2>/dev/null || true)"
  if [[ "${health}" == "healthy" ]] && session_ready; then
    echo "[4/4] Restart selesai; container healthy dan sesi ready."
    exit 0
  fi
  sleep 5
done

health="$(docker inspect "${BOT_CONTAINER}" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' 2>/dev/null || echo missing)"
echo "Restart gagal diverifikasi dalam ${HEALTH_TIMEOUT_SECONDS} detik; health=${health}." >&2
exit 1
