# Aplikasi Lembaga Handoff

Last updated: 2026-07-07 Asia/Jakarta

## Current Project

- Local path: /home/ubuntu/Documents/lembaga/aplikasi lembaga
- Server host: 178.128.19.223
- Server app path: /opt/apps/lembaga/aplikasi-lembaga
- Main GitHub repo: https://github.com/yogaajisukma712/dashboard-keuangan-lbb

## Database Backup

Latest encrypted database backup:

- Backup repository: https://github.com/yogaajisukma712/lembaga-db-backups
- Backup file: backups/20260707-133509-WIB/lembaga-db-backup-20260707-133509-WIB.tar.gz.enc
- Passphrase file in this app repo: docs/backups/secrets/database-backup-passphrase-20260707-133509-WIB.txt
- Restore handoff: docs/backups/database-backup-handoff.md
- Server local encrypted archive: /root/db-backups/lembaga/lembaga-db-backup-20260707-133509-WIB.tar.gz.enc
- Server passphrase source: /root/db-backups/lembaga/20260707-133509-WIB/PASSPHRASE_DO_NOT_UPLOAD.txt

Read docs/backups/database-backup-handoff.md before restore. Backup archive is encrypted with OpenSSL AES-256-CBC PBKDF2.

## Deployment Reminder

The production web container does not mount source code. After code changes on server, rebuild and recreate billing_supersmart_web, then connect it to the existing aplikasilembaga_billing_net network if Compose creates a new project network.
