# Docker Deployment Guide

Panduan ini membantu Anda menjalankan **Dashboard Keuangan LBB Super Smart** di Docker pada laptop, VPS, atau server lokal Anda.

## File Docker yang Sudah Disiapkan

Project ini sudah memiliki file berikut:

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `docker/entrypoint.sh`
- `docker/wait_for_db.py`
- `.env.docker.example`

## Arsitektur Container

Stack Docker ini terdiri dari 2 service:

1. **`web`**
   - Menjalankan aplikasi Flask dengan `gunicorn`
   - Port default: `5000`

2. **`db`**
   - Menjalankan PostgreSQL
   - Port default: `5432`

Saat container `web` start:

- aplikasi menunggu database siap
- koneksi database diuji
- schema database diinisialisasi dengan `db.create_all()`
- lalu aplikasi dijalankan dengan `gunicorn`

## Prasyarat

Pastikan server Anda sudah terpasang:

- Docker
- Docker Compose plugin

Cek dengan:

```/dev/null/check.sh#L1-2
docker --version
docker compose version
```

## 1. Masuk ke Folder Project

```/dev/null/cd.sh#L1-1
cd "aplikasi lembaga"
```

## 2. Siapkan Environment File

Copy file contoh environment:

```/dev/null/env-copy.sh#L1-1
cp .env.docker.example .env.docker
```

Lalu edit `.env.docker` dan sesuaikan nilainya.

Contoh minimal:

```/dev/null/example.env#L1-15
FLASK_APP=run.py
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
PORT=5000
DEBUG=False

SECRET_KEY=ganti-dengan-random-secret-yang-panjang-dan-aman

POSTGRES_DB=lbb_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=ganti-password-db-yang-kuat

LOG_LEVEL=INFO
PAGINATION_PER_PAGE=20
GUNICORN_WORKERS=4
```

## 3. Jalankan Docker Compose

Jalankan stack:

```/dev/null/up.sh#L1-1
docker compose --env-file .env.docker up -d --build
```

Perintah ini akan:

- build image aplikasi
- membuat container `web`
- membuat container `db`
- membuat volume PostgreSQL persisten
- menjalankan app di background

## 4. Cek Status Container

```/dev/null/ps.sh#L1-1
docker compose --env-file .env.docker ps
```

## 5. Lihat Log Aplikasi

```/dev/null/logs.sh#L1-1
docker compose --env-file .env.docker logs -f web
```

Untuk log database:

```/dev/null/logs-db.sh#L1-1
docker compose --env-file .env.docker logs -f db
```

## 6. Akses Aplikasi

Secara default aplikasi bisa diakses di:

```/dev/null/url.txt#L1-1
http://localhost:5000
```

Jika deploy di VPS, ganti `localhost` dengan IP/domain server Anda:

```/dev/null/url-vps.txt#L1-1
http://IP-SERVER-ANDA:5000
```

## 7. Stop Container

```/dev/null/down.sh#L1-1
docker compose --env-file .env.docker down
```

Jika Anda juga ingin menghapus volume database:

```/dev/null/down-volumes.sh#L1-1
docker compose --env-file .env.docker down -v
```

> `down -v` akan menghapus seluruh data PostgreSQL di volume Docker.

## 8. Update Aplikasi Setelah Pull Perubahan

Kalau ada perubahan code dari repository:

```/dev/null/update.sh#L1-3
git pull
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker logs -f web
```

## 9. Menjalankan Ulang Service

Restart semua service:

```/dev/null/restart.sh#L1-1
docker compose --env-file .env.docker restart
```

Restart hanya aplikasi:

```/dev/null/restart-web.sh#L1-1
docker compose --env-file .env.docker restart web
```

## 10. Masuk ke Container

Masuk ke shell container aplikasi:

```/dev/null/exec-web.sh#L1-1
docker compose --env-file .env.docker exec web sh
```

Masuk ke PostgreSQL:

```/dev/null/exec-db.sh#L1-1
docker compose --env-file .env.docker exec db psql -U postgres -d lbb_db
```

Jika username atau database Anda berbeda, sesuaikan parameternya.

## 11. Membuat Admin Pertama

Project ini memiliki file `create_admin.py`.

Setelah container berjalan, Anda bisa membuat admin dengan:

```/dev/null/create-admin.sh#L1-1
docker compose --env-file .env.docker exec web python create_admin.py
```

Default credential dari script tersebut:

```/dev/null/admin.txt#L1-2
Username: admin
Password: admin123456
```

Setelah berhasil login, **segera ganti password admin**.

## 12. Port yang Bisa Diubah

Nilai berikut bisa Anda ubah di `.env.docker`:

```/dev/null/ports.env#L1-4
APP_PORT=5000
POSTGRES_PORT=5432
FLASK_PORT=5000
PORT=5000
```

Contoh jika ingin app di port `8080`:

```/dev/null/app-port.env#L1-1
APP_PORT=8080
```

Lalu jalankan ulang:

```/dev/null/reup.sh#L1-1
docker compose --env-file .env.docker up -d --build
```

Aplikasi akan tersedia di:

```/dev/null/url-8080.txt#L1-1
http://localhost:8080
```

## 13. Deploy di Server dengan Domain

Jika Anda ingin pakai domain, biasanya alurnya:

1. jalankan app di Docker pada port internal
2. pasang Nginx atau Traefik sebagai reverse proxy
3. arahkan domain ke server
4. pasang SSL dengan Let's Encrypt

Contoh sederhana reverse proxy:
- domain `app.domainanda.com`
- Nginx meneruskan request ke `127.0.0.1:5000`

## 14. Backup Database

Backup database dari container:

```/dev/null/backup.sh#L1-1
docker compose --env-file .env.docker exec db pg_dump -U postgres -d lbb_db > backup.sql
```

Restore:

```/dev/null/restore.sh#L1-1
cat backup.sql | docker compose --env-file .env.docker exec -T db psql -U postgres -d lbb_db
```

## 15. Troubleshooting

### A. Container `web` restart terus

Cek log:

```/dev/null/troubleshoot-web.sh#L1-1
docker compose --env-file .env.docker logs --tail=200 web
```

Kemungkinan penyebab:
- `SECRET_KEY` belum diisi dengan benar
- konfigurasi database salah
- ada error import Python
- dependency belum sesuai
- ada file template yang belum ikut ke repository

### B. Tidak bisa konek ke PostgreSQL

Cek status database:

```/dev/null/troubleshoot-db.sh#L1-1
docker compose --env-file .env.docker logs --tail=200 db
```

Pastikan:
- `POSTGRES_DB` terisi
- `POSTGRES_USER` benar
- `POSTGRES_PASSWORD` benar
- service `db` dalam kondisi `healthy`

### C. Port sudah dipakai

Jika port `5000` atau `5432` bentrok, ubah:

```/dev/null/conflict.env#L1-2
APP_PORT=8080
POSTGRES_PORT=5433
```

Lalu jalankan ulang compose.

### D. Ingin reset semua data

```/dev/null/reset.sh#L1-2
docker compose --env-file .env.docker down -v
docker compose --env-file .env.docker up -d --build
```

## 16. Catatan Penting

- File `.env.docker` sebaiknya **jangan di-commit**
- Gunakan `SECRET_KEY` yang kuat
- Gunakan password PostgreSQL yang kuat
- Untuk production, sebaiknya pasang reverse proxy + HTTPS
- Lakukan backup database secara rutin
- Jika halaman tertentu error saat dibuka, cek apakah semua file `templates` dan `static` benar-benar tersedia di repository

## Ringkasan Command Cepat

Start:

```/dev/null/quick-start.sh#L1-2
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

Cek log:

```/dev/null/quick-logs.sh#L1-1
docker compose --env-file .env.docker logs -f web
```

Stop:

```/dev/null/quick-stop.sh#L1-1
docker compose --env-file .env.docker down
```

Buat admin:

```/dev/null/quick-admin.sh#L1-1
docker compose --env-file .env.docker exec web python create_admin.py
```
