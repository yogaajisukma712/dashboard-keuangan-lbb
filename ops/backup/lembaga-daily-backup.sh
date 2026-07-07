#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

readonly REPOSITORY="yogaajisukma712/lembaga-db-backups"
readonly BOT_CONTAINER="billing_supersmart_whatsapp_bot"
readonly DB_CONTAINER="billing_supersmart_db"
readonly BOT_BACKUP_URL="http://127.0.0.1:6002/session/backup"
readonly CONFIG_DIR="/root/.config/lembaga-backup"
readonly PASSPHRASE_FILE="${CONFIG_DIR}/passphrase"
readonly GITHUB_TOKEN_FILE="${CONFIG_DIR}/github-token"
readonly BACKUP_ROOT="/root/daily-backups/lembaga"
readonly LOCK_FILE="/run/lock/lembaga-daily-backup.lock"
readonly GITHUB_RETENTION=14
readonly LOCAL_RETENTION_DAYS=3
readonly BOT_LOCAL_RETENTION=3

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Backup lain masih berjalan; keluar."
  exit 0
fi

for command in docker gh openssl gzip sha256sum python3; do
  command -v "${command}" >/dev/null || {
    echo "Perintah wajib tidak tersedia: ${command}" >&2
    exit 1
  }
done

for secret_file in "${PASSPHRASE_FILE}" "${GITHUB_TOKEN_FILE}"; do
  if [[ ! -s "${secret_file}" ]]; then
    echo "Secret tidak tersedia: ${secret_file}" >&2
    exit 1
  fi
done

export GH_TOKEN
GH_TOKEN="$(<"${GITHUB_TOKEN_FILE}")"

stamp="$(TZ=Asia/Jakarta date +'%Y%m%d-%H%M%S-WIB')"
created_at="$(TZ=Asia/Jakarta date --iso-8601=seconds)"
tag="daily-${stamp}"
work_dir="${BACKUP_ROOT}/${stamp}"
mkdir -p "${work_dir}"

echo "[1/6] Membuat backup sesi WhatsApp resmi"
session_filename="$({ python3 - "${BOT_BACKUP_URL}" <<'PY'
import json
import sys
import urllib.request

request = urllib.request.Request(
    sys.argv[1],
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=1800) as response:
    payload = json.load(response)

filename = payload.get("backup", {}).get("filename")
if not payload.get("ok") or not filename:
    raise SystemExit("Bot tidak mengembalikan nama backup yang valid")
print(filename)
PY
} 2>&1)" || {
  echo "Pembuatan backup sesi gagal: ${session_filename}" >&2
  exit 1
}

if [[ "${session_filename}" != "$(basename -- "${session_filename}")" ]] \
  || [[ "${session_filename}" != wa-session-*.tar.gz ]]; then
  echo "Nama backup sesi tidak valid." >&2
  exit 1
fi

session_plain="${work_dir}/${session_filename}"
docker cp "${BOT_CONTAINER}:/app/.wwebjs_backups/${session_filename}" "${session_plain}" >/dev/null
gzip -t "${session_plain}"

echo "[2/6] Dump seluruh cluster PostgreSQL"
database_plain="${work_dir}/postgres-cluster-${stamp}.sql.gz"
docker exec "${DB_CONTAINER}" sh -lc \
  'pg_dumpall --clean --if-exists -U "$POSTGRES_USER"' | gzip -9 >"${database_plain}"
gzip -t "${database_plain}"

echo "[3/6] Enkripsi AES-256-CBC"
session_encrypted="${session_plain}.enc"
database_encrypted="${database_plain}.enc"
for source_file in "${session_plain}" "${database_plain}"; do
  openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
    -in "${source_file}" -out "${source_file}.enc" \
    -pass "file:${PASSPHRASE_FILE}"
  rm -f -- "${source_file}"
done

manifest="${work_dir}/MANIFEST.txt"
cat >"${manifest}" <<EOF
Backup Aplikasi Lembaga
Created: ${created_at}
GitHub tag: ${tag}
WhatsApp source: ${BOT_CONTAINER}:/app/.wwebjs_backups/${session_filename}
Database source: ${DB_CONTAINER} (all databases and globals via pg_dumpall)
Encryption: OpenSSL AES-256-CBC, PBKDF2, 200000 iterations
Passphrase handoff: dashboard-keuangan-lbb/docs/backups/secrets/database-backup-passphrase-20260707-133509-WIB.txt
Restore handoff: dashboard-keuangan-lbb/docs/backups/daily-github-backup.md
EOF

checksums="${work_dir}/SHA256SUMS"
(
  cd "${work_dir}"
  sha256sum "$(basename -- "${session_encrypted}")" \
    "$(basename -- "${database_encrypted}")" MANIFEST.txt >SHA256SUMS
)

echo "[4/6] Unggah aset terenkripsi ke GitHub Releases"
gh release create "${tag}" \
  --repo "${REPOSITORY}" \
  --target main \
  --title "Backup harian ${stamp}" \
  --notes-file "${manifest}" \
  "${session_encrypted}" "${database_encrypted}" "${manifest}" "${checksums}"

asset_count="$(gh release view "${tag}" --repo "${REPOSITORY}" \
  --json assets --jq '.assets | length')"
if [[ "${asset_count}" -ne 4 ]]; then
  echo "Verifikasi GitHub gagal: jumlah aset ${asset_count}, seharusnya 4." >&2
  exit 1
fi

echo "[5/6] Terapkan retensi"
mapfile -t expired_tags < <(
  gh release list --repo "${REPOSITORY}" --limit 100 \
    --json tagName,createdAt \
    --jq "map(select(.tagName | startswith(\"daily-\"))) | sort_by(.createdAt) | reverse | .[${GITHUB_RETENTION}:][] | .tagName"
)
for expired_tag in "${expired_tags[@]}"; do
  gh release delete "${expired_tag}" --repo "${REPOSITORY}" --cleanup-tag --yes
done

find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d \
  -mtime "+${LOCAL_RETENTION_DAYS}" -exec rm -rf -- {} +

docker exec "${BOT_CONTAINER}" sh -lc \
  "find /app/.wwebjs_backups -maxdepth 1 -type f -name 'wa-session-*.tar.gz' -printf '%T@ %p\\n' | sort -nr | tail -n +$((BOT_LOCAL_RETENTION + 1)) | cut -d' ' -f2- | xargs -r rm -f --"

echo "[6/6] Backup selesai: ${tag}; aset=${asset_count}"
