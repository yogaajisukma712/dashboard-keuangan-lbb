# Setup Guide - Dashboard Keuangan LBB Super Smart

Panduan lengkap untuk setup dan menjalankan aplikasi Flask Dashboard Keuangan LBB Super Smart.

## Prasyarat

Sebelum memulai, pastikan Anda sudah menginstal:

1. **Python 3.9+**
   ```bash
   python --version
   ```

2. **PostgreSQL 12+**
   ```bash
   psql --version
   ```

3. **Git** (untuk version control)
   ```bash
   git --version
   ```

4. **pip** (Python package manager - biasanya sudah terinstal dengan Python)
   ```bash
   pip --version
   ```

## Langkah-Langkah Setup

### 1. Clone Repository atau Setup Folder

Jika menggunakan Git:
```bash
cd C:\Users\desip\OneDrive\Documents\Lembaga\App Lembaga
git clone <repository-url>
cd app_lembaga
```

Atau jika sudah ada folder:
```bash
cd C:\Users\desip\OneDrive\Documents\Lembaga\App Lembaga\app_lembaga
```

### 2. Buat Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Verifikasi virtual environment aktif (akan melihat `(.venv)` di command prompt):
```bash
python --version
```

### 3. Upgrade pip dan Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Tunggu hingga semua package selesai terinstal. Ini mungkin memakan waktu beberapa menit.

### 4. Setup Database PostgreSQL

#### 4.1. Buat Database

**Windows (Command Prompt/PowerShell):**
```bash
createdb -U postgres lbb_db
```

Atau melalui psql:
```bash
psql -U postgres
CREATE DATABASE lbb_db;
\q
```

**macOS/Linux:**
```bash
createdb lbb_db
```

Atau:
```bash
psql
CREATE DATABASE lbb_db;
\q
```

#### 4.2. Verifikasi Database Terbuat

```bash
psql -U postgres -d lbb_db -c "SELECT 1;"
```

Seharusnya menampilkan hasil tanpa error.

### 5. Setup Environment Variables

#### 5.1. Copy Template

```bash
cp .env.example .env
```

#### 5.2. Edit File .env

Buka file `.env` dengan text editor favorit Anda dan sesuaikan:

```env
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-very-secret-key-min-32-characters-long
DATABASE_URL=postgresql://postgres:password@localhost:5432/lbb_db
DEBUG=True
LOG_LEVEL=INFO
PAGINATION_PER_PAGE=20
```

**Penting:** Ganti `password` dengan password PostgreSQL Anda.

Contoh:
```env
DATABASE_URL=postgresql://postgres:MyPassword123@localhost:5432/lbb_db
```

### 6. Initialize Database dengan Flask-Migrate

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

Jika sudah ada folder `migrations`, skip langkah `flask db init`.

### 7. Seed Database (Optional)

Untuk menambahkan data awal:

```bash
flask seed-db
```

Ini akan menambahkan:
- 3 Kurikulum: Nasional, Internasional, Cambridge
- 4 Jenjang: TK, SD, SMP, SMA
- 5 Mata Pelajaran: Matematika, Bahasa Indonesia, Bahasa Inggris, IPA, IPS

### 8. Jalankan Aplikasi

```bash
flask run
```

Atau:

```bash
python run.py
```

Aplikasi akan berjalan di: **http://localhost:5000**

## Login Pertama

Setelah aplikasi berjalan, Anda perlu membuat user admin terlebih dahulu.

### Cara 1: Menggunakan Flask Shell

```bash
flask shell
```

Kemudian di Python shell:

```python
from app import db
from app.models import User

# Buat user admin
admin = User(
    username='admin',
    email='admin@lbb.com',
    full_name='Administrator',
    role='admin',
    is_active=True
)
admin.set_password('admin123')

db.session.add(admin)
db.session.commit()

print("Admin user created successfully!")
exit()
```

### Cara 2: Langsung di Browser (Jika Register Route Aktif)

1. Buka http://localhost:5000/auth/register
2. Isi form registrasi
3. Login dengan user yang baru dibuat

### Login

- URL: http://localhost:5000/auth/login
- Username: `admin`
- Password: `admin123`

## Struktur Folder

```
app_lembaga/
├── app/                    # Main application package
│   ├── models/            # Database models
│   ├── routes/            # Route blueprints
│   ├── services/          # Business logic
│   ├── forms/             # WTForms
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS, images
│   └── utils/             # Utilities
├── migrations/            # Flask-Migrate versions
├── tests/                 # Unit tests
├── logs/                  # Application logs
├── .env                   # Environment variables (jangan commit!)
├── .env.example           # Template environment
├── requirements.txt       # Python dependencies
├── config.py              # Flask configuration
├── run.py                 # Application entry point
└── README.md              # Project documentation
```

## Troubleshooting

### Problem: ModuleNotFoundError: No module named 'app'

**Solusi:**
Pastikan Anda berada di folder `app_lembaga` dan virtual environment aktif.

```bash
cd app_lembaga
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
```

### Problem: Database connection refused

**Solusi:**
- Pastikan PostgreSQL running
- Check DATABASE_URL di .env sudah benar
- Verifikasi username dan password PostgreSQL

```bash
psql -U postgres -c "SELECT 1;"
```

### Problem: Port 5000 already in use

**Solusi:**
Gunakan port berbeda:

```bash
flask run --port 5001
```

### Problem: Secret key not set

**Solusi:**
Pastikan `SECRET_KEY` ada di .env file dengan minimal 32 karakter.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Gunakan output di atas sebagai SECRET_KEY.

### Problem: Tables not created

**Solusi:**
```bash
flask db upgrade
```

Jika masih tidak muncul:
```bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
```

## Development Commands

### Menjalankan aplikasi dengan debug

```bash
flask run
```

atau

```bash
python run.py
```

### Membuat migration baru setelah edit model

```bash
flask db migrate -m "Deskripsi perubahan"
flask db upgrade
```

### Masuk ke Python shell dengan app context

```bash
flask shell
```

### Menjalankan tests

```bash
pytest
pytest -v
pytest --cov
```

### Membuat user baru

```bash
flask shell
>>> from app import db
>>> from app.models import User
>>> user = User(username='user', email='user@lbb.com', full_name='User Name', role='user')
>>> user.set_password('password123')
>>> db.session.add(user)
>>> db.session.commit()
>>> exit()
```

## Deployment ke Production

Untuk production, lihat file `docs/deployment.md`.

Secara singkat:
1. Ubah `FLASK_ENV=production`
2. Gunakan production database
3. Setup SSL certificate
4. Gunakan production WSGI server (Gunicorn, uWSGI)
5. Setup reverse proxy (Nginx)

## Bantuan dan Support

Jika ada error atau pertanyaan:
1. Baca file `README.md` untuk overview
2. Cek `docs/` folder untuk dokumentasi detail
3. Lihat context files:
   - `context_dashboard_keuangan_lbb_super_smart.txt`
   - `project_structure_dan_setup_flask.txt`

## Verifikasi Setup Berhasil

Jika semua langkah di atas berhasil:

1. ✅ Aplikasi berjalan di http://localhost:5000
2. ✅ Bisa login dengan username admin
3. ✅ Dashboard menampilkan data kosong (normal untuk setup baru)
4. ✅ Tidak ada error di console

Selamat! Aplikasi Dashboard Keuangan LBB Super Smart siap digunakan.

---

**Last Updated:** 2024
**Version:** 1.0.0