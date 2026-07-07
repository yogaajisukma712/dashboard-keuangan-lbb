# Backup Harian GitHub

## Cakupan

Backup otomatis berjalan setiap hari pukul 00.00 WIB dari server produksi.

- Sesi WhatsApp: bot membuat arsip resmi dari volume auth ke volume backup.
- Data aplikasi dan pesan tersimpan: seluruh cluster PostgreSQL melalui `pg_dumpall`.
- Tujuan: GitHub Releases pada repo privat `yogaajisukma712/lembaga-db-backups`.
- Enkripsi: OpenSSL AES-256-CBC, PBKDF2, 200000 iterasi.
- Retensi: 14 rilis harian GitHub, 3 hari arsip terenkripsi lokal, 3 backup sesi bot lokal.

Timer tidak menghentikan atau me-restart container WhatsApp maupun web.

## Restart Mingguan WhatsApp

`lembaga-weekly-whatsapp-restart.timer` me-restart hanya container WhatsApp
setiap Minggu pukul 01.00 WIB, satu jam setelah backup harian.

Restart hanya dijalankan jika:

- backup terenkripsi terbaru berumur maksimal dua jam;
- seluruh checksum backup valid;
- container berstatus `healthy` dan sesi berstatus `ready` sebelum restart.

Setelah restart, service menunggu maksimal lima menit sampai container kembali
`healthy` dan sesi kembali `ready`. Volume auth, volume backup, PostgreSQL, dan
container web tidak dihapus atau di-restart. Timer tidak mengejar jadwal yang
terlewat setelah server baru menyala.

## Lokasi Server

- Skrip: `/usr/local/sbin/lembaga-daily-backup`
- Secret: `/root/.config/lembaga-backup/`
- Arsip sementara: `/root/daily-backups/lembaga/`
- Unit: `lembaga-daily-backup.service`
- Timer: `lembaga-daily-backup.timer`

## Pemeriksaan

```bash
systemctl status lembaga-daily-backup.timer
systemctl list-timers lembaga-daily-backup.timer
journalctl -u lembaga-daily-backup.service -n 100 --no-pager
systemctl status lembaga-weekly-whatsapp-restart.timer
journalctl -u lembaga-weekly-whatsapp-restart.service -n 100 --no-pager
```

## Restore WhatsApp

1. Unduh aset `wa-session-*.tar.gz.enc` dari rilis yang dipilih.
2. Verifikasi file terhadap `SHA256SUMS`.
3. Dekripsi tanpa menampilkan passphrase:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in wa-session-*.tar.gz.enc -out wa-session-restore.tar.gz \
  -pass file:/root/.config/lembaga-backup/passphrase
```

4. Salin arsip hasil dekripsi ke volume `/app/.wwebjs_backups` milik container bot.
5. Restore melalui halaman manajemen WhatsApp. Jangan menimpa volume auth secara manual saat bot aktif.
6. Verifikasi status sesi, sinkronisasi grup, pesan, kontak, dan bukti presensi.

## Restore PostgreSQL

Restore database adalah operasi berisiko. Buat backup keadaan terkini dan hentikan penulisan aplikasi sebelum menjalankannya.

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in postgres-cluster-*.sql.gz.enc -out postgres-cluster.sql.gz \
  -pass file:/root/.config/lembaga-backup/passphrase
gzip -t postgres-cluster.sql.gz
gunzip -c postgres-cluster.sql.gz | \
  docker exec -i billing_supersmart_db sh -lc 'psql -U "$POSTGRES_USER" -d postgres'
```

Setelah restore, verifikasi schema, jumlah record utama, status web, status bot, dan relasi bukti WhatsApp ke presensi.
