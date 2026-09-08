#!/usr/bin/env bash
# Backup state VM (WA session volume + uploads + env) -> GitHub Release.
set -Eeuo pipefail
WORK="${VM_BUNDLE_WORK:-/opt/apps/lembaga/vm-bundle}"
OUT="$WORK/backups"
TS=$(date -u +%Y%m%d-%H%M%S)
TAG="vm-state-$TS"
REPO="${BACKUP_REPO:-yogaajisukma712/lembaga-db-backups}"
GH_FILE="${GH_TOKEN_FILE:-/root/.config/lembaga/github-token}"
mkdir -p "$OUT"
GH=$(cat "$GH_FILE")
API="https://api.github.com/repos/$REPO"

echo "[vm-backup] tar volumes..."
docker run --rm -v vm-bundle_whatsapp_bot_auth:/data:ro alpine tar czf - -C /data . > "$OUT/wa-auth.tar.gz"
docker run --rm -v vm-bundle_uploads:/data:ro alpine tar czf - -C /data . > "$OUT/uploads.tar.gz" 2>/dev/null || true
cp -f "$WORK/env" "$OUT/env.txt" 2>/dev/null || true

BUNDLE="$OUT/$TAG.tar.gz"
tar czf "$BUNDLE" -C "$OUT" wa-auth.tar.gz uploads.tar.gz env.txt 2>/dev/null || tar czf "$BUNDLE" -C "$OUT" wa-auth.tar.gz env.txt

echo "[vm-backup] create release $TAG..."
CREATE=$(curl -s -X POST "$API/releases" -H "Authorization: Bearer $GH" -H "Content-Type: application/json" \
  -d "{\"tag_name\":\"$TAG\",\"name\":\"VM state $TS\"}")
REL_ID=$(echo "$CREATE" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true)
if [ -n "$REL_ID" ]; then
  curl -s -X POST "$API/releases/$REL_ID/assets?name=vm-state.tar.gz" \
    -H "Authorization: Bearer $GH" -H "Content-Type: application/gzip" \
    --data-binary "@$BUNDLE" > /dev/null && echo "[vm-backup] asset terunggah."
else
  echo "[vm-backup] GAGAL buat release:"; echo "$CREATE" | head -c 200
fi

# retensi lokal 7 hari
find "$OUT" -name 'vm-state-*.tar.gz' -mtime +7 -delete 2>/dev/null || true
rm -f "$OUT/wa-auth.tar.gz" "$OUT/uploads.tar.gz" "$OUT/env.txt" 2>/dev/null || true
echo "[vm-backup] selesai."
