# WhatsApp Management Session Backup

## Purpose

Map WhatsApp bot management, session lifecycle, backup/restore, group/contact directories, validation, and sync endpoints.

## Source Of Truth

- Bot runtime/session state: WhatsApp bot container and persistent auth/session volume
- Backup artifacts: configured WhatsApp backup storage
- Group/contact/message records: WhatsApp models in `app/models/whatsapp.py`
- Bot management routes: `app/routes/whatsapp.py`
- Attendance evidence consumers: attendance review blueprint and `whatsapp_ingest_service`

## Entry Points

- UI pages: `index`, `management`
- Session APIs: `bot_session`, `bot_session_management`, `bot_session_initialize`, `bot_session_logout`
- Backup APIs: `bot_session_backup`, `bot_session_restore`, `bot_session_backup_download`, `bot_session_backup_delete`
- Directory APIs: `bot_groups`, `bot_group_directory`, `bot_contact_directory`
- Validation APIs: `bot_contact_directory_validate`, `bot_contact_directory_validate_student`, `bot_group_directory_validate_student`
- Sync APIs: `bot_sync_groups`, `bot_sync_messages_full`
- Bot-to-app API: `health`, `sync`

## Route And Service Path

1. Admin opens WhatsApp management pages.
2. Web app proxies bot/session requests to the bot through `_bot_request` or `_bot_stream_request`.
3. Bot initializes, logs out, backs up, restores, downloads, or deletes session artifacts.
4. Group and contact directories are fetched and validated against student/tutor data.
5. Group/message sync endpoints ingest directory and message state for downstream attendance review.
6. Bot-to-app `/api/whatsapp/sync` requires token validation through `_require_bot_token`.

## User-Facing Surfaces

- WhatsApp bot dashboard
- WhatsApp management page
- Session initialize/logout controls
- Backup/restore/download/delete controls
- Group/contact directory validation UI/API
- Attendance review pages consuming synced evidence

## Invariants

- Bot token checks must protect bot-to-app sync endpoints.
- Backup files and session artifacts must not be dumped to chat, logs, or public templates.
- Restore must target the intended WhatsApp session storage only.
- Group/contact validation must not mutate student/tutor identity without explicit validation route action.
- Message/group sync must not create duplicate review evidence.

## Known Fragility

- WhatsApp session state is external to Flask request state and can drift after container restart.
- Backup/restore can make the bot appear healthy while app-side directory data is stale.
- Streaming full message sync can produce large output and must be summarized with context-mode.
- Token or session leakage is a security incident.

## Required Checks

- `openspec validate --specs --strict --no-interactive`
- Secret-redacted bot/session status check
- Docker service check for `whatsapp_bot` after bot integration changes
- Focused WhatsApp ingest/service tests when sync or validation changes
- Manual backup/restore dry-run only when explicitly safe

## Diagram

```mermaid
flowchart LR
  Admin[Admin WhatsApp UI] --> Routes[whatsapp.py management routes]
  Routes --> BotRequest[_bot_request / _bot_stream_request]
  BotRequest --> Bot[WhatsApp bot container]
  Bot --> Session[Persistent auth/session volume]
  Bot --> Backup[Backup artifacts]
  Bot --> Directories[Groups contacts messages]
  Directories --> Sync[Sync/validation APIs]
  Sync --> Models[WhatsApp models]
  Models --> AttendanceReview[Attendance review consumers]
  Bot --> TokenSync[/api/whatsapp/sync token-protected]
```
