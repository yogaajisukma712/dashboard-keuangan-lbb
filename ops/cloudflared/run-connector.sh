#!/usr/bin/env bash
set -Eeuo pipefail

connector_name="${1:-}"
[ -n "$connector_name" ] || {
  echo "Nama connector wajib diisi." >&2
  exit 2
}

token_file="/root/.config/lembaga/cloudflared-${connector_name}.token"
config_file="/etc/cloudflared/${connector_name}.yml"

[ -s "$token_file" ] || {
  echo "Token connector tidak ditemukan: ${token_file}" >&2
  exit 1
}

args=(tunnel --no-autoupdate)
if [ -f "$config_file" ]; then
  args+=(--config "$config_file")
fi
args+=(run --token-file "$token_file")

exec /usr/local/bin/cloudflared "${args[@]}"
