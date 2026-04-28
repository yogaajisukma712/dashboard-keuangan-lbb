# Audit & Remediation Plan
## Dashboard Keuangan LBB Super Smart

Dokumen ini merangkum hasil audit menyeluruh dan mengubahnya menjadi rencana perbaikan bertahap yang bisa dieksekusi.

## Tujuan
1. Menstabilkan aplikasi agar bisa boot dan dipakai tanpa error runtime dasar.
2. Memastikan semua angka keuangan dihitung konsisten dari transaksi dasar.
3. Menghilangkan logic yang janggal, rapuh, atau mematahkan audit trail.
4. Membuat seluruh variabel bisnis penting menjadi dinamis melalui master data atau form transaksi.
5. Menyiapkan fondasi yang layak untuk migrasi, testing, dan deployment.

---

# Prinsip Perbaikan

## 1. Bedakan jenis variabel
### A. Master-data driven
Harus bisa diatur via CRUD:
- User
- Role
- Level
- Curriculum
- Subject
- Student
- Tutor
- PricingRule
- EnrollmentSchedule
- ExpenseCategory
- IncomeCategory
- PaymentMethod
- ClosingPeriod / MonthlyClosing

### B. Transaction-input driven
Harus diinput via form transaksi, bukan hardcoded:
- AttendanceSession
- StudentPayment
- StudentPaymentLine
- OtherIncome
- Expense
- TutorPayout
- TutorPayoutLine

### C. System-derived
Tidak boleh diedit manual:
- nominal_amount
- tutor_payable_amount
- margin_amount
- profit
- cash_balance
- grand_profit
- verified_at
- closed_at
- opening/closing snapshot hasil proses closing

## 2. Transaksi finansial tidak boleh hard delete
Semua transaksi keuangan harus diarahkan ke:
- void / cancel / inactive / reversed
- bukan `delete` fisik

## 3. Semua perhitungan bulanan harus sadar periode
Setiap query bulanan harus selalu mempertimbangkan:
- month
- year
- service period yang benar
- carry-forward opening/closing bila relevan

## 4. Snapshot closing adalah kontrol audit
Closing bulanan harus menjadi:
- sumber opening balance bulan berikutnya
- kontrol edit transaksi lintas periode
- jejak audit hasil akhir bulan

---

# Ringkasan Temuan Audit

## Blocker runtime
- Folder `templates` tidak ada
- Relasi ORM attendance/tutor bermasalah
- `AttendanceSession.tutor_id` belum mapped secara benar
- Redirect auth menuju endpoint yang tidak ada
- `IncomeForm` tidak diexport
- `current_user` dipakai tanpa import
- Migrations belum ada

## Logic keuangan bermasalah
- Cash balance tidak mengurangi tutor payout
- Grand tutor payable salah lintas tahun
- Opening balance logic tertukar
- Reconciliation memakai basis tanggal yang salah
- Reconciliation per tutor berisiko double count
- Payment header tidak divalidasi terhadap payment lines
- Payout header bisa tercatat tanpa line payout
- Historis tutor attribution tidak stabil
- Helper helper bulanan tidak konsisten terhadap year

## CRUD/master-data belum lengkap
- User management belum ada
- Level CRUD belum ada
- EnrollmentSchedule CRUD belum ada
- StudentPaymentLine CRUD belum sehat
- TutorPayoutLine CRUD belum ada
- MonthlyClosing belum operasional
- Expense category hardcoded
- Income category hardcoded
- Payment method hardcoded dan inkonsisten
- Identity type hardcoded
- PricingRule belum menjadi sumber utama rate/quota
- service_month line pembayaran belum benar-benar dinamis

---

# Tahapan Remediasi

# Stage 0 — Freeze & Safety Baseline
## Tujuan
Mencegah kerusakan tambahan saat refactor besar dilakukan.

## Checklist
- [ ] Hentikan perubahan acak di banyak area sekaligus
- [ ] Tetapkan urutan kerja bertahap
- [ ] Identifikasi transaksi yang sementara tidak boleh dihapus
- [ ] Dokumentasikan semua model, service, route, dan form yang saat ini aktif
- [ ] Pastikan semua perubahan berikutnya mengikuti satu sumber desain

## Output
- baseline audit
- backlog kerja prioritas
- scope refactor yang jelas

---

# Stage 1 — Runtime Stabilization
## Tujuan
Membuat app bisa start, login, dan membuka route dasar tanpa error struktural.

## 1.1 Perbaiki auth flow
### Masalah
- redirect ke endpoint dashboard yang tidak ada
- register route terlalu terbuka

### Tindakan
- [ ] Ganti redirect `dashboard.index` ke endpoint dashboard yang valid
- [ ] Rapikan logic `next` redirect
- [ ] Tentukan mode register:
  - bootstrap only
  - admin-only
  - atau nonaktifkan public register untuk production

### Selesai jika
- login berhasil
- logout berhasil
- redirect pasca-login valid

## 1.2 Perbaiki import/runtime bug route
### Tindakan
- [ ] Export `IncomeForm` dari package forms
- [ ] Import `current_user` di route income/expense yang memakainya
- [ ] Audit seluruh route untuk import yang tidak lengkap
- [ ] Audit endpoint yang me-render template

### Selesai jika
- route incomes/expenses tidak crash karena import
- form bisa dipanggil dengan benar

## 1.3 Lengkapi struktur Flask minimum
### Tindakan
- [ ] Tambahkan `app/templates/`
- [ ] Tambahkan `app/static/`
- [ ] Tambahkan placeholder template minimum agar route tidak `TemplateNotFound`
- [ ] Tambahkan halaman login, register, dashboard, dan form dasar yang benar-benar dipakai

### Selesai jika
- route GET utama tidak gagal karena template hilang

## 1.4 Tambahkan CSRF protection
### Tindakan
- [ ] Inisialisasi proteksi CSRF global
- [ ] Pastikan semua form WTForms dirender dengan token CSRF
- [ ] Audit route yang masih bypass WTForms

### Selesai jika
- seluruh form penting lewat validasi yang konsisten

---

# Stage 2 — ORM & Data Model Repair
## Tujuan
Membuat relasi antar entitas sehat, queryable, dan stabil.

## 2.1 Perbaiki model `AttendanceSession`
### Masalah
- `tutor_id` hanya property, bukan mapped column
- relasi `tutor` tidak aman untuk query
- histori tutor bisa berubah jika enrollment diubah

### Tindakan
- [ ] Tambahkan kolom snapshot yang dibutuhkan untuk attendance:
  - `tutor_id`
  - `student_id`
  - `subject_id` bila diperlukan sebagai snapshot
- [ ] Pastikan relasi memakai foreign key yang jelas
- [ ] Saat attendance dibuat, isi nilai snapshot dari enrollment aktif saat itu
- [ ] Evaluasi apakah `subject_id` tetap perlu di-form atau harus auto dari enrollment

### Selesai jika
- semua query attendance by tutor berjalan aman
- histori attendance tidak berubah hanya karena enrollment berubah

## 2.2 Hilangkan relationship yang ganda/konflik
### Tindakan
- [ ] Pilih satu pola relasi yang konsisten:
  - `backref`, atau
  - `back_populates`
- [ ] Rapikan pasangan:
  - Enrollment ↔ AttendanceSession
  - Enrollment ↔ StudentPaymentLine
  - Subject ↔ AttendanceSession
  - Tutor ↔ AttendanceSession
- [ ] Audit semua model agar tidak ada definisi dua arah yang saling tumpang tindih

### Selesai jika
- mapper SQLAlchemy stabil
- tidak ada query yang bergantung pada property Python untuk filter SQL

## 2.3 Audit uniqueness & integrity
### Tindakan
- [ ] Tambahkan constraint unik yang diperlukan
- [ ] Pertimbangkan unique per:
  - closing `(month, year)`
  - attendance `(enrollment_id, session_date)` bila sesuai
  - pricing rule aktif bila diperlukan aturan prioritas
- [ ] Tambahkan index untuk field period/filter penting

### Selesai jika
- tidak ada duplikasi transaksi yang mudah masuk tanpa kontrol

---

# Stage 3 — Financial Logic Correction
## Tujuan
Memastikan angka dashboard, payroll, reconciliation, dan report tidak janggal.

## 3.1 Perbaiki cash logic
### Tindakan
- [ ] Ubah `cash_balance` agar mengurangi `TutorPayout`
- [ ] Tentukan dengan tegas apakah cash memakai:
  - payout header date
  - atau payout line service month
- [ ] Pisahkan konsep:
  - cash movement
  - accrued payable
  - margin
  - profit

### Selesai jika
- saldo kas mencerminkan uang benar-benar keluar

## 3.2 Perbaiki opening/closing balance logic
### Tindakan
- [ ] Definisikan aturan resmi:
  - opening bulan N = closing bulan N-1
  - jika tidak ada closing sebelumnya, gunakan opening default/seed
- [ ] Ubah helper opening balance agar tidak memakai closing bulan yang sama
- [ ] Hubungkan helper dashboard ke snapshot closing dengan benar

### Selesai jika
- saldo awal dan saldo akhir konsisten lintas bulan

## 3.3 Perbaiki grand tutor payable lintas periode
### Tindakan
- [ ] Ganti filter `month <= ...` dan `year <= ...` yang berdiri sendiri
- [ ] Gunakan perbandingan periode yang benar
- [ ] Tentukan apakah grand payable dihitung dari:
  - cumulative collection allocation minus payouts
  - atau opening payable plus current movement minus payout

### Selesai jika
- hutang tutor lintas tahun tidak salah

## 3.4 Perbaiki reconciliation logic
### Tindakan
- [ ] Jangan gunakan `StudentPaymentLine.created_at` sebagai dasar periode finansial
- [ ] Gunakan `StudentPayment.payment_date` atau `service_month` yang benar
- [ ] Hindari join yang menyebabkan payment line terhitung berulang karena banyak attendance
- [ ] Definisikan secara resmi:
  - payable from collection
  - accrual from attendance
  - payout actual
  - gap
- [ ] Pastikan tutor-level reconciliation tidak double count

### Selesai jika
- angka reconciliation global dan per tutor bisa diaudit

## 3.5 Perbaiki helper bulanan
### Tindakan
- [ ] Tambahkan parameter `year` pada helper yang belum konsisten
- [ ] Audit seluruh method `get_total_*`, `get_balance`, `get_attendance_count`, `get_total_paid`, `get_total_payable`
- [ ] Hindari implicit current year untuk query histori

### Selesai jika
- Januari tahun lalu dan Januari tahun ini tidak bercampur

---

# Stage 4 — Transaction Integrity & Audit Trail
## Tujuan
Membuat transaksi aman, konsisten, dan bisa ditelusuri.

## 4.1 Payment integrity
### Tindakan
- [ ] Validasi `StudentPayment.total_amount == sum(StudentPaymentLine.nominal_amount)`
- [ ] Validasi enrollment line benar-benar milik student yang dipilih
- [ ] Pisahkan edit header dan edit line dengan workflow yang jelas
- [ ] Jadikan `service_month` per line sebagai input eksplisit
- [ ] Tambahkan verification workflow:
  - `is_verified`
  - `verified_by`
  - `verified_at`

### Selesai jika
- pembayaran tidak bisa disimpan dengan header-line mismatch

## 4.2 Attendance integrity
### Tindakan
- [ ] Cegah duplikasi attendance untuk enrollment dan tanggal yang sama
- [ ] Rapikan bulk attendance agar input string diparse menjadi list ID valid
- [ ] Pastikan fee tutor default berasal dari enrollment/pricing, bukan entry bebas tanpa kontrol
- [ ] Tambahkan status lifecycle:
  - scheduled
  - attended
  - cancelled
  - rescheduled

### Selesai jika
- attendance tidak mudah duplikat dan tidak mengacaukan payroll

## 4.3 Payroll integrity
### Tindakan
- [ ] Wajibkan payout line jika payout dicatat untuk periode tertentu
- [ ] Tambahkan validasi overpayment
- [ ] Tambahkan validasi duplicate payout untuk periode yang sama
- [ ] Bedakan:
  - cash payout event
  - alokasi payout ke service period
- [ ] Tambahkan status payout yang benar:
  - draft
  - completed
  - voided

### Selesai jika
- payout tidak bisa masuk setengah jadi

## 4.4 Soft-delete / void workflow
### Tindakan
- [ ] Ganti hard delete transaksi finansial dengan void/cancel
- [ ] Tambahkan reason/note bila transaksi dibatalkan
- [ ] Lindungi transaksi yang sudah masuk closing

### Selesai jika
- histori finansial tidak hilang diam-diam

---

# Stage 5 — Dynamic Master Data Completion
## Tujuan
Membuat semua variabel bisnis penting menjadi dinamis, bukan hardcoded.

## 5.1 Tambahkan CRUD yang hilang
### Wajib
- [ ] User Management
- [ ] Level CRUD
- [ ] EnrollmentSchedule CRUD
- [ ] MonthlyClosing CRUD/workflow
- [ ] ExpenseCategory CRUD
- [ ] IncomeCategory CRUD
- [ ] PaymentMethod CRUD

### Opsional tapi disarankan
- [ ] IdentityType master
- [ ] Bank master/reference

## 5.2 Jadikan PricingRule benar-benar sumber utama
### Tindakan
- [ ] Enrollment form memilih kombinasi student context:
  - curriculum
  - level
  - subject
  - grade
- [ ] Sistem mengambil default:
  - student_rate_per_meeting
  - tutor_rate_per_meeting
  - default_meeting_quota
- [ ] Jika override diperbolehkan:
  - simpan flag override
  - catat siapa yang override
  - wajib alasan override

### Selesai jika
- rate dan kuota tidak lagi hardcoded/manual by default

## 5.3 Standardisasi master pilihan
### Tindakan
- [ ] Hilangkan hardcoded category di form income/expense
- [ ] Hilangkan hardcoded payment method yang inkonsisten
- [ ] Satukan vocab:
  - `cash` vs `tunai`
  - `check` vs `cek`
- [ ] Tetapkan satu naming convention resmi

### Selesai jika
- pilihan bisnis tersentralisasi dan konsisten

---

# Stage 6 — Form & CRUD Completion
## Tujuan
Menjamin setiap entitas penting punya alur CRUD/form yang sehat.

## 6.1 Student/Tutor lifecycle completion
### Tindakan
- [ ] Tambahkan pengelolaan:
  - `status`
  - `is_active`
- [ ] Ganti delete master menjadi deactivate bila punya histori transaksi

## 6.2 PricingRule lifecycle completion
### Tindakan
- [ ] Form untuk:
  - `is_active`
  - `active_from`
  - `active_to`
- [ ] Definisikan prioritas rule jika lebih dari satu cocok

## 6.3 Enrollment lifecycle completion
### Tindakan
- [ ] Form/route untuk:
  - `start_date`
  - `end_date`
  - `status`
  - `is_active`
- [ ] Tambahkan CRUD schedule per enrollment

## 6.4 Payment line management
### Tindakan
- [ ] Buat line-item form/CRUD yang nyata
- [ ] Jangan bergantung pada raw array form tanpa validasi object-level
- [ ] Pisahkan create/edit/remove line dengan validasi total

## 6.5 Tutor payout line management
### Tindakan
- [ ] Tambahkan line-item CRUD
- [ ] Tambahkan note per line
- [ ] Dukung payout multi-service-month secara benar

## 6.6 Monthly closing workflow
### Tindakan
- [ ] Tambahkan form create closing
- [ ] Tambahkan form detail/review
- [ ] Tambahkan reopen/void flow bila bisnis mengizinkan
- [ ] Tambahkan lock period behavior

---

# Stage 7 — Reporting & Closing Implementation
## Tujuan
Membuat dashboard dan report benar-benar menjadi hasil otomatis dari transaksi dasar.

## 7.1 Implement report routes
### Tindakan
- [ ] Hubungkan `reports.py` ke `ReportingService`
- [ ] Selesaikan:
  - monthly report
  - tutor report
  - student report
  - reconciliation report
- [ ] Pastikan definisi angka konsisten dengan dashboard service

## 7.2 Implement export
### Tindakan
- [ ] Excel export
- [ ] PDF export
- [ ] Penamaan file berbasis period/type
- [ ] Pastikan sumber data terstandardisasi

## 7.3 Implement closing bulanan
### Tindakan
- [ ] Hitung otomatis:
  - opening cash
  - opening tutor payable
  - total income
  - total expense
  - total tutor salary/accrual
  - total margin
  - closing cash
  - closing tutor payable
  - closing profit
- [ ] Simpan snapshot
- [ ] Lock period

### Selesai jika
- dashboard bulanan dan laporan bisa diaudit dari closing

---

# Stage 8 — Migration, Seed, and Deployment Hygiene
## Tujuan
Membuat perubahan model aman untuk deployment jangka panjang.

## 8.1 Tambahkan migrations
### Tindakan
- [ ] Inisialisasi migration repository
- [ ] Buat migration awal dari schema yang sudah dibersihkan
- [ ] Buat migration untuk field baru seperti attendance snapshots/master data baru

## 8.2 Seed data minimum
### Tindakan
- [ ] Seed:
  - curriculum
  - level
  - subject
  - payment method
  - expense category
  - income category
  - admin user
- [ ] Hilangkan ketergantungan pada script admin hardcoded yang tidak aman

## 8.3 Samakan strategi schema
### Tindakan
- [ ] Hapus ketergantungan `db.create_all()` untuk production
- [ ] Gunakan migration sebagai sumber resmi schema evolution
- [ ] Samakan local, Docker, dan deploy flow

---

# Stage 9 — Testing & Regression Safety
## Tujuan
Mencegah perbaikan merusak logic lain.

## 9.1 Tambahkan test structure
### Tindakan
- [ ] Tambahkan folder `tests/`
- [ ] Buat fixtures app/db
- [ ] Tambahkan test auth
- [ ] Tambahkan test model integrity
- [ ] Tambahkan test finance calculation

## 9.2 Test yang wajib ada
### Auth
- [ ] login
- [ ] logout
- [ ] register restrictions
- [ ] role guard

### Attendance
- [ ] create attendance
- [ ] duplicate prevention
- [ ] tutor snapshot persistence

### Payments
- [ ] header-line total validation
- [ ] wrong-student enrollment rejection
- [ ] service_month per line

### Payroll
- [ ] payout requires valid service allocation
- [ ] no overpayment
- [ ] balance reduction consistent

### Reconciliation
- [ ] no double count
- [ ] tutor-level reconciliation correct
- [ ] month/year correctness

### Closing
- [ ] opening follows previous closing
- [ ] period locked after close
- [ ] transactions blocked or controlled after close

---

# Urutan Eksekusi yang Direkomendasikan

## Sprint 1
Fokus:
- Stage 1
- Stage 2

Output:
- app bisa boot
- auth flow valid
- route income/expense tidak crash
- ORM stabil
- attendance query by tutor sehat

## Sprint 2
Fokus:
- Stage 3
- Stage 4

Output:
- dashboard, payroll, reconciliation logic benar
- transaction integrity meningkat
- hard delete mulai dihilangkan

## Sprint 3
Fokus:
- Stage 5
- Stage 6

Output:
- master data dinamis lengkap
- CRUD entitas penting lengkap
- pricing benar-benar driving enrollment/attendance

## Sprint 4
Fokus:
- Stage 7
- Stage 8
- sebagian Stage 9

Output:
- report dan closing hidup
- migrations siap
- deployment flow rapi

## Sprint 5
Fokus:
- penyempurnaan Stage 9

Output:
- regression tests untuk core finance flows
- baseline quality untuk perubahan berikutnya

---

# Definisi Selesai per Domain

## Domain Auth selesai jika
- login/logout aman
- register dibatasi sesuai kebijakan
- redirect valid
- user management admin tersedia

## Domain Attendance selesai jika
- attendance tersimpan dengan tutor/student snapshot
- tidak double
- bulk input valid
- filter tutor valid

## Domain Payments selesai jika
- total header selalu cocok dengan lines
- line per service_month valid
- verification workflow ada
- tidak bisa salah student↔enrollment

## Domain Payroll selesai jika
- payout tidak bisa tanpa alokasi yang sah
- unpaid balance benar
- overpayment dicegah
- payout tidak tercatat setengah jadi

## Domain Reconciliation selesai jika
- tidak double count
- periode benar
- global dan tutor-level konsisten

## Domain Closing selesai jika
- closing tersimpan per month-year unik
- opening bulan berikutnya benar
- period lock berjalan
- report/dashboard sinkron dengan snapshot

---

# Prioritas Tertinggi
1. ORM attendance/tutor
2. auth redirect dan bug import route
3. templates minimum agar app bisa dilihat
4. cash/payable/reconciliation correction
5. payment and payout integrity
6. closing bulanan
7. dynamic master data completion
8. migrations and tests

---

# Catatan Penting
- Jangan mengerjakan semua sekaligus.
- Jangan mulai dari report sebelum model dan logic finansial stabil.
- Jangan menambah fitur UI besar sebelum relasi data sehat.
- Jangan mengaktifkan production deployment sebelum:
  - migrations ada
  - auth aman
  - closing minimal hidup
  - test core finance flow ada

---

# Deliverable Akhir yang Ditargetkan
- aplikasi bisa boot dan dipakai
- ORM stabil
- semua perhitungan finansial utama konsisten
- semua variabel bisnis penting dinamis
- transaksi memiliki audit trail
- closing bulanan operasional
- migration flow resmi tersedia
- test suite dasar tersedia
- deployment Docker/production konsisten dengan schema strategy
