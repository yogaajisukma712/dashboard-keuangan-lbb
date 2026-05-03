# Dashboard Keuangan LBB Super Smart

Sistem pembukuan dan dashboard keuangan terintegrasi untuk Lembaga Bimbingan Belajar (LBB) Super Smart.

## 📋 Daftar Isi

- [Deskripsi Proyek](#deskripsi-proyek)
- [Fitur Utama](#fitur-utama)
- [Teknologi yang Digunakan](#teknologi-yang-digunakan)
- [Prasyarat Instalasi](#prasyarat-instalasi)
- [Instalasi](#instalasi)
- [Konfigurasi](#konfigurasi)
- [Menjalankan Aplikasi](#menjalankan-aplikasi)
- [Migrasi Server & Backup](#migrasi-server--backup)
- [Struktur Proyek](#struktur-proyek)
- [Database](#database)
- [API Endpoints](#api-endpoints)
- [Dokumentasi](#dokumentasi)

## 🎯 Deskripsi Proyek

Dashboard Keuangan LBB Super Smart adalah aplikasi web yang dirancang untuk mengelola operasional dan keuangan Lembaga Bimbingan Belajar. Sistem ini menggabungkan data operasional (siswa, tutor, jadwal les) dengan data keuangan (pembayaran, pengeluaran, gaji tutor) dalam satu platform terintegrasi.

Proyek ini merupakan migrasi dari spreadsheet Excel yang kompleks ke sistem berbasis web menggunakan Flask dan PostgreSQL.

## ✨ Fitur Utama

### 1. Manajemen Master Data
- Siswa
- Tutor
- Mata Pelajaran
- Kurikulum
- Jenjang Pendidikan
- Aturan Tarif

### 2. Manajemen Enrollment/Les
- Pendaftaran siswa untuk layanan les
- Jadwal les (hari, jam, kuota)
- Tracking pertemuan (terlaksana vs sisa)
- Status aktif/nonaktif

### 3. Presensi Tutor
- Pencatatan sesi les yang terlaksana
- Pemberian nominal fee tutor
- Rekap presensi per tutor per bulan
- Estimasi gaji tutor berdasarkan presensi

### 4. Pembayaran Siswa
- Pencatatan pembayaran siswa
- Alokasi otomatis ke hutang gaji tutor dan margin
- Riwayat pembayaran per siswa
- Laporan pemasukan bulanan

### 5. Pengeluaran
- Pencatatan semua pengeluaran operasional
- Kategorisasi pengeluaran
- Laporan pengeluaran bulanan per kategori

### 6. Payroll Tutor
- Rekap total hutang gaji per tutor
- Proses pembayaran gaji tutor
- Daftar transfer ke bank
- Riwayat pembayaran

### 7. Dashboard & Reporting
- Dashboard owner dengan KPI utama
- Dashboard payroll dengan informasi gaji tutor
- Dashboard pemasukan dengan omzet detail
- Dashboard rekonsiliasi hutang gaji
- Laporan bulanan dalam format Excel/PDF
- Grafik dan tren keuangan

### 8. Closing Bulanan
- Snapshot saldo awal/akhir bulan
- Snapshot hutang gaji awal/akhir bulan
- Lock periode untuk audit

## 🛠 Teknologi yang Digunakan

### Backend
- **Framework**: Flask 2.3.3
- **ORM**: SQLAlchemy 2.0.21
- **Database Migration**: Alembic (via Flask-Migrate)
- **Authentication**: Flask-Login

### Database
- **PostgreSQL** 12+

### Frontend
- **Template Engine**: Jinja2
- **CSS Framework**: Bootstrap 4
- **JavaScript**: jQuery
- **Charts**: Chart.js

### Additional Libraries
- **Form Handling**: WTForms
- **Validation**: Marshmallow
- **Excel Export**: openpyxl
- **PDF Generation**: ReportLab
- **Testing**: pytest, pytest-flask
- **Environment Management**: python-dotenv

## 📦 Prasyarat Instalasi

1. **Python** 3.9 atau lebih tinggi
2. **PostgreSQL** 12 atau lebih tinggi
3. **Git** (untuk version control)
4. **pip** (Python package manager)

### Verifikasi instalasi:

```bash
python --version
psql --version
git --version
```

## 🚀 Instalasi

### 1. Clone Repository
```bash
cd /path/to/projects
git clone <repository-url>
cd app_lembaga
```

### 2. Buat Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Buat Database PostgreSQL
```bash
# Windows
createdb -U postgres lbb_db

# macOS/Linux
createdb lbb_db
```

Atau melalui psql:
```bash
psql -U postgres
CREATE DATABASE lbb_db;
\q
```

### 5. Setup Environment Variables
```bash
# Copy template
cp .env.example .env

# Edit .env dengan text editor
# Sesuaikan DATABASE_URL dengan kredensial PostgreSQL Anda
```

Contoh .env:
```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-min-32-chars
DATABASE_URL=postgresql://postgres:password@localhost:5432/lbb_db
DEBUG=True
```

### 6. Initialize Database
```bash
# Buat migrasi awal (jika belum ada)
flask db init

# Generate migrasi dari models
flask db migrate -m "Initial migration"

# Apply migrasi ke database
flask db upgrade

# (Optional) Seed database dengan data awal
flask seed-db
```

## ⚙️ Konfigurasi

### File Konfigurasi Utama

**config.py** - Konfigurasi Flask global
- Base Config: Common settings
- DevelopmentConfig: Settings untuk development
- ProductionConfig: Settings untuk production
- TestingConfig: Settings untuk testing

### Environment Variables

Wajib dikonfigurasi di `.env`:

| Variable | Default | Deskripsi |
|----------|---------|-----------|
| FLASK_ENV | development | Environment mode |
| FLASK_APP | run.py | Entry point aplikasi |
| SECRET_KEY | dev-key | Secret key untuk session |
| DATABASE_URL | postgresql://... | URL koneksi database |
| DEBUG | True | Debug mode |
| LOG_LEVEL | INFO | Level logging |

## 🏃 Menjalankan Aplikasi

### Development Server
```bash
# Menggunakan flask run
flask run

# Atau direct dengan python
python run.py

# Dengan custom host dan port
flask run --host=0.0.0.0 --port=8000
```

Aplikasi akan accessible di: `http://localhost:5000`

### Database Shell
```bash
# Akses Flask shell untuk testing
flask shell

# Contoh:
>>> from app.models import Student
>>> Student.query.all()
```

### Database Commands
```bash
# Generate migration
flask db migrate -m "Deskripsi perubahan"

# Apply migration
flask db upgrade

# Revert migration
flask db downgrade

# Lihat history migration
flask db history
```

### Management Commands
```bash
# Initialize database
flask init-db

# Drop database
flask drop-db

# Seed dengan data awal
flask seed-db
```

## 🔁 Migrasi Server & Backup

Project ini menyediakan satu script eksekusi untuk migrasi ke server baru:

```bash
scripts/provision_new_server.sh
```

Script ini menyiapkan server baru dari repo GitHub:

- Clone/pull repo dari GitHub.
- Membuat `.env.docker` dari template dan mengisi secret aman.
- Membuat folder mount: `logs`, `uploads`, `backups`, `whatsapp-auth`, `deploy`.
- Membuat override compose agar sesi WhatsApp `.wwebjs_auth` persisten.
- Build semua image Docker.
- Start PostgreSQL, web, dan WhatsApp bot.
- Init schema via entrypoint app.
- Optional restore database `.sql/.sql.gz`, uploads archive, dan WhatsApp auth archive.
- Smoke check HTTP.
- Optional `CREATE_ADMIN=true`.

Contoh menjalankan di server baru:

```bash
REPO_URL=https://github.com/yogaajisukma712/dashboard-keuangan-lbb.git \
APP_DIR=/opt/billing-supersmart \
APP_BASE_URL=https://billing.supersmart.click \
bash scripts/provision_new_server.sh
```

Restore backup database:

```bash
DB_BACKUP=/path/backup.sql.gz \
FORCE_RESTORE=true \
bash scripts/provision_new_server.sh
```

Restore uploads dan session WhatsApp:

```bash
UPLOADS_ARCHIVE=/path/uploads.tgz \
WHATSAPP_AUTH_ARCHIVE=/path/whatsapp-auth.tgz \
bash scripts/provision_new_server.sh
```

Catatan penting:

- Jangan jalankan `docker compose down -v` kecuali siap menghapus database.
- Session WhatsApp juga bisa dibackup/restore dari halaman **WhatsApp Bot** di dashboard.
- Backup session WhatsApp disimpan di volume auth bot: `/app/.wwebjs_auth/_backups`.

## 📂 Struktur Proyek

```
app_lembaga/
├── app/
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── master.py        # Student, Tutor, Subject, Curriculum, Level
│   │   ├── enrollment.py    # Enrollment, EnrollmentSchedule
│   │   ├── attendance.py    # AttendanceSession
│   │   ├── payment.py       # StudentPayment, StudentPaymentLine
│   │   ├── income.py        # OtherIncome
│   │   ├── expense.py       # Expense
│   │   ├── payroll.py       # TutorPayout, TutorPayoutLine
│   │   ├── pricing.py       # PricingRule
│   │   └── closing.py       # MonthlyClosing
│   │
│   ├── routes/              # Blueprint routes
│   │   ├── auth.py
│   │   ├── master.py
│   │   ├── enrollments.py
│   │   ├── attendance.py
│   │   ├── payments.py
│   │   ├── incomes.py
│   │   ├── expenses.py
│   │   ├── payroll.py
│   │   ├── dashboard.py
│   │   ├── reports.py
│   │   └── closings.py
│   │
│   ├── services/            # Business logic
│   │   ├── dashboard_service.py
│   │   ├── enrollment_service.py
│   │   ├── attendance_service.py
│   │   ├── payment_service.py
│   │   ├── payroll_service.py
│   │   ├── reporting_service.py
│   │   └── reconciliation_service.py
│   │
│   ├── forms/               # WTForms
│   ├── templates/           # Jinja2 templates
│   ├── static/              # CSS, JS, images
│   ├── utils/               # Helper functions
│   └── __init__.py          # App factory
│
├── migrations/              # Alembic migrations
├── tests/                   # Unit tests
├── logs/                    # Application logs
├── docs/                    # Documentation
├── config.py                # Global configuration
├── run.py                   # Entry point
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .gitignore              # Git ignore rules
└── README.md                # This file
```

## 🗄️ Database

### Database Diagram (ERD)

Lihat `docs/database_schema.md` untuk ERD lengkap.

### Tabel Utama

**Master Data:**
- `users` - User aplikasi
- `students` - Data siswa
- `tutors` - Data tutor
- `subjects` - Mata pelajaran
- `curriculums` - Kurikulum
- `levels` - Jenjang pendidikan

**Operasional:**
- `enrollments` - Pendaftaran les siswa
- `enrollment_schedules` - Jadwal les
- `attendance_sessions` - Presensi sesi les

**Keuangan:**
- `student_payments` - Header pembayaran siswa
- `student_payment_lines` - Detail pembayaran
- `other_incomes` - Pemasukan lain-lain
- `expenses` - Pengeluaran
- `tutor_payouts` - Pembayaran gaji tutor
- `tutor_payout_lines` - Detail pembayaran tutor

**Reporting:**
- `monthly_closings` - Snapshot bulanan
- `pricing_rules` - Aturan tarif

### Koneksi Database

Connection string format:
```
postgresql://username:password@hostname:port/database_name
```

Contoh:
```
postgresql://postgres:mypassword@localhost:5432/lbb_db
```

## 📡 API Endpoints

### Authentication
- `POST /auth/login` - Login user
- `POST /auth/logout` - Logout user
- `GET /auth/register` - Register page
- `POST /auth/register` - Create user baru

### Master Data - Students
- `GET /master/students` - Daftar siswa
- `GET /master/students/add` - Form tambah siswa
- `POST /master/students` - Simpan siswa baru
- `GET /master/students/<id>` - Detail siswa
- `GET /master/students/<id>/edit` - Form edit siswa
- `POST /master/students/<id>` - Update siswa
- `POST /master/students/<id>/delete` - Hapus siswa

### Master Data - Tutors
- `GET /master/tutors` - Daftar tutor
- `GET /master/tutors/add` - Form tambah tutor
- `POST /master/tutors` - Simpan tutor baru
- Dan seterusnya...

### Enrollment
- `GET /enrollments` - Daftar enrollment
- `GET /enrollments/add` - Form tambah enrollment
- `POST /enrollments` - Simpan enrollment
- `GET /enrollments/<id>` - Detail enrollment
- `GET /enrollments/<id>/edit` - Edit enrollment
- `POST /enrollments/<id>/delete` - Hapus enrollment

### Attendance
- `GET /attendance` - Daftar presensi
- `GET /attendance/add` - Form input presensi
- `POST /attendance` - Simpan presensi
- `GET /attendance/monthly-summary` - Ringkasan bulanan

### Payments
- `GET /payments` - Daftar pembayaran siswa
- `GET /payments/add` - Form pembayaran
- `POST /payments` - Simpan pembayaran
- `GET /payments/<id>` - Detail pembayaran

### Payroll
- `GET /payroll/tutor-summary` - Ringkasan gaji tutor
- `GET /payroll/payout/add` - Form input payout
- `POST /payroll/payout` - Simpan payout
- `GET /payroll/transfer-list` - Daftar transfer

### Dashboard
- `GET /` atau `GET /dashboard` - Dashboard utama owner
- `GET /dashboard/payroll` - Dashboard payroll
- `GET /dashboard/income` - Dashboard pemasukan
- `GET /dashboard/reconciliation` - Dashboard rekonsiliasi

### Reports
- `GET /reports/monthly` - Laporan bulanan
- `GET /reports/tutor` - Laporan tutor
- `GET /reports/student` - Laporan siswa
- `GET /reports/export/<format>` - Export laporan

Lihat `docs/api_endpoints.md` untuk daftar lengkap.

## 📚 Dokumentasi

### File Dokumentasi

- **docs/api_endpoints.md** - Daftar lengkap API endpoints
- **docs/database_schema.md** - ERD dan struktur database
- **docs/deployment.md** - Panduan deployment ke production
- **docs/user_guide.md** - Manual penggunaan aplikasi

### Panduan Pengembang

1. Baca `context_dashboard_keuangan_lbb_super_smart.txt` untuk memahami logika bisnis
2. Baca `project_structure_dan_setup_flask.txt` untuk struktur project
3. Ikuti naming conventions di dokumentasi
4. Ikuti best practices di dokumentasi

## 🧪 Testing

### Menjalankan Tests
```bash
# Run semua tests
pytest

# Run dengan verbose
pytest -v

# Run dengan coverage report
pytest --cov

# Run specific test file
pytest tests/test_models.py

# Run specific test function
pytest tests/test_models.py::test_student_model
```

### Struktur Test
```
tests/
├── __init__.py
├── conftest.py           # Fixtures and config
├── test_models.py        # Model tests
├── test_routes.py        # Route tests
└── test_services.py      # Service tests
```

## 📖 Konvensi Koding

### Python
- PEP 8 untuk style guide
- camelCase untuk functions dan variables
- PascalCase untuk class names

### Database
- lowercase dengan underscore untuk table names
- lowercase dengan underscore untuk column names
- `{table}_id` untuk foreign keys

### Routes
- kebab-case untuk URL paths
- snake_case untuk function names

### Git
- Commit message: "feat: deskripsi" atau "fix: deskripsi"
- Branch naming: feature/nama-fitur atau bugfix/nama-bug

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/nama-fitur`
2. Commit changes: `git commit -m "feat: deskripsi"`
3. Push ke branch: `git push origin feature/nama-fitur`
4. Open Pull Request

## 📝 License

Proprietary - LBB Super Smart

## 👥 Support

Untuk pertanyaan atau issues, hubungi tim development.

---

**Last Updated:** 2024
**Version:** 1.0.0
