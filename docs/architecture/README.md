# Aplikasi Lembaga Architecture Knowledge System

This folder is the architecture map for long-term maintenance. OpenSpec is the global contract, while these docs make the critical wiring explicit enough for future changes to start from the right place.

## Six-Stack Model

1. OpenSpec requirements: global contracts and safety rules in `openspec/specs/`.
2. Integration blueprints: end-to-end business pipelines in `docs/blueprints/`.
3. Diagram-as-code: Mermaid flow diagrams embedded in blueprint Markdown.
4. C4 / Structurizr model: system, container, and component boundaries in `docs/architecture/structurizr.dsl`.
5. ADR: durable decisions in `docs/adr/`.
6. Codex guardian skill: pre-edit workflow in `.codex/skills/lembaga-integration-guardian/`.

## How To Use Before Coding

For small isolated UI copy changes, read only the affected file. For anything involving payment, quota, invoice, attendance, payroll, tutor portal, WhatsApp, closing, dashboard, Docker, or schema changes, use this sequence:

1. Read the related OpenSpec file under `openspec/specs/`.
2. Read the matching blueprint under `docs/blueprints/`.
3. Check ADRs for source-of-truth and calculation decisions.
4. Trace the route, service, model, template, and tests listed by the blueprint.
5. If code and blueprint disagree, pause and decide whether the code is wrong or the blueprint is stale.
6. Implement with focused tests and container/runtime checks where relevant.
7. Update the blueprint and ADR when the change teaches a new durable rule.

## Critical Flow Index

| Flow | Blueprint | Primary Risk |
| --- | --- | --- |
| Student payment to quota to invoice | `docs/blueprints/student-payment-to-quota-to-invoice.md` | Bought sessions, invoice totals, and visible quota diverge. |
| Attendance to payroll to reconciliation | `docs/blueprints/attendance-to-payroll-to-reconciliation.md` | Tutor payable differs across attendance, payroll, and dashboard. |
| Enrollment to schedule to attendance | `docs/blueprints/enrollment-to-schedule-to-attendance.md` | Attendance loses subject, tutor, fee, or quota context. |
| WhatsApp attendance to presensi | `docs/blueprints/whatsapp-attendance-to-presensi.md` | Bot evidence creates duplicate or incorrect attendance rows. |
| Closing to dashboard balance | `docs/blueprints/closing-to-dashboard-balance.md` | Opening balance, payable, and profit drift across months. |
| Recruitment to contract to tutor | `docs/blueprints/recruitment-to-contract-to-tutor.md` | Candidate status, contract signature, and tutor creation drift. |
| Tutor dashboard to SS Meet | `docs/blueprints/tutor-dashboard-to-ss-meet.md` | Tutor-scoped schedules and external meet links break or leak scope. |
| Tutor portal credentials and requests | `docs/blueprints/tutor-portal-credentials-and-requests.md` | Credential delivery, request review, and approved schedule mutation drift. |
| WhatsApp management and backup | `docs/blueprints/whatsapp-management-session-backup.md` | Bot session artifacts, backups, and sync leak or drift. |
| Data manager export/restore/table editor | `docs/blueprints/data-manager-export-restore-table-editor.md` | Generic table editor or restore corrupts canonical business records. |
| Bulk upload/import order | `docs/blueprints/bulk-upload-import-order.md` | Imports create duplicates, skip dependencies, or break totals. |
| Auth/admin session security | `docs/blueprints/auth-admin-session-security.md` | Unsafe redirects, exposed admin routes, or weak session handling. |
| Income/expense cash movement | `docs/blueprints/income-expense-cash-movement.md` | Cash movement diverges from dashboard, closing, and reports. |
| Reports and exports | `docs/blueprints/reports-and-exports.md` | Visible reports and exported files diverge. |

Coverage audit and next detailing queue:

- `docs/architecture/blueprint-coverage-audit.md`

## Maintenance Rules

- Treat blueprints as executable review checklists.
- Do not duplicate formulas in templates when a service already owns the calculation.
- Keep source-of-truth statements explicit.
- Add ADRs for decisions that future changes must not reverse.
- Keep diagrams textual and close to the pipeline they explain.
- When a bug is found while mapping, fix the bug and update the map in the same branch when practical.
