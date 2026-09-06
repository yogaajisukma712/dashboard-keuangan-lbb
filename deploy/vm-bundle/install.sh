#!/usr/bin/env bash
# LBB VM Bundle — one-liner install/redploy WA bot + scheduler + heavy-jobs worker
# Prasyarat: VM Ubuntu 22.04/24.04 root, 2GB+ RAM.
# Sumber: image prebuilt GHCR (tanpa build chromium) + state dari release backup.
#
# Pemakaian:
#   bash install.sh --env-file /path/env --tunnel-token-file /path/token --backup-tar /path/wa-auth.tar.gz
# Semua state persist di docker volume; idempoten (aman dijalankan ulang).
set -Eeuo pipefail

ENV_FILE="" TUNNEL_TOKEN_FILE="" BACKUP_TAR="" BACKUP_TARS_TAR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2;;
    --tunnel-token-file) TUNNEL_TOKEN_FILE="$2"; shift 2;;
    --backup-tar) BACKUP_TAR="$2"; shift 2;;          # tar whatsapp_bot_auth
    --backup-tars-tar) BACKUP_TARS_TAR="$2"; shift 2;; # tar whatsapp_bot_backups
    *) echo "arg tak dikenal: $1" >&2; exit 2;;
  esac
done

log(){ echo "[vm-bundle] $*"; }
die(){ echo "[vm-bundle] FATAL: $*" >&2; exit 1; }

[[ -n "$ENV_FILE" && -n "$TUNNEL_TOKEN_FILE" ]] || die "butuh --env-file dan --tunnel-token-file"

# 1. Docker (idempoten)
if ! command -v docker >/dev/null; then
  log "installing docker..."
  curl -fsSL https://get.docker.com | sh >/dev/null 2>&1 || die "docker install gagal"
fi
docker compose version >/dev/null 2>&1 || die "compose plugin tidak ada"

# 2. Direktori kerja
WORK=/opt/apps/lembaga/vm-bundle
mkdir -p "$WORK"
cd "$WORK"
cp -f "$(readlink -f "$ENV_FILE")" .env 2>/dev/null || cp "$ENV_FILE" .env

# 3. Pull compose unit
if [[ ! -f docker-compose.vm.yml ]]; then
  log "unduh compose unit..."
  curl -fsSL -o docker-compose.vm.yml \
    https://raw.githubusercontent.com/yogaajisukma712/dashboard-keuangan-lbb/main/deploy/vm-bundle/docker-compose.vm.yml \
    || die "gagal unduh compose"
fi

# 4. Restore volume sesi WA (TANPA QR ulang) — hanya jika tar disertakan
if [[ -n "$BACKUP_TAR" ]]; then
  log "restore volume whatsapp_bot_auth..."
  docker volume create vm-bundle_whatsapp_bot_auth >/dev/null
  docker run --rm -i -v vm-bundle_whatsapp_bot_auth:/data alpine sh -c 'cd /data && tar xzf -' < "$BACKUP_TAR" || die "restore auth gagal"
fi
if [[ -n "$BACKUP_TARS_TAR" ]]; then
  log "restore volume whatsapp_bot_backups..."
  docker volume create vm-bundle_whatsapp_bot_backups >/dev/null
  docker run --rm -i -v vm-bundle_whatsapp_bot_backups:/data alpine sh -c 'cd /data && tar xzf -' < "$BACKUP_TARS_TAR" || die "restore backups gagal"
fi

# 5. Pull image & up
log "pull image GHCR..."
docker compose --project-name vm-bundle -f docker-compose.vm.yml pull
log "starting bot + worker..."
docker compose --project-name vm-bundle -f docker-compose.vm.yml up -d

# 6. cloudflared tunnel (wa.supersmart.click -> localhost:6002)
if ! command -v cloudflared >/dev/null; then
  log "install cloudflared..."
  curl -fsSL -o /usr/local/bin/cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$(dpkg --print-architecture)"
  chmod 0755 /usr/local/bin/cloudflared
fi
mkdir -p /etc/cloudflared /root/.config/lembaga
cp -f "$(readlink -f "$TUNNEL_TOKEN_FILE")" /root/.config/lembaga/cloudflared-supersmart-wa.token
chmod 0600 /root/.config/lembaga/cloudflared-supersmart-wa.token

cat > /usr/local/sbin/cloudflared-lembaga-run <<'WRAP'
#!/usr/bin/env bash
set -Eeuo pipefail
connector_name="${1:-}"
[ -n "$connector_name" ] || { echo "Nama connector wajib diisi." >&2; exit 2; }
token_file="/root/.config/lembaga/cloudflared-${connector_name}.token"
config_file="/etc/cloudflared/${connector_name}.yml"
[ -s "$token_file" ] || { echo "Token tidak ditemukan: ${token_file}" >&2; exit 1; }
args=(tunnel --no-autoupdate)
if [ -f "$config_file" ]; then args+=(--config "$config_file"); fi
args+=(run --token-file "$token_file")
exec /usr/local/bin/cloudflared "${args[@]}"
WRAP
chmod 0755 /usr/local/sbin/cloudflared-lembaga-run

cat > /etc/systemd/system/cloudflared-lembaga@.service <<'UNIT'
[Unit]
Description=Cloudflare Tunnel connector for %i
Wants=network-online.target
After=network-online.target docker.service
[Service]
Type=simple
User=root
ExecStart=/usr/local/sbin/cloudflared-lembaga-run %i
Restart=always
RestartSec=5s
[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now cloudflared-lembaga@supersmart-wa

# 7. Firewall: hanya SSH (bot + tunnel = outbound)
command -v ufw >/dev/null && { ufw allow 22/tcp >/dev/null 2>&1 || true; ufw --force enable >/dev/null 2>&1 || true; }

# 8. Smoke test
sleep 12
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://localhost:6002/health || echo 000)
[[ "$CODE" == "200" ]] && log "bot /health 200 OK" || log "PERINGATAN: /health = $CODE (cek: docker logs billing_supersmart_whatsapp_bot)"

log "SELESAI — cek https://wa.supersmart.click/health (propagasi ~1mnt)"
