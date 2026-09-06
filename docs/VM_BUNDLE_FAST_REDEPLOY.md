# Bundel VM: WA Bot + Scheduler + Job Berat (Fast Redeploy)

> Revisi arsitektur 2026-09-06: scheduler bot tetap di VM; fitur berat (bulk kirim, export besar, import massal) ikut VM. Dashboard Vercel tetap kurus (CRUD + view). Prinsip: **VM mati → hanya fitur berat + bot terdampak; data (Neon) + dashboard (Vercel) hidup; VM baru siap < 15 menit.**

## Pembagian final

| Komponen | Tempat | Alasan |
|---|---|---|
| DB `lbb_db` | Neon | availability tertinggi, autoscale, free tier cukup (58MB) |
| Dashboard (CRUD, laporan ringan, auth) | Vercel | serverless cocok — request sinkron pendek saja |
| WA bot + auto-sync scheduler (6 jam) + watchdog | VM | butuh proses persist + chromium |
| Bulk kirim slip gaji (ex-Thread payroll.py:1967) | VM worker | proses panjang, reconnect WA |
| Export/import besar (openpyxl massal, BulkImportService CSV besar) | VM worker | CPU/memory besar, tanpa maxDuration |
| Uploads (tutor files, payroll proofs) | VM volume + backup harian | FS Vercel ephemeral; R2 opsional belakangan |
| Vercel masih perlu: skip `setup_logging` file handler (VERCEL=1), tanpa entrypoint Docker | patch kecil | sudah teridentifikasi |

Pola koordinasi Vercel→VM untuk job berat: **tabel job di Neon** (`heavy_jobs`: type, payload, status, requested_by). Route dashboard (mis. tombol "kirim semua slip") tinggal INSERT row → VM worker polling tiap 10-30 detik → eksekusi → update status → dashboard view menampilkan progress dari tabel. VM mati = job status `pending` menunggu, tidak hilang.

## Bundel Fast Redeploy VM (`deploy/vm-bundle/`)

Target: VM baru dari nol → bot jalan < 15 menit, tanpa build chromium di VM (hindari kegagalan mirror bullseye yang sudah terjadi).

### Isi repo
```
deploy/vm-bundle/
├── install.sh              # one-liner bootstrap: docker, compose, image pull, systemd, restore volume, up
├── docker-compose.vm.yml   # bot + worker (satu compose, project name tetap: aplikasilembaga)
├── systemd/
│   ├── cloudflared-wa@.service + wrapper (pola cloudflared-lembaga@, terbukti jalan)
│   └── vm-bundle-backup.timer/.service  # backup harian volume → GitHub release (enkripsi age/openssl)
└── RESTORE.md              # runbook pemulihan
```

### Kunci desain
1. **Image prebuilt di GHCR** (`ghcr.io/yogaajisukma712/lbb-*`): push image WA bot + worker hasil build sekali (dari mesin mana pun yang bisa build — lokal/DO #1). VM baru cukup `docker pull`, tidak pernah build. Menutup risiko mirror apt mati + menjamin identik.
2. **Backup harian state VM** → repo `lembaga-db-backups` (pola release terenkripsi sudah ada & terbukti): tar `whatsapp_bot_auth` (127M terkompresi) + `uploads/`. Retensi 7 hari. WA session bertahan → tanpa QR ulang setelah VM mati.
3. **install.sh** idempoten:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/yogaajisukma712/dashboard-keuangan-lbb/main/deploy/vm-bundle/install.sh | bash -s -- \
     --tunnel-token <cloudflared-token-wa> \
     --backup-release <latest-tag>
   ```
   Langkah: docker install (get.docker.com) → pull GHCR → restore volume dari release → compose up → cloudflared systemd enable → ufw (SSH only) → smoke test `/health` + `/session`.
4. **Tunnel WA**: `wa.supersmart.click` via cloudflared (token baru per VM, dibuat sekali di CF dashboard; route DNS tetap). Ganti VM = install ulang tunnel token yang sama (connector baru menimpa), DNS tak berubah.

### Runbook pemulihan (VM mati mendadak)
1. Buat VM baru (DO/Fly/vps manapun, 2 vCPU/2GB min — chromium butuh ~1.2G).
2. Jalankan `install.sh` (semua state dari release terbaru).
3. Cek `https://wa.supersmart.click/health` → 200.
4. Cek `WHATSAPP_BOT_INTERNAL_URL` di Vercel tetap menunjuk domain WA (tak berubah).
5. Job `pending` di Neon otomatis diproses worker baru.
6. Scan QR hanya jika release backup lebih tua dari unlink sesi (jarang; sesi WA umumnya bertahan).

## Urutan eksekusi revisi

```
A  Neon: buat project + restore lbb_db.dump        (API key ada, akun verified)
B  Vercel: deploy dashboard (patch logging + no-entrypoint)
C1 GHCR: build & push image bot+worker
C2 deploy/vm-bundle: install.sh + compose.vm.yml + backup timer
D  VM: install via bundle, tunnel wa.supersmart.click
E  Job table + route "kirim bulk" INSERT job (ganti Thread)
F  Cutover DNS → Vercel; decommission tunnel web lama; AWS terminate
```

E bisa dikerjakan setelah D (VM dulu jalan, koordinasi menyusul) — bulk kirim tetap bisa dipicu manual dari UI bot VM sementara.
