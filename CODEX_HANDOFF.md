# Aplikasi Lembaga Handoff

Last updated: 2026-09-09 Asia/Jakarta

## Current Project

- Local path: /home/ubuntu/Documents/lembaga/aplikasi lembaga
- Main GitHub repo: https://github.com/yogaajisukma712/dashboard-keuangan-lbb
- Production domains: https://app.supersmart.click, https://tutor.supersmart.click, https://recruitment.supersmart.click (Cloudflare Tunnel)
- Version at last update: `1.5.0+20260908.f59c168` (HEAD `5620713`)

## Current Architecture (post-AWS migration)

- Dashboard (Flask): deployed on **Vercel** (`vercel.json` uses `rewrites` + `regions sin1`)
- Database: **Neon** PostgreSQL (migrated off self-hosted Postgres 5433)
- WhatsApp bot: Docker container on VM, talks to dashboard purely over HTTP + token
- WA bot heartbeat endpoint: `/dashboard/api/system/heartbeat`

### DigitalOcean VPS#1 (WA bot host) — CURRENTLY OFF

- IP: `152.42.246.93`
- Status at 2026-09-08: port 22 CLOSED, ping 100% loss — droplet powered off
- Action needed: power on from DigitalOcean panel, then recover payroll proof files (below)

## Migration History (2026-09-07 to 2026-09-08)

Old production was AWS EC2 (`ec2-user@ec2-34-239-130-246.compute-1.amazonaws.com`,
key `lembaga.pem`, app path `/opt/apps/lembaga/aplikasi-lembaga`, compose project
`aplikasilembaga`): 5 containers (web 6001, tutor 6003, recruitment 6006, WA bot
6002, db 5433) behind Cloudflare Tunnel. `billing.supersmart.click` was already
dead there.

Migration steps executed:

1. Full EC2 backup taken first (see Backup Assets below)
2. DO VPS#1 provisioned: Docker + cloudflared installed, 3 Flask images built
3. WA bot moved via `docker save`/`docker load` from AWS (base image
   `node:18-bullseye-slim` is EOL — apt install fails, so image was transferred,
   not rebuilt)
4. Cutover: freeze AWS writes → final DB dump (36,174 rows) → stop AWS tunnel →
   same Cloudflare tunnel token brought up on DO
5. AWS instance left intact as rollback; not decommissioned

Post-migration application fixes:

- Dual SQLAlchemy instance bug fixed (`app/__init__.py` vs `app/extensions`) that
  broke `heavy_jobs_queue`
- Bot heartbeat path corrected to `/dashboard/api/system/heartbeat`
- Surat paklaring generator rewritten with ReportLab: numbering starts at 37, QR
  code links to a public digital verification page (no login), duplicate INSERT
  fixed
- Paklaring PDF delivery to tutors via WA bot

Server hardening applied on DO VPS#1:

- `ufw` allows SSH only
- All service ports bind `127.0.0.1` (previously Postgres 5433 was exposed)

## Payroll Proof Files

- Metadata: 67 rows in Neon
- Physical files: Docker volume `uploads/payroll_proofs/` on DO VPS#1
- 15 files restored to VPS#2
- 42 files (May–July 2026) are on DO VPS#1's disk — unrecoverable until the
  droplet is powered on; recover them to VPS#2 promptly

## Backup Assets

- Local full EC2 backup: `backups/ec2-full-backup-20260905-232801-WIB/`
  (526 MB, 17 files, sha256 + gzip verified, 0 DB delta vs AWS at backup time)
  — contains real secrets; never commit
- Legacy encrypted GitHub releases (from AWS era): repo
  `yogaajisukma712/lembaga-db-backups`, restore source
  `daily-20260711-000018-WIB`, guarded tool `ops/restore/restore-latest-backup.sh`
- GitHub backup for WA bot assets: 149.5 MB upload verified; 5 stale empty
  releases were deleted first
- Backup repo operations notes: `docs/backups/daily-github-backup.md`

## Secrets

- `.server_lembaga/` — GitHub + cloudflared tokens in plaintext. Must stay
  gitignored; never commit or push
- `api key penting/` — GitHub token used by WA bot backup uploads
- `.gitignore` verified to cover all secret paths; `.env.example` and
  `.env.railway` remain committed intentionally

## Standby / Failover Options

- Helipod: standby bot, not yet migrated
- VPS#3: candidate for backup/failover host
- AWS EC2: intact, usable as rollback (legacy topology)

## Deployment Flow (current)

- Dashboard: push to GitHub → Vercel deployment
- WA bot host (DO VPS#1): pull repo → rebuild/recreate affected Compose service
- Database: Neon (no container rebuild)

## Legacy Notes

- Persistent filters: shared manager `app/static/js/persistent-filters.js`,
  styling `app/static/css/persistent-filters.css`; covers authenticated admin
  pages and tutor portal GET filter forms; the inline manager in
  `app/templates/base.html` is fallback-only
- Historical WhatsApp recovery work (July 2026, commits `33ca64b`, `e0697d1`,
  `e6d5ed2`): gap recovery, July attendance reconciliation, pre-July history
  restore — details in git history of this file

## Next Actions

1. Power on DO VPS#1 from the DigitalOcean panel
2. Copy 42 payroll proof files (`uploads/payroll_proofs/`) to VPS#2
3. Consider migrating Helipod and provisioning VPS#3 as failover
