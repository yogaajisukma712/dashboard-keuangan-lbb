# Mapping Progres Audit Presensi vs Fee Tutor

Periode final data: 2024-08-01 sampai 2025-12-31.

Prinsip utama: fee tutor yang sudah dibayarkan adalah sumber pembanding paling akurat. Presensi boleh dikoreksi agar selaras dengan fee yang sudah dibayar, setelah backup SQL dan audit read-only.

## Status Legend

- `[ ]` Belum mulai
- `[~]` Sedang dikerjakan
- `[x]` Selesai
- `[N/A]` Tidak diterapkan karena diganti keputusan eksekusi
- `[!]` Blocker / butuh keputusan
- `[R]` Butuh review manual

## Goal Utama

- [x] Backup SQL lengkap sebelum perubahan data.
- [x] Buat audit read-only presensi vs fee tutor periode Agustus 2024 - Desember 2025.
- [x] Cocokkan fee tutor paid dengan presensi per bulan/tutor/siswa/mapel.
- [x] Tandai mismatch: presensi kurang, presensi berlebih, kemungkinan double, kemungkinan sesi hilang.
- [x] Koreksi SQL setelah user meminta mismatch langsung disesuaikan karena backup sudah ada.
- [x] Re-run audit setelah koreksi setiap bulan.
- [x] Update dashboard: hutang gaji tutor berasal dari pembayaran siswa, berkurang saat payout paid.
- [x] Tambah test agar formula dashboard/payroll tidak kembali ke konsep lama.
- [x] Kunci periode audit fix agar scan WhatsApp tidak mengubah presensi yang sudah match.
- [x] Amankan artefak audit/backup agar tidak ikut commit.
- [x] Cocokkan dan kunci Januari-Maret 2026 seperti periode fix sebelumnya.

## Urutan Eksekusi

### P0 - Safety Baseline

- [x] Buat backup SQL full.
- [x] Catat lokasi file backup.
- [x] Catat ukuran file backup.
- [x] Catat checksum backup.
- [x] Simpan snapshot row count tabel utama:
  - `attendance_sessions`
  - `student_payments`
  - `student_payment_lines`
  - `tutor_payouts`
  - `tutor_payout_lines`
- [x] Tidak ada update/delete SQL sebelum P0 selesai.

Output wajib:

- `backups/lbb_db_YYYYMMDD_HHMMSS.sql`
- `backups/lbb_db_YYYYMMDD_HHMMSS.sha256`
- Ringkasan row count sebelum koreksi.

### P1 - Audit Query Read-Only

- [x] Buat query agregasi presensi per bulan/tutor/siswa/mapel.
- [x] Buat query agregasi payout paid per bulan/tutor.
- [x] Buat query agregasi payout line per service_month.
- [x] Buat query pembanding presensi fee vs payout paid.
- [x] Export hasil audit ke CSV.
- [x] Tidak ada perubahan data pada tahap ini.

Output wajib:

- `audit_outputs/presensi_fee_audit_YYYYMMDD.csv`
- Summary mismatch per bulan.

### P2 - Sample Bulan Pertama

Batch awal: Agustus 2024.
Prioritas mismatch terbesar dari P1: Oktober 2025, Desember 2025, Februari 2025.

- [N/A] Audit Agustus 2024.
- [x] Audit sample mismatch Oktober 2025.
- [x] Kelompokkan hasil dari audit seluruh periode:
  - `[x] MATCH`
  - `[x] PRESENSI_KURANG`
  - `[x] PRESENSI_BERLEBIH`
  - `[N/A] KEMUNGKINAN_DOUBLE`
  - `[N/A] BUTUH_REVIEW`
- [x] User meminta koreksi langsung karena backup SQL sudah tersedia.
- [x] Aturan koreksi aman ditentukan: penyesuaian nominal fee presensi, tanpa delete/insert presensi.

Catatan eksekusi: user meminta ketidakseimbangan langsung disesuaikan agar match karena backup SQL sudah tersedia. Koreksi dilakukan secara finansial dengan menyesuaikan `attendance_sessions.tutor_fee_amount` pada sesi `attended`, tanpa delete/insert presensi.

Kriteria lanjut:

- Selisih bisa dijelaskan.
- Aturan koreksi jelas.
- Tidak ada perubahan massal tanpa sample valid.

### P3 - Koreksi Data Bulanan

Per bulan dari Agustus 2024 sampai Desember 2025.

Untuk setiap bulan:

- [x] Jalankan audit read-only.
- [x] Simpan file hasil audit.
- [x] Review kandidat koreksi.
- [x] Apply koreksi SQL batch kecil.
- [x] Simpan log perubahan.
- [x] Re-run audit.
- [x] Tandai periode `fixed` karena mismatch 0 dan sisa selisih Rp 0.

Daftar bulan:

- [x] 2024-08
- [x] 2024-09
- [x] 2024-10
- [x] 2024-11
- [x] 2024-12
- [x] 2025-01
- [x] 2025-02
- [x] 2025-03
- [x] 2025-04
- [x] 2025-05
- [x] 2025-06
- [x] 2025-07
- [x] 2025-08
- [x] 2025-09
- [x] 2025-10
- [x] 2025-11
- [x] 2025-12

## Aturan Koreksi Data

### Jika payout/fee paid lebih besar dari presensi

Makna: presensi kemungkinan kurang.

Langkah:

- [x] Cari tutor dan bulan yang terkait.
- [N/A] Cari indikasi sesi hilang.
- [N/A] Jika tanggal jelas, tambahkan presensi yang hilang.
- [N/A] Jika tanggal tidak jelas, masuk `BUTUH_REVIEW`.

Keputusan final: tidak membuat presensi baru; selisih disesuaikan lewat nominal `tutor_fee_amount` pada sesi `attended` terbaru tutor/bulan terkait.

### Jika presensi lebih besar dari payout/fee paid

Makna: presensi kemungkinan berlebih.

Langkah:

- [x] Cari baris tutor/bulan yang terkait.
- [x] Jangan otomatis anggap double.
- [x] Cocokkan terhadap total fee paid.
- [N/A] Jika benar double salah, nonaktifkan/hapus sesuai aturan yang disetujui.
- [N/A] Jika normal 1 hari 2 sesi, biarkan.

Keputusan final: tidak menghapus presensi; selisih disesuaikan lewat nominal `tutor_fee_amount` dan diberi catatan audit.

## Dashboard Logic Baru

Konsep target:

- Uang siswa masuk dari `student_payments`.
- Pemisahan untung dan fee tutor dari `student_payment_lines`.
- Hutang gaji tutor terbentuk dari `student_payment_lines.tutor_payable_amount`.
- Hutang gaji tutor berkurang dari payout tutor yang statusnya paid/confirmed.
- Presensi bukan sumber utama hutang dashboard; presensi jadi alat operasional dan rekonsiliasi.

Formula target:

- Pendapatan siswa = sum `student_payment_lines.nominal_amount`
- Hutang tutor gross = sum `student_payment_lines.tutor_payable_amount`
- Tutor paid = sum `tutor_payout_lines.amount` yang payout-nya paid/confirmed
- Hutang tutor tersisa = hutang tutor gross - tutor paid
- Margin kotor = sum `student_payment_lines.margin_amount`
- Cash keluar tutor = tutor paid

Checklist dashboard:

- [x] Audit formula `DashboardService`.
- [x] Tandai formula lama yang memakai presensi sebagai sumber hutang.
- [x] Ubah formula hutang tutor ke basis pembayaran siswa.
- [x] Pastikan payout paid mengurangi hutang.
- [x] Tambah test dashboard service.
- [x] Verifikasi angka dashboard via focused test.

## Bukti P0 - Backup SQL

- File backup: `backups/lbb_db_20260508_142951.sql`
- File checksum: `backups/lbb_db_20260508_142951.sql.sha256`
- Ukuran: `12,519,866` bytes
- SHA256: `5c8154c32d7bd21556822422e6a87299c19d8158114ee33eb9862523f6ace45f`

Row count sebelum koreksi:

| Tabel | Row |
| --- | ---: |
| `attendance_sessions` | 4,657 |
| `student_payments` | 602 |
| `student_payment_lines` | 860 |
| `tutor_payouts` | 425 |
| `tutor_payout_lines` | 425 |

## Bukti P1 - Audit Read-Only

- File audit utama: `audit_outputs/presensi_fee_audit_20260508_143602.csv`
- File detail presensi: `audit_outputs/presensi_detail_20260508_143602.csv`
- File detail payout: `audit_outputs/payout_detail_20260508_143602.csv`
- File summary mismatch per bulan: `audit_outputs/presensi_fee_audit_month_summary_20260508_143602.csv`
- Baris audit utama: 359
- Status audit: `MATCH` 314 baris, `PRESENSI_BERLEBIH` 42 baris, `PRESENSI_KURANG` 3 baris.
- Total nilai mismatch absolut: Rp 4.420.000.
- Bulan mismatch terbesar:
  - 2025-10: 10 dari 23 baris mismatch, abs selisih Rp 1.450.000.
  - 2025-12: 12 dari 21 baris mismatch, abs selisih Rp 1.150.000.
  - 2025-02: 6 dari 25 baris mismatch, abs selisih Rp 520.000.
- Belum ada perubahan data SQL pada P1.

## Bukti P2 - Sample Mismatch

- File sample mismatch Oktober 2025: `audit_outputs/p2_sample_mismatch_2025_10_20260508_143602.csv`
- Isi sample: 10 baris summary tutor mismatch dan detail presensi terkait.
- Status sample Oktober 2025: `PRESENSI_BERLEBIH` 9 tutor, `PRESENSI_KURANG` 1 tutor.
- Belum ada koreksi data SQL pada P2.

## Bukti P3 - Koreksi Fee Presensi

- File plan koreksi: `audit_outputs/presensi_fee_adjustment_plan_20260508_151000.csv`
- Backup baris terdampak sebelum update: `audit_outputs/presensi_fee_adjustment_rows_before_20260508_151000.csv`
- SQL apply: `audit_outputs/presensi_fee_adjustment_apply_20260508_151000.sql`
- Audit ulang setelah koreksi: `audit_outputs/presensi_fee_audit_attended_post_adjust_20260508_151000.csv`
- Baris presensi terdampak: 134.
- Metode koreksi:
  - `PRESENSI_BERLEBIH`: kurangi `tutor_fee_amount` dari sesi attended terbaru sampai total bulan/tutor match payout.
  - `PRESENSI_KURANG`: tambah `tutor_fee_amount` pada sesi attended terbaru tutor/bulan tersebut sampai match payout.
  - Tidak ada delete/insert presensi.
  - Setiap baris terdampak diberi catatan `AUDIT_FEE_MATCH 2026-05-08`.
- Hasil audit ulang database: mismatch 0, sisa selisih Rp 0.

## Bukti P4 - Dashboard Logic

- File diubah: `app/services/dashboard_service.py`
- File diubah: `app/routes/closings.py`
- File test diubah: `tests/test_dashboard_service.py`
- Perubahan formula:
  - Hutang tutor dashboard = hutang sebelumnya + `student_payment_lines.tutor_payable_amount` bulan berjalan - payout tutor paid/confirmed.
  - `get_grand_tutor_payable()` sekarang mengembalikan hutang tutor tersisa, bukan gross sebelum payout.
  - Monthly closing menyimpan `closing_tutor_payable` sebagai hutang tersisa setelah payout, tidak dikurangi dua kali.
- Test: `docker compose exec -T web python -m pytest tests/test_dashboard_service.py -q`
- Hasil test: 4 passed.

## Bukti P5 - Lock Periode Fix

- Periode dikunci: Agustus 2024 sampai Desember 2025.
- Jumlah lock: 17 bulan.
- Tabel: `attendance_period_locks`.
- Catatan lock: hasil audit presensi vs fee tutor sudah match payout.
- Efek: scan WhatsApp dan aksi tambah/edit/hapus presensi pada bulan terkunci harus buka kunci dulu.
- Verifikasi setelah lock: mismatch 0, sisa selisih Rp 0.

## Bukti P6 - Git Hygiene

- File diubah: `.gitignore`
- Folder diabaikan dari commit:
  - `backups/`
  - `audit_outputs/`
- Alasan: folder tersebut berisi backup SQL dan CSV audit data operasional.
- Manifest dan bukti ringkas tetap ada di file ini agar progres bisa dipantau tanpa commit data sensitif.

## Bukti P7 - Koreksi Fee Presensi Q1 2026

- Periode: Januari 2026 sampai Maret 2026.
- Backup sebelum koreksi: `backups/lbb_db_before_2026_q1_match_20260508_154301.sql`
- SHA256 backup: `39f6cbb65016ef42094faaf87841b49933be70c47f2fb7005c1f5980bf9b387d`
- File audit sebelum koreksi: `audit_outputs/presensi_fee_audit_attended_2026_q1_before_20260508_154301.csv`
- File plan koreksi: `audit_outputs/presensi_fee_adjustment_plan_2026_q1_20260508_154301.csv`
- Backup baris terdampak sebelum update: `audit_outputs/presensi_fee_adjustment_rows_before_2026_q1_20260508_154301.csv`
- SQL apply: `audit_outputs/presensi_fee_adjustment_apply_2026_q1_20260508_154301.sql`
- Audit ulang setelah koreksi: `audit_outputs/presensi_fee_audit_attended_2026_q1_post_20260508_154301.csv`
- Target mismatch sebelum koreksi: 19 tutor/bulan.
- Baris presensi terdampak: 58.
- Hasil audit ulang: 59 baris `MATCH`, mismatch 0, sisa selisih Rp 0.
- Lock periode: Januari 2026, Februari 2026, Maret 2026.
- Tidak ada delete/insert presensi.

## Progress Log

| Tanggal | Tahap | Status | Catatan | Output |
| --- | --- | --- | --- | --- |
| 2026-05-08 | P7 | [x] | Januari-Maret 2026 dicocokkan terhadap payout paid dan hasil audit ulang mismatch 0. | `audit_outputs/presensi_fee_audit_attended_2026_q1_post_20260508_154301.csv` |
| 2026-05-08 | P7 | [x] | Januari-Maret 2026 dikunci setelah match. | `attendance_period_locks` |
| 2026-05-08 | P6 | [x] | Backup SQL dan audit output dikecualikan dari git agar tidak ikut commit/push. | `.gitignore` |
| 2026-05-08 | P5 | [x] | Periode 2024-08 sampai 2025-12 dikunci setelah audit match. | `attendance_period_locks` |
| 2026-05-08 | P4 | [x] | Dashboard logic disesuaikan: hutang tutor dari pembayaran siswa dan berkurang saat payout paid/confirmed. | `app/services/dashboard_service.py` |
| 2026-05-08 | P4 | [x] | Focused dashboard test passed. | `tests/test_dashboard_service.py` |
| 2026-05-08 | P4 | [x] | Container web rebuilt dan dashboard route merespons redirect login normal. | `docker compose up -d --build web` |
| 2026-05-08 | P3 | [x] | Koreksi fee presensi diterapkan untuk seluruh mismatch periode 2024-08 sampai 2025-12. | `audit_outputs/presensi_fee_adjustment_apply_20260508_151000.sql` |
| 2026-05-08 | P3 | [x] | Audit ulang setelah koreksi menghasilkan semua baris `MATCH`, mismatch 0, selisih Rp 0. | `audit_outputs/presensi_fee_audit_attended_post_adjust_20260508_151000.csv` |
| 2026-05-08 | P2 | [x] | Sample mismatch Oktober 2025 dibuat, lalu user meminta koreksi langsung karena backup sudah tersedia. | `audit_outputs/p2_sample_mismatch_2025_10_20260508_143602.csv` |
| 2026-05-08 | P1 | [x] | Audit read-only presensi vs payout paid selesai. Tidak ada update/delete SQL. | `audit_outputs/presensi_fee_audit_20260508_143602.csv` |
| 2026-05-08 | P1 | [x] | Summary mismatch per bulan dibuat untuk menentukan batch koreksi. | `audit_outputs/presensi_fee_audit_month_summary_20260508_143602.csv` |
| 2026-05-08 | P0 | [x] | Backup SQL full, checksum, dan row count baseline selesai. Belum ada koreksi data. | `backups/lbb_db_20260508_142951.sql` |
| 2026-05-08 | P0 | [x] | File mapping progres dibuat. | `AUDIT_PRESENSI_FEE_PROGRESS.md` |

## Keputusan Terbuka

- [x] Presensi berlebih tidak dihapus; nominal `tutor_fee_amount` disesuaikan dan diberi catatan audit.
- [x] Presensi kurang tidak dibuat tanggal baru; nominal sesi attended terbaru tutor/bulan terkait disesuaikan dan diberi catatan audit.
- [x] Payout yang mengurangi hutang: `completed`, `paid`, `confirmed`.
- [x] Periode 2024-08 sampai 2025-12 dikunci setelah koreksi selesai.

## Cara Mulai Yang Disarankan

1. Jalankan backup SQL full.
2. Ambil row count tabel utama.
3. Buat audit read-only untuk Agustus 2024.
4. Review Agustus 2024 bersama user.
5. Baru apply koreksi data untuk Agustus 2024.
6. Jika hasil benar, ulangi per bulan sampai Desember 2025.
