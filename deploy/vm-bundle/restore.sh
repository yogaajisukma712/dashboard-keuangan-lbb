#!/usr/bin/env bash
# RESTORE INSTAN - pulihkan WA bot di VM BARU dari backup GitHub release.
# Pemakaian (root di VM baru):
#   bash restore.sh --github-token ghp_xxx --tunnel-token-file ./wa.token [--release TAG]
set -Eeuo pipefail
GH_TOKEN="" REPO="yogaajisukma712/lembaga-db-backups" RELEASE="" TUNNEL_TOKEN_FILE="" WORKDIR="/opt/apps/lembaga/vm-bundle"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --github-token) GH_TOKEN="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --release) RELEASE="$2"; shift 2;;
    --tunnel-token-file) TUNNEL_TOKEN_FILE="$2"; shift 2;;
    *) echo "arg tak dikenal: $1" >&2; exit 2;;
  esac
done
[ -n "$GH_TOKEN" ] || { echo "butuh --github-token"; exit 2; }
[ -n "$TUNNEL_TOKEN_FILE" ] || { echo "butuh --tunnel-token-file"; exit 2; }
API=https://api.github.com/repos/$REPO
AUTH="Authorization: Bearer $GH_TOKEN"
echo "[restore] cari release..."
[ -z "$RELEASE" ] && RELEASE=$(curl -sf -H "$AUTH" "$API/releases/latest" | python3 -c "import sys,json;print(json.load(sys.stdin)['tag_name'])")
echo "[restore] release: $RELEASE"
mkdir -p "$WORKDIR" && cd "$WORKDIR"
curl -sfL -H "$AUTH" -o bundle.tar.gz "$API/releases/download/$RELEASE/$RELEASE.tar.gz"
tar xzf bundle.tar.gz -C "$WORKDIR"
ls env-*.txt >/dev/null 2>&1 && cp -f $(ls env-*.txt | head -1) env
curl -fsSL -o install.sh https://raw.githubusercontent.com/yogaajisukma712/dashboard-keuangan-lbb/main/deploy/vm-bundle/install.sh
chmod +x install.sh
echo "[restore] ekstrak volume WA session..."
WA_TAR=$(ls wa-auth-*.tar.gz | head -1)
bash install.sh --env-file ./env --tunnel-token-file "$TUNNEL_TOKEN_FILE" --backup-tar "./$WA_TAR"
echo "[restore] SELESAI. Cek: https://wa.supersmart.click/health"
echo "[restore] Jika sesi invalid (backup tua) -> scan QR sekali di app /whatsapp/management."
