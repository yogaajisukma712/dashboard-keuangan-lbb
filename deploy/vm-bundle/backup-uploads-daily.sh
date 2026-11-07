#!/bin/bash
# Backup volume bukti bayar WhatsApp -> GitHub Release.
# Non-destructive: mount read-only, tidak pernah prune/rm volume.
# Pakai: backup-uploads-daily.sh [tag]
#   tanpa arg -> tag lbb-proofs-daily-<YYYY-MM-DD> (WIB), aman dijalankan ulang
#   dengan arg -> tag dipakai apa adanya
set -uo pipefail

VOLUME="aplikasilembaga_whatsapp_bot_uploads"
REPO="yogaajisukma712/lembaga-db-backups"
WORK="/root/backup/proofs"
TOKEN_FILE="/root/.config/lembaga-backup/github-token"
TAG="${1:-lbb-proofs-daily-$(TZ=Asia/Jakarta date +%Y-%m-%d)}"
LOG_TAG="[$(date -Is)]"

log() { echo "$LOG_TAG $*"; }
die() { echo "$LOG_TAG ERROR: $*" >&2; exit 1; }

[ -r "$TOKEN_FILE" ] || die "token file tidak terbaca: $TOKEN_FILE"
TOKEN="$(tr -d ' \n\r' < "$TOKEN_FILE")"
[ -n "$TOKEN" ] || die "token kosong"
API="https://api.github.com"

mkdir -p "$WORK" || die "mkdir $WORK"
rm -rf "$WORK"/x "$WORK"/lbb-proofs.tar.gz "$WORK"/MANIFEST.csv "$WORK"/SHA256SUMS

# 1) tar isi volume (read-only)
docker run --rm -v "${VOLUME}:/data:ro" -v "${WORK}:/out" alpine \
  sh -c 'cd /data && tar czf /out/lbb-proofs.tar.gz .' || die "tar volume gagal"

# 2) manifest + sha256 (semua file, bukan hanya PNG)
mkdir -p "$WORK/x" && tar xzf "$WORK/lbb-proofs.tar.gz" -C "$WORK/x" || die "extract gagal"
{
  printf 'filename,size_bytes,sha256\n'
  find "$WORK/x" -type f | sort | while read -r f; do
    printf '%s,%s,%s\n' "${f#$WORK/x/}" "$(stat -c%s "$f")" "$(sha256sum "$f" | cut -d' ' -f1)"
  done
} > "$WORK/MANIFEST.csv"
( cd "$WORK/x" && find . -type f | sort | while read -r f; do printf '%s  %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "${f#./}"; done ) > "$WORK/SHA256SUMS"
N=$(find "$WORK/x" -type f | wc -l)
rm -rf "$WORK/x"
[ "$N" -gt 0 ] || die "volume kosong"
log "files=$N tar=$(stat -c%s "$WORK/lbb-proofs.tar.gz") bytes tag=$TAG"

# 3) release: buat baru, atau pakai existing (retry hari sama) + ganti asset lama
code=$(curl -s -o "$WORK/rel.json" -w '%{http_code}' -X POST "$API/repos/$REPO/releases" \
  -H "Authorization: Bearer $TOKEN" -H 'Accept: application/vnd.github+json' \
  -d "{\"tag_name\":\"$TAG\",\"name\":\"LBB Proofs Backup $TAG\",\"body\":\"Backup otomatis $N file dari volume $VOLUME.\"}")
if [ "$code" = "422" ]; then
  log "tag $TAG sudah ada, pakai release existing"
  curl -s -o "$WORK/rel.json" -H "Authorization: Bearer $TOKEN" -H 'Accept: application/vnd.github+json' \
    "$API/repos/$REPO/releases/tags/$TAG" || die "ambil release gagal"
  RID=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["id"])' "$WORK/rel.json" 2>/dev/null)
  for name in lbb-proofs.tar.gz MANIFEST.csv SHA256SUMS; do
    AID=$(curl -s -H "Authorization: Bearer $TOKEN" "$API/repos/$REPO/releases/$RID/assets" \
      | python3 -c 'import json,sys;n=sys.argv[1];print(next((a["id"] for a in json.load(sys.stdin) if a["name"]==n),""))' "$name" 2>/dev/null)
    [ -n "$AID" ] && curl -s -o /dev/null -X DELETE -H "Authorization: Bearer $TOKEN" "$API/repos/$REPO/releases/assets/$AID"
  done
elif [ "$code" != "201" ]; then
  die "buat release gagal HTTP $code"
else
  log "release $TAG dibuat"
fi
RID=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["id"])' "$WORK/rel.json") || die "parse release gagal"

# 4) upload 3 asset
for f in lbb-proofs.tar.gz MANIFEST.csv SHA256SUMS; do
  up=$(curl -s -o "$WORK/up.json" -w '%{http_code}' -X POST \
    "https://uploads.github.com/repos/$REPO/releases/$RID/assets?name=$f" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/octet-stream' \
    --data-binary "@$WORK/$f")
  [ "$up" = "201" ] || die "upload $f gagal HTTP $up"
  log "uploaded $f"
done

# 5) verifikasi
curl -s -H "Authorization: Bearer $TOKEN" "$API/repos/$REPO/releases/$RID/assets" \
  | python3 -c 'import json,sys;[print("asset:",a["name"],a["size"]) for a in json.load(sys.stdin)]'
log "SELESAI https://github.com/$REPO/releases/tag/$TAG"
