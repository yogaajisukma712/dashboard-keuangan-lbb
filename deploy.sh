#!/bin/bash
# =============================================================================
# deploy.sh — Redeploy LBB Super Smart Dashboard
# Jalankan: bash deploy.sh
#           bash deploy.sh "pesan commit"     → custom commit message
#           bash deploy.sh --no-push          → skip git push
#           bash deploy.sh --no-build         → restart container saja
# =============================================================================

set -euo pipefail

# ── Warna ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
info() { echo -e "${CYAN}  →${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }
err()  { echo -e "${RED}  ✗ ERROR:${RESET} $*" >&2; }
step() { echo -e "\n${BOLD}${CYAN}[$1]${RESET} $2"; }

# ── Argumen ───────────────────────────────────────────────────────────────────
COMMIT_MSG=""
DO_PUSH=true
DO_BUILD=true

for arg in "$@"; do
  case "$arg" in
    --no-push)  DO_PUSH=false ;;
    --no-build) DO_BUILD=false ;;
    --help|-h)
      echo "Penggunaan: bash deploy.sh [opsi] [\"pesan commit\"]"
      echo ""
      echo "  Opsi:"
      echo "    --no-push    Skip git add/commit/push"
      echo "    --no-build   Hanya restart container tanpa rebuild image"
      echo "    --help       Tampilkan bantuan ini"
      echo ""
      echo "  Contoh:"
      echo "    bash deploy.sh"
      echo "    bash deploy.sh \"fix: perbaikan form pembayaran\""
      echo "    bash deploy.sh --no-push"
      echo "    bash deploy.sh --no-build"
      exit 0
      ;;
    --*) warn "Opsi tidak dikenal: $arg (diabaikan)" ;;
    *)   COMMIT_MSG="$arg" ;;
  esac
done

# ── Deteksi direktori project ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
info "Direktori project: $SCRIPT_DIR"

# ── Nama container dan compose file ──────────────────────────────────────────
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
WEB_CONTAINER="billing_supersmart_web"

# Cek file yang diperlukan
for f in "$COMPOSE_FILE" "$ENV_FILE" "Dockerfile"; do
  if [ ! -f "$f" ]; then
    err "File $f tidak ditemukan di $SCRIPT_DIR"
    exit 1
  fi
done

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║   LBB Super Smart — Deploy Script                   ║${RESET}"
echo -e "${BOLD}${CYAN}║   billing.supersmart.click : port 6001               ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""

DEPLOY_START=$(date +%s)

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Sinkronisasi kode dari container ke disk (jika container running)
# ═════════════════════════════════════════════════════════════════════════════
step "1/6" "Sinkronisasi kode dari container ke disk"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${WEB_CONTAINER}$"; then
  info "Container $WEB_CONTAINER sedang berjalan — sync file yang diubah langsung di container..."

  SYNC_FILES=(
    "app/__init__.py"
    "app/routes/master.py"
    "app/routes/payroll.py"
    "app/routes/quota_invoice.py"
    "app/routes/__init__.py"
    "app/routes/attendance.py"
    "app/routes/auth.py"
    "app/routes/closings.py"
    "app/routes/dashboard.py"
    "app/routes/enrollments.py"
    "app/routes/expenses.py"
    "app/routes/incomes.py"
    "app/routes/payments.py"
    "app/routes/reports.py"
  )

  for f in "${SYNC_FILES[@]}"; do
    if docker exec "$WEB_CONTAINER" test -f "/app/$f" 2>/dev/null; then
      docker cp "${WEB_CONTAINER}:/app/${f}" "${f}" 2>/dev/null && info "sync: $f" || true
    fi
  done

  # Sync semua template
  docker cp "${WEB_CONTAINER}:/app/app/templates/" "app/" 2>/dev/null \
    && ok "Sync templates selesai" || warn "Gagal sync templates (lanjut...)"
else
  info "Container tidak berjalan — gunakan kode dari disk langsung"
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Git: add, commit, push
# ═════════════════════════════════════════════════════════════════════════════
step "2/6" "Git — commit & push ke GitHub"

if [ "$DO_PUSH" = false ]; then
  warn "Skip git push (--no-push)"
else
  # Cek apakah ini repo git
  if ! git rev-parse --git-dir > /dev/null 2>&1; then
    warn "Bukan repository git — skip git push"
    DO_PUSH=false
  else
    # Cek ada perubahan?
    if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
      ok "Tidak ada perubahan — skip commit"
    else
      # Buat pesan commit otomatis jika tidak diberikan
      if [ -z "$COMMIT_MSG" ]; then
        CHANGED_COUNT=$(git diff --name-only HEAD 2>/dev/null | wc -l | tr -d ' ')
        UNTRACKED_COUNT=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')
        TOTAL=$((CHANGED_COUNT + UNTRACKED_COUNT))
        TIMESTAMP=$(date '+%d/%m/%Y %H:%M')
        COMMIT_MSG="deploy: update ${TOTAL} file — ${TIMESTAMP}"
      fi

      info "Menambahkan semua perubahan ke staging..."
      git add -A

      info "Commit: $COMMIT_MSG"
      git commit -m "$COMMIT_MSG"

      info "Push ke GitHub..."
      if git push 2>&1; then
        ok "Push berhasil ke GitHub"
      else
        warn "Push gagal — lanjut deploy tanpa push"
      fi
    fi
  fi
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Stop container lama
# ═════════════════════════════════════════════════════════════════════════════
step "3/6" "Menghentikan container lama"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE "billing_supersmart"; then
  info "Menghentikan container billing_supersmart_*..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down 2>&1 | \
    grep -E "Removing|Removed|Stopping|Stopped|done|error" | \
    while read -r line; do info "$line"; done
  ok "Container dihentikan"
else
  ok "Tidak ada container yang berjalan"
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Build image baru
# ═════════════════════════════════════════════════════════════════════════════
step "4/6" "Build Docker image"

if [ "$DO_BUILD" = false ]; then
  warn "Skip build (--no-build) — gunakan image yang sudah ada"
else
  info "Memulai build... (mungkin 2-3 menit)"
  BUILD_START=$(date +%s)

  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache 2>&1 | \
      grep -E "Step|RUN|COPY|=>|error|Error|warning|FINISHED|Built" | \
      while read -r line; do echo -e "  ${CYAN}|${RESET} $line"; done; then
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))
    ok "Build selesai dalam ${BUILD_TIME}s"
  else
    err "Build GAGAL! Periksa error di atas."
    exit 1
  fi
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Jalankan container baru
# ═════════════════════════════════════════════════════════════════════════════
step "5/6" "Menjalankan container baru"

info "Starting services..."
if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d 2>&1 | \
    grep -E "Creating|Created|Starting|Started|healthy|error|Error" | \
    while read -r line; do info "$line"; done; then
  ok "Container berjalan"
else
  err "Gagal menjalankan container!"
  exit 1
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — Verifikasi
# ═════════════════════════════════════════════════════════════════════════════
step "6/6" "Verifikasi deployment"

info "Menunggu app siap (maks 45 detik)..."
MAX_WAIT=45
WAITED=0
APP_READY=false

while [ $WAITED -lt $MAX_WAIT ]; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:6001/auth/login 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    APP_READY=true
    break
  fi
  sleep 2
  WAITED=$((WAITED + 2))
  printf "  . "
done
echo ""

if [ "$APP_READY" = true ]; then
  ok "App merespons di http://localhost:6001 (HTTP 200)"
else
  warn "App belum merespons setelah ${MAX_WAIT}s — cek log di bawah"
fi

# Tampilkan status container
echo ""
echo -e "  ${BOLD}Status Container:${RESET}"
docker ps --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | \
  grep "billing_supersmart" | \
  while IFS=$'\t' read -r name status ports; do
    if echo "$status" | grep -q "Up"; then
      echo -e "  ${GREEN}●${RESET} $name — $status"
      echo -e "    ${CYAN}$ports${RESET}"
    else
      echo -e "  ${RED}●${RESET} $name — $status"
    fi
  done

# Tampilkan log terbaru (10 baris)
echo ""
echo -e "  ${BOLD}Log terbaru ($WEB_CONTAINER):${RESET}"
docker logs "$WEB_CONTAINER" --tail 10 2>&1 | \
  while read -r line; do echo "  $line"; done

# ── Summary ────────────────────────────────────────────────────────────────
DEPLOY_END=$(date +%s)
TOTAL_TIME=$((DEPLOY_END - DEPLOY_START))

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║   ✓ DEPLOY SELESAI dalam ${TOTAL_TIME}s${RESET}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${BOLD}${GREEN}║${RESET}   URL   : https://billing.supersmart.click"
echo -e "${BOLD}${GREEN}║${RESET}   Port  : http://localhost:6001"
echo -e "${BOLD}${GREEN}║${RESET}   Login : admin / admin123456"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
