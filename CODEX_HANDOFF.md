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

## Daily GitHub Backup

- Timer: `lembaga-daily-backup.timer`
- Schedule: daily at 00.00 Asia/Jakarta (17.00 UTC)
- Private target: GitHub Releases in `yogaajisukma712/lembaga-db-backups`
- Coverage: official WhatsApp session archive plus all PostgreSQL databases/globals
- Encryption: OpenSSL AES-256-CBC PBKDF2, passphrase from the database backup handoff
- Retention: 14 GitHub releases, 3 local encrypted days, 3 local bot session archives
- First verified release: `daily-20260707-143842-WIB`
- Operations and restore: `docs/backups/daily-github-backup.md`

The timer does not stop or restart the WhatsApp, web, or database containers.

## Deployment Reminder

The production web container does not mount source code. After code changes on server, rebuild and recreate billing_supersmart_web, then connect it to the existing aplikasilembaga_billing_net network if Compose creates a new project network.
