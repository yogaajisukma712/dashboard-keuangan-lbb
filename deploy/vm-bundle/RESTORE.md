# Runbook: VM Bot Mati / Migrasi VM Baru

## Prasyarat yang harus tersedia SEBELUM mati (disimpan di luar VM)
1. **Image**: `ghcr.io/yogaajisukma712/lbb-whatsapp-bot:latest` (GHCR, public/private per repo setting)
2. **Backup state**: `/opt/apps/lembaga/vm-bundle/backups/wa-auth-*.tar.gz` (backup harian 04:30, retensi 7 hari) — **copy berkala ke luar VM** (mis. GitHub release repo `lembaga-db-backups`) atau lokasi aman lain. Ini kunci tanpa-QR-ulang.
3. **File**: `.env` (WHATSPAPP_FLASK_BASE_URL, WHATSAPP_BOT_TOKEN, DATABASE_URL), token tunnel `cloudflared-supersmart-wa.token`
4. Cloudflare dashboard: DNS `wa.supersmart.click` → tunnel `supersmart-wa` (statis, tak berubah saat ganti VM)

## Langkah pemulihan (< 15 menit)
1. Buat VM Ubuntu 22.04+ root, min 2 vCPU/2GB (SGP disarankan).
2. Upload 3 file: `.env`, token tunnel, `wa-auth-*.tar.gz` terbaru.
3. Jalankan:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/yogaajisukma712/dashboard-keuangan-lbb/main/deploy/vm-bundle/install.sh -o install.sh
   bash install.sh --env-file ./env --tunnel-token-file ./wa.token --backup-tar ./wa-auth-TERBARU.tar.gz
   ```
4. Verifikasi:
   - `https://wa.supersmart.click/health` → 200
   - `https://wa.supersmart.click/session` → `authenticated:true` (tanpa QR; jika QR diminta, sesi ter-unlink sejak backup — scan ulang sekali)
5. Job `heavy_jobs` status `pending` otomatis diproses worker baru (polling).

## Catatan
- VM mati → dampak HANYA: bot offline + job berat menunda. Dashboard (Vercel) + DB (Neon) tak tersentuh.
- Cloudflare tunnel connector lama otomatis tergantikan connector baru (token sama, hostname sama).
- `install.sh` idempoten — aman diulang di VM sama.
