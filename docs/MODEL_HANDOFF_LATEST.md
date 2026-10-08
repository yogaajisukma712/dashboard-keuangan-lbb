# Model Handoff Terbaru — LBB Dashboard + WhatsApp Bot

> Snapshot: 2026-10-08. Dokumen ini ditujukan untuk model/agent berikutnya. Baca `AGENTS.md`, `PROJECT_MAP.md`, dokumen arsitektur, lalu dokumen ini.

## Ringkasan sistem

Aplikasi ini adalah Flask dashboard operasional/keuangan LBB Super Smart.

```text
Flask dashboard (Vercel: app.supersmart.click)
        │
        ├── Neon PostgreSQL (sumber data tunggal)
        │       ├── master: User, Tutor, Student, Subject, Curriculum, Level
        │       ├── akademik: Enrollment, EnrollmentSchedule, AttendanceSession
        │       ├── WhatsApp evidence: WhatsAppGroup, WhatsAppMessage,
        │       │   WhatsAppEvaluation, validation/alias/group membership
        │       └── finance: StudentPayment*, TutorPayout*, proofs, closing
        │
        └── VM worker + WhatsApp bot (tunnel: wa.supersmart.click)
                ├── WhatsApp Web.js + Chromium + persistent auth volume
                ├── polling heavy_jobs di Neon
                ├── render PDF fee slip
                ├── kirim dokumen WhatsApp
                └── POST payload sync WhatsApp → dashboard
```

## Graphify snapshot

Graphify telah direfresh dari source saat ini:

- Output utama: `graphify-out/graph.json`, `graphify-out/GRAPH_REPORT.md`, `graphify-out/graph.html`.
- 3.265 nodes, 7.048 edges, 233 communities.
- Extraction: 97% extracted, 3% inferred, 0% ambiguous.
- File corpus: 219 file.
- Graphify hubs: `Tutor`, `Enrollment`, `AttendanceSession`, `Student`, `WhatsAppIngestService`, `DashboardService`, `TutorPayout`, `WhatsAppMessage`, `WhatsAppEvaluation`.
- Flow penting terpetakan: fee slip payroll → PDF → `heavy_jobs` → VM worker → bot `/messages/send`; WhatsApp group → parser → `WhatsAppEvaluation` → `AttendanceSession`.
- Setelah perubahan source, jalankan `graphify update .`. Jangan commit secret/cache mentah.

## Deployment production aktual

### Dashboard

- URL: `https://app.supersmart.click`.
- Runtime: Flask di Vercel.
- Route dashboard memanggil bot melalui `WHATSAPP_BOT_INTERNAL_URL`, token melalui `WHATSAPP_BOT_TOKEN`.
- `app/routes/whatsapp.py` menjadi proxy management/session/group/contact ke bot.
- `app/routes/payroll.py` membuat PDF, mengirim langsung untuk single slip, atau membuat job untuk bulk.
- `app/services/remote_storage.py` mengalihkan file upload dari filesystem ephemeral Vercel ke endpoint file VM.

### Database

- Neon PostgreSQL adalah source of truth untuk dashboard, worker, evaluasi WhatsApp, attendance, payroll, dan `heavy_jobs`.
- Jangan memakai database lokal/container untuk keputusan production.
- Jangan commit `DATABASE_URL`, token, credential, `.env`, `api key penting/`, `.server_lembaga`, `.pem`.
- Tabel integrasi utama:
  - `attendance_sessions`: sesi presensi dan `tutor_fee_amount`.
  - `whatsapp_messages`: pesan asli dari group.
  - `whatsapp_evaluations`: hasil parser/matching pesan ke siswa/tutor/tanggal.
  - `tutor_payouts`, `tutor_payout_lines`, `tutor_payout_proofs`: payroll, settlement, bukti.
  - `heavy_jobs`: antrean pekerjaan panjang dari dashboard ke VM.

### VM bot

- Production bot aktif pada VM Sumopod yang terhubung ke tunnel `supersmart-wa-vps`; tunnel publik: `wa.supersmart.click`.
- Working directory production: `/opt/apps/lembaga/vm-bundle`.
- Container: `billing_supersmart_whatsapp_bot`.
- Production image aktif terakhir: `lbb-whatsapp-bot:media-fixed`.
- Auth volume tetap dipertahankan: `/app/.wwebjs_auth`.
- Status terakhir terverifikasi: `ready=true`, `authenticated=true`.
- `WHATSAPP_AUTO_SYNC_ENABLED=true` di production; `WHATSAPP_AUTO_SYNC_FULL_SYNC=false` teramati pada instance production.
- Auto-sync dapat menambah/memproses evidence WhatsApp. Attendance bulan yang sudah memiliki payout ditahan oleh `is_tutor_month_payout_locked()` pada jalur auto-create.

## Integrasi WhatsApp attendance

1. Bot membaca group/chat melalui `whatsapp-bot/src/chat-loader.js`.
2. `evaluation/parser.js` mengklasifikasikan laporan dan mengekstrak nama, tanggal, subjek, waktu.
3. `flask-client.js` mengirim payload ke dashboard.
4. `WhatsAppIngestService` melakukan validasi identitas tutor/siswa/group, normalisasi, dan upsert `WhatsAppEvaluation`.
5. `link_or_create_attendance()` menghubungkan evaluasi ke `AttendanceSession`.
6. Attendance menjadi source untuk tutor payable/payout.

Guard penting:

- Evidence WhatsApp tidak otomatis dipercaya; ambiguity harus bisa direview.
- `AttendancePeriodLock` mencegah scan mengubah periode terkunci.
- `is_tutor_month_payout_locked()` mencegah auto-ingest menambah sesi baru pada bulan tutor yang sudah punya payout; manual admin tetap diperbolehkan.
- Duplikat fallback lama memakai ID/prefix `false_`; jangan menghapus sesi tanpa bukti kembar kanonik dan FK audit.

## Integrasi payroll fee slip

### Single slip

`app/routes/payroll.py`:

1. `fee_slip_send_whatsapp()` memilih nomor WhatsApp tutor.
2. `_render_fee_slip_pdf_via_bot()` meminta bot merender HTML menjadi PDF.
3. `_send_fee_slip_whatsapp_attachment()` memanggil bot `/messages/send` dengan `MessageMedia` payload.
4. Gagal kirim mengembalikan `ok=false`, HTTP 502, dan tidak mengisi timestamp seolah sukses.
5. Pencatatan `whatsapp_last_status` harus dibedakan antara `sent` dan `failed`.

### Bulk slip

1. Dashboard insert satu row `heavy_jobs` bertipe pengiriman fee slip.
2. Worker `whatsapp-bot/src/heavy-jobs.js` polling job tiap interval.
3. Worker memanggil endpoint dashboard `/payroll/api/fee-slip-job/<ref>`.
4. Endpoint Flask tersebut merender dan mengirim slip melalui `_send_fee_slip_whatsapp_attachment()`; worker hanya mengumpulkan hasil, bukan langsung mengirim PDF untuk jalur bulk ini.
5. Hasil dikembalikan sebagai sent/failed/skipped. `heavy_jobs.status=done` berarti batch selesai diproses, bukan semua slip terkirim: baca `result.sent`, `result.failed`, dan `result.detailFailed`. Error HTTP per-slip ditangkap dalam loop sehingga batch dapat `done` dengan kegagalan; jangan menganggap retry job menjamin retry setiap slip gagal.

### Perbaikan upload PDF production

Akar error:

```text
upload failed: media entry was not created
Data passed to getter must include an id property
```

Penyebab: `whatsapp-web.js 1.34.7` belum membawa upstream fix untuk private `__x_id` dari MediaData yang menimpa ID Msg saat media dikirim. Patch persisten berada di:

- `whatsapp-bot/patches/apply-wwebjs-media-fix.js`
- `whatsapp-bot/Dockerfile`
- `whatsapp-bot/src/whatsapp-client.js`

Patch production saat ini melakukan dua normalisasi:

- hapus `message.__x_id` sebelum Msg dikirim;
- fallback ID WhatsApp baru `id.$1` selain `_serialized`.

Production telah diuji tanpa mengirim ke tutor:

- render PDF: sukses;
- kirim `uji-persistent.pdf` ke nomor bot sendiri: sukses;
- WhatsApp receipt: `type=document`, `ack=3`, message ID valid;
- bot tetap `ready/authenticated` setelah recreate container.

Jangan menyatakan slip tutor terkirim hanya karena job berstatus `done`; cek hasil `sent`, error, dan bila perlu ACK/message receipt.

## Status data payroll yang diaudit

- Rendi September: 41 sesi tervalidasi manual.
- Chelsi September: fee `35.000` per sesi.
- Kekurangan Agustus Chelsi: 7 sesi × `5.000` = `35.000`, dibawa sebagai line kekurangan ke payout September.
- Payout Rendi September: 41 sesi `1.365.000` + shortfall Agustus `35.000` = `1.400.000`.
- Jangan menjalankan ulang cleanup/payout tanpa query idempoten dan transaksi/lock.

## Presensi manual

`app/routes/attendance.py` dan `app/templates/attendance/form.html` harus tetap mengirim `attendance_tutor_map` pada route tambah dan edit. Tanpa context tersebut, tombol tambah/edit membuka form tetapi gagal render. Jalur manual admin berbeda dari auto-ingest dan tidak boleh diblok hanya karena payout-lock auto-ingest.

## Backup, rollback, dan deployment

- Session WhatsApp ada di volume auth; jangan menghapus volume saat mengganti image.
- Sebelum patch production, backup file/library atau volume; gunakan image rollback bila health turun.
- Source deployment VM ada di `deploy/vm-bundle/`.
- Production VM dapat berbeda dari local Docker. Verifikasi tunnel publik, bukan hanya `127.0.0.1` lokal.
- Build image langsung di VM pernah gagal karena mirror Debian; prefer prebuilt GHCR/image dari image sehat.
- Setelah deploy: cek `/health`, `/session`, container image digest, auth state, render PDF, lalu uji dokumen ke nomor bot sendiri.
- Jangan kirim ulang slip tutor otomatis setelah test; gunakan approval eksplisit untuk tutor nyata.

## Validasi wajib sebelum perubahan berikutnya

```text
1. Baca AGENTS.md + PROJECT_MAP.md + blueprint terkait.
2. Cek git status dan jangan menimpa perubahan user.
3. Jalankan Graphify update setelah perubahan struktur kode.
4. Untuk simbol besar, jalankan GitNexus impact sebelum edit.
5. Jalankan test relevan.
6. Cek secret scan dan staged diff.
7. Commit hanya file yang dimaksud.
8. Push remote `origin` setelah status/diff/log ditinjau.
```

## Jangan salah baca state

- Graphify graph merepresentasikan source repo; tidak otomatis merepresentasikan image/container production.
- Neon database production adalah state runtime; Graphify tidak menyimpan data transaksi.
- VM image production bisa memiliki patch manual. Source patch wajib dipertahankan di `whatsapp-bot/patches/` dan Dockerfile agar rebuild berikutnya tidak menghilangkannya.
- Credential production berada di file ignored/secret store. Model berikutnya harus meminta/verifikasi akses, bukan menebak atau mencetak secret.
