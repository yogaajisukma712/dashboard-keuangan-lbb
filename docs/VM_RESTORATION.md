# VM Bot - Handoff & Restorasi Instan (untuk AI agent / admin berikutnya)

> 2026-09-07. Baca ini SEBELUM menyentuh infrastruktur VM/deploy.

## Arsitektur aktif

- Dashboard: Vercel (sin1) - project `lbb-dashboard`, domain `*.supersmart.click`
- DB: Neon SGP project `green-morning-40964370` (sumber data tunggal, PITR 7 hari)
- WA bot: container di DO#1 `152.42.246.93` (image GHCR `lbb-whatsapp-bot:latest`,
  volume: sesi WA + backups + uploads). Satu-satunya bot; VPS#2 & AWS sudah off.
- File upload (bukti payroll, file tutor): disimpan di volume bot DO#1 via
  `PUT /files/*` (auth `X-Bot-Token`). Vercel `VERCEL=1` mengaktifkan
  `app/services/remote_storage.py` yang mengalihkan semua `file.save()`.
- Bulk kirim slip: dashboard INSERT job Neon `heavy_jobs` -> worker bot polling
  30 dtk -> kirim per-slip via `/payroll/api/fee-slip-job/<ref>` (token, exempt CSRF).
- Heartbeat: bot POST `/api/system/heartbeat` tiap 5 menit (auth token);
  badge status VM di `/whatsapp/management` (aktif / stale >180 detik).
- Versi dashboard: file `VERSION` (regenerate tiap deploy) tampil di sidebar.

## Kunci-kunci (lokal, gitignored)

- `api key penting/` : vercel.key, neon.key, neon-pooled-conn.txt, neon-direct-conn.txt, github-token.key
- `.server_lembaga` (repo root): ringkasan akses server
- DO#1: `/opt/apps/lembaga/aplikasi-lembaga/.env` (SECRET_KEY, token bot,
  DATABASE_URL_NEON) + `/etc/cloudflared` & `/root/.config/lembaga/` (tunnel WA)

## VM & Failover (status 2026-09-08)

| VM | IP | Peran | Status |
|---|---|---|---|
| VPS#2 | 139.59.99.242 | WA bot aktif (vm-bundle) + Caddy wa-direct + tunnel supersmart-wa | RUNNING |
| VPS#3 | 206.189.34.41 (bancet712) | STANDBY failover — docker + vm-bundle siap, env/wa.token/GH token ter-copy, image GHCR sudah di-pull, ufw SSH-only | STANDBY |
| DO#1 | 152.42.246.93 | MATI (unreachable) — asal sesi WA lama | OFF |
| Helipod | 156.67.24.112 (SSH port 45500, root) | STANDBY #2 — docker + image bot ter-pull + env/wa.token/GH token + backup script siap. Spek: 4 vCPU/4GB/765GB. Akses: `ssh -p 45500 root@156.67.24.112` (key terpasang). Token API: `api key penting/token helipod.key` | STANDBY |

Failover VPS#2 mati -> VPS#3 (menit):
1. SSH root@206.189.34.41 (SSH key terpasang).
2. cd /opt/apps/lembaga/vm-bundle
   bash backup-state.sh 2>/dev/null || true   # backup terakhir dari VPS2 sudah di GitHub release
   bash restore.sh --github-token <ghp_...> --tunnel-token-file ./wa.token
3. wa.supersmart.click + wa-direct (Caddy) otomatis pindah — tunnel token sama.
4. DNS wa-direct -> 206.189.34.41 via Cloudflare API (token di .server_lembaga) bila pakai jalur direct.

Failover ke Helipod: sama seperti prosedur VPS#3 — SSH port 45500, restore.sh + wa.token sudah ada di
/opt/apps/lembaga/vm-bundle. Pembeda: billing harian Helipod (bayar sesuai pemakaian), akses SSH pakai port 45500.

Catatan: backup harian berjalan di VM AKTIF (Sekarang VPS#2). Setelah failover,
install.sh + timer vm-bundle-backup otomatis terpasang di VM baru.

## Restorasi VM mati -> VM baru (<=15 menit)

1. VM Ubuntu 22.04+ (2 vCPU/2GB+, SGP), login root.
2. Dua file: token tunnel Cloudflare (`wa.token`: tunnel `supersmart-wa`,
   hostname `wa.supersmart.click` -> `localhost:6002`) + GitHub token.
3. Satu perintah:
   curl -fsSL -o restore.sh https://raw.githubusercontent.com/yogaajisukma712/dashboard-keuangan-lbb/main/deploy/vm-bundle/restore.sh
   bash restore.sh --github-token <ghp_...> --tunnel-token-file ./wa.token
   Otomatis: unduh backup state terakhir (GitHub release `vm-state-*` di
   `lembaga-db-backups`) -> docker+image GHCR -> restore volume sesi WA ->
   bot+tunnel jalan -> health check.
4. Verifikasi: `https://wa.supersmart.click/health` 200; badge **VM Bot Aktif**
   di `/whatsapp/management`.
5. Sesi invalid (backup tua) -> scan QR sekali di halaman manajemen.

## Backup rutin (otomatis)

- Systemd `vm-bundle-backup.timer` di DO#1: harian 04:30 WIB -> `backup-state.sh`
  -> tar (sesi WA + uploads + env) -> GitHub release `vm-state-YYYYMMDD`
  di repo `yogaajisukma712/lembaga-db-backups` (token di
  `/root/.config/lembaga/github-token`). DB tidak ikut backup VM (sudah di Neon).

## Deploy dashboard (update versi otomatis)

bash scripts/deploy-vercel.sh
Regenerate `VERSION` (semver+tanggal+commit) -> staging rsync -> deploy. Label
versi tampil di sidebar dashboard.

## Perangkap yang sudah pernah terjadi (JANGAN diulang)

1. Build image bot di VM gagal (mirror Debian bullseye 404) -> SELALU image GHCR;
   build bertingkat dari image lama bila perlu.
2. PATCH env Vercel tidak berlaku ke deployment lama -> deploy ulang setelah ubah env.
3. Deploy dari folder tanpa `.vercel/project.json` membuat project liar
   (`vercel-deploy`) -> staging wajib link ke `lbb-dashboard`.
4. SSO/password protection menutup domain vercel.app -> sudah `ssoProtection: null`.
5. `vercel.json` wajib `rewrites` catch-all -> tanpa itu semua route 404.
6. Endpoint non-session (worker/heartbeat) wajib `csrf.exempt` di `app/__init__.py`.
7. Jangan set `SESSION_COOKIE_DOMAIN` (cookie host-only supaya login pasti cocok).
8. Dua instance `SQLAlchemy` ada (`app/__init__.py` punya yang ter-init) ->
   modul baru wajib `from app import db`.
