# Rencana Migrasi: WA Bot di VM, Dashboard di Vercel, Database di Neon

> Disusun dari analisis graph (gitnexus 4.374 node/370 flow; graphify 2.262 node/124 komunitas) + code scan, 2026-09-06.
> Tujuan: VM mati → hanya WA bot terdampak. Dashboard + DB tetap hidup. Migrasi bot = pindah VM saja.

## Arsitektur Target

```
┌─────────────────┐   DATABASE_URL    ┌──────────────────┐
│  Vercel         │ ────────────────► │  Neon Postgres    │
│  dashboard web  │                   │  (lbb_db, 58MB)  │
│  app/tutor/     │                   └──────────────────┘
│  recruitment   │
└───┬────────▲───┘
    │        │ POST /api/whatsapp/sync
    │        │ header X-Bot-Token (WHATSAPP_BOT_TOKEN)
    │ WHATSAPP_BOT_INTERNAL_URL
    ▼        │
┌────────────┴────┐  cloudflared tunnel   ┌─────────────────┐
│  VM (bot only)   │ ◄───────────────────  │ Cloudflare edge  │
│  whatsapp_bot    │  wa.supersmart.click  └─────────────────┘
│  + cloudflared   │
│  + session vol   │
└──────────────────┘
```

Pemisahan berdasar graph — sudah terbukti loose coupling:
- Komunitas bot (`whatsapp-bot/*`, 197 node) → VM
- Komunitas app (`app/*`, 1507 node) → Vercel
- Koneksi lintas = murni HTTP + env var (graphify: 0 edge statis lintas bahasa yang berarti; gitnexus: wiring hanya lewat `WHATSAPP_BOT_INTERNAL_URL` / `WHATSAPP_FLASK_BASE_URL` / `WHATSAPP_BOT_TOKEN`)

## Workstream A — Database → Neon (dulu, fondasi)

1. Buat project Neon (region apapun dekat user, mis. Singapore) → dapat connection string pooled + direct.
2. Restore dari backup terverifikasi:
   ```bash
   # dari backups/ec2-full-backup-20260905-232801-WIB/
   pg_restore --no-owner --role=neondb_owner --clean --if-exists \
     -d "postgresql://...neon.../neondb" database/lbb_db.dump
   ```
   (37 tabel, 36.174 row — `--no-owner` karena role AWS beda dari Neon.)
3. Verifikasi: row count 5 tabel kunci sama (whatsapp_messages=22128, attendance_sessions=4318, student_payments=552, whatsapp_evaluations=1808, expenses=313).
4. Neon free tier: 0.5GB storage (cukup, DB 58MB), autosuspend OK untuk dashboard Flask.

## Workstream B — Dashboard → Vercel

**Blokir 2 hal dulu (urutan wajib):**

### B1. Fix tulis-file `UPLOAD_FOLDER` (blocker filesystem ephemeral)
Bukti scan: `_save_tutor_upload` (tutor_portal.py:962), payroll proofs (payroll.py:438), route serve `/uploads/<path>` (tutor_portal.py:1630, payroll.py:2439).
Pilihan (urut rekomendasi):
- **R2 (Cloudflare R2)** — `.env.railway` template sudah menyiapkan pola `AWS_S3_*` (S3-compatible API, R2 compatible). Buat `app/services/storage.py` abstraction: `save_upload(folder, file) -> key`, `url_for(key)`. Ubah 4 titik di atas. Serve via presigned URL atau r2 public bucket. Kerja: ±½ hari.
- Alternatif murah tapi menambah ketergantungan VM: volume di bot VM + serve via tunnel. TIDAK disarankan — menyatukan lagi nasib file dengan VM.
- Bypass total: kalau upload proof jarang dipakai, nonaktifkan fitur upload sementara di Vercel (feature flag) dan kerjakan R2 belakangan.

### B2. Fix `Thread()` bulk slip fee (blocker serverless)
Bukti scan: `payroll.py:1967` `Thread(...)` untuk `_send_fee_slips_whatsapp_bulk_background` — di Vercel function, thread mati saat response terkirim → job hilang diam-diam.
Pilihan:
- **Job table + bot pull** (rekomendasi): tabel `wa_send_jobs` (payload slip, status pending) ditulis route sync; bot, yang sudah punya loop auto-sync/watchdog (terbukti di graph: `startAutoSyncScheduler`, `runScheduledAutoSync`), polling job pending tiap menit → kirim → update status. VM mati = job menumpuk pending, tidak hilang; VM hidup lagi = lanjut kirim.
- Alternatif: synchronous dengan `maxDuration=300` (Vercel pro) — hanya kalau volume slip kecil (<50).

### B3. Deploy Vercel
1. `vercel.json` + runtime Python (WSGI adapter `api/index.py` → `app:create_app()`).
2. Build command: `pip install -r requirements.txt` + `flask db upgrade` (jalankan sekali via Vercel CLI, bukan tiap cold start).
3. Env: `DATABASE_URL` (Neon pooled), `SECRET_KEY`, `WHATSAPP_BOT_TOKEN`, `WHATSAPP_BOT_INTERNAL_URL=https://wa.supersmart.click`, `SESSION_COOKIE_DOMAIN=.supersmart.click`, `UPLOAD` config R2.
4. Gunicorn Procfile sudah ada (`web: gunicorn -w 4 run:app`) — tidak dipakai Vercel tapi berguna kalau nanti pindah Fly/Render.
5. 3 deployment/domain: `app.supersmart.click`, `tutor.supersmart.click`, `recruitment.supersmart.click` (tunnel Cloudflare web lama dimatikan, DNS diarahkan ke Vercel/CNAME).
   - Catatan: app+billing+tutor = satu codebase sama, dibedakan env (pola container AWS/DO yang sudah terbukti di graph — `create_app` tunggal).

## Workstream C — Bot ke VM (terpisah penuh)

1. VM kandidat: **VPS #2 DO `139.59.99.242`** (idle sekarang) atau VM baru — bot butuh ±2GB RAM (chromium).
2. Deploy: `whatsapp-bot/` + Dockerfile sudah self-contained (terbukti — image 823MB berisi chromium+node18). Cukup `docker compose up -d whatsapp_bot` dengan env:
   - `WHATSAPP_FLASK_BASE_URL=https://app.supersmart.click` (URL Vercel)
   - `WHATSAPP_BOT_TOKEN=<sama>`
   - volume `whatsapp_bot_auth` + `whatsapp_bot_backups` (restore dari backup tar 127M+334M — QR tidak perlu scan ulang kalau sesi valid)
3. Expose bot via **cloudflared tunnel baru** `wa.supersmart.click` → `localhost:6002` (pola systemd `cloudflared-lembaga@` sudah ada & terbukti di DO #1 — copy unit + token baru).
4. `WHATSAPP_BOT_INTERNAL_URL` di Vercel = `https://wa.supersmart.click`.
   - Semua 3 call site dashboard (whatsapp.py:47, tutor_portal.py:386, payroll.py:113) otomatis ikut — tak ada ubah kode, hanya env.
5. Firewall VM: hanya SSH + outbound (bot & tunnel keluar-initiate). Tidak ada port publik.

## Workstream D — Cutover & Decommission

1. Freeze tulisan (stop app containers DO #1) → final `pg_dump` → restore ke Neon (metode sama, terbukti 0-delta di migrasi kemarin).
2. Vercel live-test di domain preview → cek login, list siswa, payroll.
3. Bot VM baru: start, verify `/health` 200 via tunnel, sesi WA `authenticated:true` (kalau minta QR, scan sekali — terakhir awaiting_qr sejak AWS).
4. DNS cutover: 3 domain → Vercel. Matikan tunnel web di DO #1.
5. DO #1 decommission (snapshot dulu volume WA bila sesi dipindah dari sana).
6. AWS EC2 terminate (sudah tidak melayani apa pun sejak migrasi DO).

## Risiko & Mitigasi

| Risiko | Bukti | Mitigasi |
|---|---|---|
| Uploads hilang di Vercel FS | `_save_tutor_upload` menulis disk | R2 sebelum cutover (B1) |
| Bulk slip fee hangus | `Thread()` payroll.py:1967 | Job table + bot polling (B2) |
| Cold start Vercel Python | serverless nature | Acceptable (dashboard internal); cache boot via /health ping kalau perlu |
| VM bot mati | alasan utama rencana ini | Job table menahan queue; data aman di Neon; restore volume = tar 127M, minutes |
| QR rescan saat ganti VM | sesi chromium 1.1G per-volume | backup `_auth` volume rutin (cron tar ke R2) |
| Neon free tier suspend | autosuspend | wake otomatis on-connect; latency +300ms pertama |

## Urutan Eksekusi (dependency order)

```
A (Neon) ──► B1 (R2 storage) ──► B3 (Vercel deploy, staging)
                     │
                     └─► B2 (job table) ──► C (bot VM + tunnel)
                                                  │
                              D (cutover DNS) ◄───┘
```

Estimasi: A ±1 jam, B1 ±½ hari, B2 ±½-1 hari, B3 ±2 jam, C ±1 jam, D ±1 jam.
