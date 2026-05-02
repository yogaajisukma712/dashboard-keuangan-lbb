# Analisis Logic, Alur, Perhitungan, dan Risiko Error

Tanggal: 2026-04-29

## Scope

Dokumen ini merangkum logic proses inti aplikasi, hubungan antar entitas, rumus perhitungan utama, alur halaman, dan titik rawan error. Dokumen ini dibuat dari inspeksi route, model, service, template, log runtime, dan dokumen audit yang ada di repo.

## Arsitektur Singkat

- Stack utama: Flask + SQLAlchemy + Jinja2 + PostgreSQL.
- Blueprint utama:
  - `auth`
  - `master`
  - `enrollments`
  - `attendance`
  - `payments`
  - `incomes`
  - `expenses`
  - `payroll`
  - `dashboard`
  - `reports`
  - `closings`
  - `quota_invoice`
- Lapisan aplikasi:
  - `models`: struktur data dan relasi
  - `routes`: halaman, form submit, API JSON
  - `services`: agregasi laporan, dashboard, payroll, reconciliation
  - `templates`: halaman HTML + AJAX/fetch

## Entitas dan Hubungan

### Master

- `Student`, `Tutor`, `Subject`, `Curriculum`, `Level`
- `Enrollment` menghubungkan siswa ke mapel, tutor, kurikulum, jenjang, dan tarif.

Referensi:
- [app/models/enrollment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/enrollment.py:11)

### Operasional

- `EnrollmentSchedule`: jadwal berulang per enrollment.
- `AttendanceSession`: sesi les aktual. Menyimpan `enrollment_id`, `student_id`, `tutor_id`, `session_date`, `status`, `tutor_fee_amount`.

Referensi:
- [app/models/attendance.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/attendance.py:11)

### Keuangan Siswa

- `StudentPayment`: header pembayaran siswa.
- `StudentPaymentLine`: detail per enrollment/periode layanan.
- Nilai turunan:
  - `nominal_amount = meeting_count * student_rate_per_meeting`
  - `tutor_payable_amount = meeting_count * tutor_rate_per_meeting`
  - `margin_amount = nominal_amount - tutor_payable_amount`

Referensi:
- [app/models/payment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/payment.py:11)
- [app/models/payment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/payment.py:96)

### Keuangan Tutor

- `TutorPayout`: header pembayaran tutor.
- `TutorPayoutLine`: detail payout per `service_month`.

Referensi:
- [app/models/payroll.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/payroll.py:11)

### Snapshot Bulanan

- `MonthlyClosing`: opening/closing cash, payable tutor, profit, income, expense, salary, margin.

Referensi:
- [app/models/closing.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/closing.py:11)

## Alur Proses Inti

### 1. Master Data -> Enrollment

1. Admin input master siswa/tutor/mapel/kurikulum.
2. User membuat `Enrollment`.
3. Enrollment menyimpan quota bulanan dan dua tarif:
   - tarif ke siswa
   - tarif ke tutor

Referensi:
- [app/models/enrollment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/enrollment.py:16)

### 2. Enrollment -> Attendance

1. Presensi dibuat per sesi les melalui modul attendance.
2. Saat sesi hadir, `AttendanceSession` menyimpan `tutor_fee_amount`.
3. Data attendance menjadi dasar accrual gaji tutor dan pemakaian quota siswa.

Referensi:
- [app/routes/attendance.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/attendance.py:17)
- [app/models/attendance.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/attendance.py:16)

### 3. Attendance/Enrollment -> Payment

1. Halaman pembayaran memilih siswa.
2. Frontend memanggil API enrollment aktif siswa:
   - `GET /payments/api/enrollments/<student_id>`
3. User menambahkan line pembayaran per enrollment dan `meeting_count`.
4. Route pembayaran membuat:
   - header `StudentPayment`
   - detail `StudentPaymentLine`
5. Nilai `nominal`, `tutor_payable`, dan `margin` dihitung langsung dari tarif enrollment.

Referensi:
- [app/routes/payments.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/payments.py:59)
- [app/routes/payments.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/payments.py:190)
- [app/templates/payments/form.html](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/templates/payments/form.html:510)

### 4. Payment + Attendance -> Payroll Tutor

1. Payroll summary memakai attendance sebagai dasar payable tutor per periode layanan.
2. Payout yang sudah dibayar diambil dari `TutorPayoutLine.service_month`.
3. Balance tutor per bulan = attendance payable - payout paid.
4. User bisa:
   - tambah payout manual
   - quick pay via AJAX
   - upload bukti transfer
   - generate fee slip HTML/PDF

Referensi:
- [app/routes/payroll.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/payroll.py:34)
- [app/routes/payroll.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/payroll.py:65)
- [app/templates/payroll/tutor_summary.html](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/templates/payroll/tutor_summary.html:388)

### 5. Payment + Income + Expense + Payroll -> Dashboard

Dashboard owner menyusun KPI dari beberapa sumber:

- pembayaran siswa
- pemasukan lain
- pengeluaran
- hutang gaji dari collection
- accrual gaji dari attendance
- snapshot closing bulan sebelumnya

Referensi:
- [app/routes/dashboard.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/dashboard.py:49)
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:32)

### 6. Payment Lines + Attendance -> Quota Alert dan Invoice

1. Quota paid diambil dari total `StudentPaymentLine.meeting_count` pada bulan layanan.
2. Quota used diambil dari jumlah `AttendanceSession` attended pada bulan yang sama.
3. Remaining = paid - used.
4. Jika remaining <= 0, enrollment masuk area alert dan bisa dibuat invoice.

Referensi:
- [app/routes/quota_invoice.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/quota_invoice.py:117)
- [app/routes/quota_invoice.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/quota_invoice.py:153)

## Rumus Utama

### Payment Line

- `nominal_amount = meeting_count * student_rate_per_meeting`
- `tutor_payable_amount = meeting_count * tutor_rate_per_meeting`
- `margin_amount = nominal_amount - tutor_payable_amount`

Referensi:
- [app/models/payment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/payment.py:102)

### Dashboard

- Opening balance = closing cash bulan sebelumnya
- Monthly cash flow = income + other income - expenses
- Cash balance = opening + income + other income - expenses
- Grand tutor payable = closing payable bulan sebelumnya + tutor payable from collection bulan berjalan
- Grand profit = cash balance - grand tutor payable
- Estimated remaining balance = cash balance - tutor salary accrual

Referensi:
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:32)
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:138)
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:192)

### Quota

- `paid = sum(StudentPaymentLine.meeting_count)` untuk enrollment + service_month
- `used = count(AttendanceSession)` untuk enrollment + month/year + attended
- `remaining = paid - used`

Referensi:
- [app/routes/quota_invoice.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/quota_invoice.py:127)
- [app/routes/quota_invoice.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/quota_invoice.py:138)

## Peta Halaman dan Proses

### Halaman CRUD / operasional

- Master data: students, tutors, subjects, curriculums, pricing
- Enrollment: list, add, edit, detail
- Attendance: list, add, edit, bulk-add
- Payments: list, add, detail, edit, delete, invoice, monthly summary
- Payroll: tutor summary, add payout, detail payout, transfer list, fee slip
- Quota: alerts, student detail, invoice list, invoice detail, invoice print
- Dashboard: owner, payroll, income, expense, reconciliation
- Closings: monthly closing, create closing, closing detail
- Reports: monthly, tutor, student, reconciliation, export

## Temuan Risiko dan Kemungkinan Error

### 1. Quota bulanan berisiko salah hitung karena `service_month` disimpan sebagai tanggal pembayaran penuh

Masalah:
- Saat create payment, line disimpan dengan `service_month = payment_date.date()`.
- Di quota module, service month dinormalisasi ke tanggal 1 tiap bulan lalu dibandingkan dengan equality penuh.
- Jika pembayaran dicatat pada 2026-04-29, quota query mencari 2026-04-01 dan line tidak akan terhitung.

Referensi:
- [app/routes/payments.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/payments.py:96)
- [app/routes/quota_invoice.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/quota_invoice.py:69)
- [app/routes/quota_invoice.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/quota_invoice.py:133)

Impact:
- alert quota bisa false negative / false positive
- invoice quota bisa salah jumlah
- pemakaian sesi dan pembayaran tidak sinkron

### 2. Template student detail memanggil field yang tidak ada

Masalah:
- Template memakai `pay.amount`.
- Model pembayaran hanya punya `total_amount`.
- Log runtime sudah mencatat 500 dengan `Undefined.__format__`.

Referensi:
- [app/templates/master/student_detail.html](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/templates/master/student_detail.html:322)
- [app/models/payment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/payment.py:25)
- [logs/app.log](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/logs/app.log:1591)

Impact:
- halaman detail siswa dapat gagal render ketika menampilkan riwayat pembayaran

### 3. Reconciliation memakai `created_at`, bukan periode finansial yang benar

Masalah:
- Collection payable dihitung dari `StudentPaymentLine.created_at`.
- Ini rawan beda dengan `payment_date` atau `service_month`.
- Pada tutor-level reconciliation, `StudentPaymentLine` di-join ke `AttendanceSession` hanya via `enrollment_id`, sehingga satu line bisa terduplikasi jika enrollment punya banyak attendance.

Referensi:
- [app/services/reconciliation_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/reconciliation_service.py:33)
- [app/services/reconciliation_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/reconciliation_service.py:111)

Impact:
- reconciliation bulanan dan per tutor bisa overstated / salah periode

### 4. Cash/profit dashboard belum merefleksikan cash out payout aktual

Masalah:
- `get_cash_balance()` hanya `opening + income + other_income - expenses`.
- payout tutor tidak dikurangkan dari cash balance.
- `get_grand_tutor_payable()` juga eksplisit menyatakan payout tidak dikurangkan.

Referensi:
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:151)
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:192)
- [app/services/dashboard_service.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/services/dashboard_service.py:202)

Impact:
- saldo kas dan grand profit dapat terlihat lebih tinggi dari kas riil

### 5. Closing bulanan belum benar-benar diimplementasikan

Masalah:
- route create closing masih TODO.
- detail closing hanya filter by `month`, tidak ikut `year`.

Referensi:
- [app/routes/closings.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/closings.py:31)
- [app/routes/closings.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/closings.py:44)

Impact:
- tidak ada snapshot audit yang sah
- potensi ambil closing bulan salah jika ada data lintas tahun

### 6. Modul reports sebagian besar placeholder

Masalah:
- monthly/tutor/student/reconciliation report belum mengisi data service.
- export excel/pdf belum membuat file, tapi tetap bisa mengembalikan pesan sukses.

Referensi:
- [app/routes/reports.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/reports.py:21)
- [app/routes/reports.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/reports.py:37)
- [app/routes/reports.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/reports.py:70)
- [app/routes/reports.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/reports.py:95)

Impact:
- halaman report bisa tampil tanpa data
- export memberi ekspektasi palsu

### 7. Ada banyak hard delete pada data finansial/operasional

Masalah:
- pembayaran dihapus fisik bersama line-nya.
- hasil static scan menemukan 12 titik hard delete lintas route.

Referensi:
- [app/routes/payments.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/payments.py:181)

Impact:
- audit trail hilang
- saldo/history bisa berubah tanpa jejak

### 8. Helper `Enrollment` tidak konsisten terhadap periode

Masalah:
- `get_attendance_count(month)` memakai tahun berjalan, bukan parameter tahun.
- `get_total_payable(month)` membangun filter tanggal, tetapi query sum akhirnya tidak memakai filter bulan tersebut.

Referensi:
- [app/models/enrollment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/enrollment.py:75)
- [app/models/enrollment.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/models/enrollment.py:107)

Impact:
- helper per enrollment dapat salah hitung saat lintas tahun
- total payable bisa akumulatif semua bulan, bukan bulan yang diminta

### 9. Endpoint AJAX attendance rawan 500 jika body JSON kosong/tidak valid

Masalah:
- endpoint langsung memakai `request.json.get(...)`.
- Jika `request.json` adalah `None`, route akan meledak sebelum masuk try/except.

Referensi:
- [app/routes/attendance.py](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/routes/attendance.py:223)

Impact:
- integrasi frontend atau client lain dapat menghasilkan 500 gampang

### 10. Sebagian fetch frontend rapuh terhadap error response

Masalah:
- quick pay memakai `fetch(...).then(res => res.json())` tanpa cek `res.ok` dan tanpa `.catch()`.
- jika backend mengembalikan HTML error/500, promise chain bisa putus dan UX gagal diam-diam.

Referensi:
- [app/templates/payroll/tutor_summary.html](/home/ubuntu/Documents/lembaga/aplikasi%20lembaga/app/templates/payroll/tutor_summary.html:388)

Impact:
- modal quick-pay bisa stuck
- user mendapat status UI yang tidak sinkron dengan DB

## Validasi Runtime yang Sudah Dicek

- `python3 -m compileall -q app`: lolos
- `from app import create_app; create_app()`: lolos
- blueprint terdaftar lengkap
- `pytest` belum tersedia di environment ini, jadi tidak ada test suite yang bisa dijalankan dari sandbox saat analisis

## Ringkasan Prioritas

Prioritas tertinggi:

1. Samakan definisi periode layanan:
   - `service_month`
   - `payment_date`
   - `created_at`
   - `session_date`
   - `payout_line.service_month`
2. Perbaiki quota vs payment line period mismatch
3. Perbaiki template `pay.amount`
4. Benahi reconciliation supaya tidak pakai `created_at` dan tidak double count
5. Putuskan definisi resmi cash balance vs payable vs payout
6. Implement closing bulanan sebagai snapshot audit yang benar
7. Ganti hard delete menjadi soft delete / void / reverse

