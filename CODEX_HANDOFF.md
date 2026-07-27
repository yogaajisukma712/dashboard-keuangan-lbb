# Aplikasi Lembaga Handoff

Last updated: 2026-07-27 Asia/Jakarta

## Current Project

- Local path: /home/ubuntu/Documents/lembaga/aplikasi lembaga
- Server SSH: ec2-user@ec2-98-94-77-55.compute-1.amazonaws.com
- SSH key: /home/ubuntu/Documents/lembaga/aplikasi lembaga/lembaga.pem
- Server app path: /opt/apps/lembaga/aplikasi-lembaga
- Main GitHub repo: https://github.com/yogaajisukma712/dashboard-keuangan-lbb
- Compose project: aplikasilembaga
- Production domains: https://app.supersmart.click, https://tutor.supersmart.click, https://recruitment.supersmart.click

## Database Backup

The new server was restored from the latest complete release available when the
old server failed:

- Backup repository: https://github.com/yogaajisukma712/lembaga-db-backups
- Restore source: GitHub release `daily-20260711-000018-WIB`
- PostgreSQL asset: `postgres-cluster-20260711-000018-WIB.sql.gz.enc`
- WhatsApp asset: `wa-session-billing-supersmart-2026-07-10T17-00-18-862Z-491cfa5d.tar.gz.enc`
- Restore cache: `/opt/backups/lembaga/daily-20260711-000018-WIB`
- Root-only passphrase: `/root/.config/lembaga-backup/passphrase`
- Guarded restore tool: `ops/restore/restore-latest-backup.sh`

All release checksums passed before decryption. The restore selected only
`lbb_db` from the full cluster dump to avoid replacing PostgreSQL system
databases and roles.

Restore verification:

- 37 table COPY blocks compared against live PostgreSQL
- 33,366 backup rows and 33,366 restored rows
- 0 table-count mismatches
- 5,955 WhatsApp auth files restored
- WhatsApp session returned `ready=true`, `authenticated=true`, and no QR
- five application containers running; database and WhatsApp containers healthy
- both Cloudflare tunnel services active

WhatsApp gap recovery completed 2026-07-27:

- Production fix commit: `33ca64b`
- Root failure: upstream `getChats()` aborted with the opaque error `r`
- Recovery: per-group chat loading, direct group-ID fallback, and 2,000-message backend batches
- Detected groups: 122; operational groups scanned: 121; configured exclusions: 1
- Direct-fallback groups: 16; failed groups after fallback: 0
- Gap cutoff: message after `2026-07-10 12:25:27 UTC`
- Gap recovered: 386 messages and 27 relevant evaluations
- Gap attendance result: 27 linked, 0 unmatched
- Latest visible WhatsApp message at audit: `2026-07-27 14:30:15 WIB`
- Final database totals: 33,955 messages, 2,993 evaluations, 5,274 attendance sessions
- Post-recovery encrypted release: `daily-20260727-150851-WIB`

## Daily GitHub Backup

- Timer: `lembaga-daily-backup.timer`
- Schedule: daily at 00.00 Asia/Jakarta (17.00 UTC)
- Private target: GitHub Releases in `yogaajisukma712/lembaga-db-backups`
- Coverage: official WhatsApp session archive plus all PostgreSQL databases/globals
- Encryption: OpenSSL AES-256-CBC PBKDF2, passphrase from the database backup handoff
- Retention: 14 GitHub releases, 3 local encrypted days, 3 local bot session archives
- First verified release from the restored server: `daily-20260727-135433-WIB`
- Operations and restore: `docs/backups/daily-github-backup.md`

The timer does not stop or restart the WhatsApp, web, or database containers.

Weekly WhatsApp maintenance:

- Timer: `lembaga-weekly-whatsapp-restart.timer`
- Schedule: every Sunday at 01.00 Asia/Jakarta (Saturday 18.00 UTC)
- Safety gate: encrypted backup not older than two hours, valid checksums, and bot `healthy` plus session `ready`
- Scope: restart only `billing_supersmart_whatsapp_bot`; persistent volumes remain attached
- Post-check: wait up to five minutes for container `healthy` and session `ready`
- Missed schedules are not replayed after server boot

## Deployment Reminder

The production containers do not mount application source. Push changes to
GitHub, pull them into `/opt/apps/lembaga/aplikasi-lembaga`, then rebuild and
recreate the affected Compose service. Keep project name `aplikasilembaga` so
the restored PostgreSQL and WhatsApp volumes remain attached. Never run
`docker compose down -v`.

The old `.env` was not present in the encrypted backup. Required production
secrets were rotated and stored root-only on the new server. Optional Google
OAuth, SMTP, and SS Meet secrets remain unset until their original values are
provided.
