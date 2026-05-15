---
name: lembaga-integration-guardian
description: Use before implementing any Aplikasi Lembaga change that touches payment, quota, invoice, attendance, enrollment, schedule, payroll, reconciliation, dashboard, tutor portal, WhatsApp, closing, Docker deployment, schema changes, or multi-file behavior. Forces Codex to read OpenSpec plus integration blueprints, identify source-of-truth records, and produce an affected-flow map before edits.
metadata:
  short-description: Guard critical LBB integrations before coding
---

# Lembaga Integration Guardian

Use this skill before code edits in critical Aplikasi Lembaga flows.

## Mandatory Inputs

Start from repo root:

```bash
/workspace/aplikasi-lembaga
```

Read these first:

1. `openspec/specs/`
2. `docs/architecture/README.md`
3. Matching `docs/blueprints/*.md`
4. Relevant `docs/adr/*.md`
5. Current git state

Use MCP:

- `context-mode` for broad scans, git history, test output, Docker output, and large files.
- `serena` for symbols, route handlers, service methods, references, and precise navigation.
- `repomapper` for architecture mapping when it works. If it cannot generate a map, say so and continue with Serena/context-mode.

## Critical Flow Routing

Use these blueprint matches:

- Payment, quota, invoice, student detail: `docs/blueprints/student-payment-to-quota-to-invoice.md`
- Attendance, payroll, reconciliation, tutor payable: `docs/blueprints/attendance-to-payroll-to-reconciliation.md`
- Enrollment, schedule, attendance context, bulk import order: `docs/blueprints/enrollment-to-schedule-to-attendance.md`
- WhatsApp bot, review, attendance evidence, credentials: `docs/blueprints/whatsapp-attendance-to-presensi.md`
- Dashboard, closing, opening balance, profit, payable: `docs/blueprints/closing-to-dashboard-balance.md`
- Recruitment, pelamar dashboard, contract, candidate-to-tutor: `docs/blueprints/recruitment-to-contract-to-tutor.md`
- Tutor dashboard, SS Meet links, portal requests: `docs/blueprints/tutor-dashboard-to-ss-meet.md`

If no dedicated blueprint exists yet, read `docs/architecture/blueprint-coverage-audit.md` and treat the feature as a documentation gap to close before risky implementation.

## Pre-Edit Report

Before editing code, report:

1. Affected blueprint(s)
2. Entry route(s)
3. Service methods and model rows that are source of truth
4. User-facing surfaces that may change
5. Invariants that must not break
6. Tests and runtime checks you will run
7. Any mismatch between code and blueprint

Keep this report concise but concrete. Use file paths and symbol names.

## Stop Conditions

Pause and tell the user before editing if:

- Source-of-truth ownership is unclear.
- Existing code contradicts OpenSpec or a blueprint in a way that could corrupt finance, quota, attendance, payroll, WhatsApp, or closing data.
- A schema/data repair may be required.
- A secret, auth file, token, or WhatsApp session artifact would need to be displayed.
- Docker/runtime state does not match the repo assumptions for a deployment-sensitive change.

## Implementation Rules

- Preserve cumulative quota/session logic.
- Do not duplicate shared formulas in templates.
- Keep payment lines synchronized with payment forms.
- Keep attendance as the basis for used sessions and tutor accrual.
- Keep payout state separate from attendance accrual.
- Keep reconciliation gaps visible.
- Keep WhatsApp evidence reviewable when ambiguous.
- Update the relevant blueprint or ADR when a durable rule is discovered.

## Verification

Minimum checks:

```bash
openspec validate --specs --strict --no-interactive
git status --short
```

Add focused checks based on risk:

- Payment/quota/invoice: quota and invoice tests.
- Attendance/payroll/reconciliation: attendance and payroll tests.
- Tutor portal: tutor portal tests and container bootstrap.
- Recruitment/contract: recruitment route/template tests and secret-redacted mail/WhatsApp checks.
- SS Meet: tutor portal tests plus secret-redacted SS Meet configuration checks.
- WhatsApp: bot/session status and secret-redacted logs.
- Docker-visible changes: rebuild/restart affected service and check status.

When the user asks to push, commit and push after verification.
