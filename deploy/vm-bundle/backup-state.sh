#!/usr/bin/env bash
# Backup state VM (volume WA) → file tar.gz lokal + opsional upload GitHub release.
# Output: /opt/apps/lembaga/vm-bundle/backups/vm-state-YYYYmmdd-HHMMSS.tar.gz
set -Eeuo pipefail
WORK=/opt/apps/lembaga/vm-bundle
OUT="$WORK/backups"
mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)

docker run --rm -v vm-bundle_whatsapp_bot_auth:/data:ro alpine tar czf - -C /data . > "$OUT/wa-auth-$TS.tar.gz"
docker run --rm -v vm-bundle_whatsapp_bot_backups:/data:ro alpine tar czf - -C /data . > "$OUT/wa-backups-$TS.tar.gz"

# Retensi 7 hari
find "$OUT" -name '*.tar.gz' -mtime +7 -delete

echo "[backup-state] selesai: $OUT/wa-auth-$TS.tar.gz"
