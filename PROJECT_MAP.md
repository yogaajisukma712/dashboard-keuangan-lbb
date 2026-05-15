# Aplikasi Lembaga Project Map

This is the first file an AI agent or developer should read before changing the project.

The project is a Flask-based operations and finance system for LBB Super Smart. Its integrations are dense: student master data, enrollments, schedules, attendance, payments, quota, invoices, tutor payroll, reconciliation, dashboard, recruitment, tutor portal, SS Meet, WhatsApp, data manager, imports, reports, and Docker runtime all affect each other.

## Required Reading Order

1. `AGENTS.md`
2. `PROJECT_MAP.md`
3. `docs/architecture/README.md`
4. `docs/architecture/blueprint-coverage-audit.md`
5. `docs/architecture/audit-question-suite.md`
6. Relevant `openspec/specs/*/spec.md`
7. Relevant `docs/blueprints/*.md`
8. Relevant `docs/adr/*.md`

## Current Mapping Status

- OpenSpec specs: 9
- Integration blueprints: 15
- Coverage matrix rows: 15
- Current coverage status: all known global feature surfaces are `Detailed`
- Audit suite: 15 questions
- Manual drills completed: `AQ-011` auth gates, `AQ-012` WhatsApp ambiguity
- Code-fix drills completed: `AQ-013` SS Meet time validation, `AQ-014` tutor schedule source map, `AQ-015` tutor portal payout slip

## Core Flow Map

Use this as the mental starting point:

```text
master data
  -> enrollment and schedule
  -> attendance
  -> payment and quota
  -> invoice
  -> tutor payable and payroll
  -> reconciliation
  -> dashboard, closing, reports
```

Parallel operational flows:

```text
recruitment -> contract -> tutor
tutor portal -> credentials/request review -> schedule/profile updates
tutor portal -> SS Meet -> active meeting links
tutor portal -> tutor payout slip -> payroll fee slip context
WhatsApp bot -> group/contact validation -> attendance evidence -> manual review -> presensi
bulk import -> canonical records -> downstream finance/academic flows
data manager -> direct table editor/export/restore -> all canonical records
```

## Do Not Start Coding Until

For any non-trivial change:

1. Identify the affected blueprint.
2. Identify source-of-truth rows.
3. Identify route/service/model/template surfaces.
4. Identify downstream effects.
5. Identify tests/runtime checks.
6. If mapping cannot answer those points, update `docs/architecture/blueprint-coverage-audit.md` first.

## Critical Source-Of-Truth Rules

- Bought sessions come from `StudentPaymentLine.meeting_count`.
- Used sessions come from attended `AttendanceSession` rows.
- Quota and invoice must use the same cumulative calculation path.
- Tutor payable accrual comes from attendance.
- Payout state comes from `TutorPayout` and payout lines/proofs.
- Tutor portal payout slip is read-only and must stay scoped to `payout.tutor_id == tutor.id`.
- Reconciliation must expose gaps between collection payable, attendance accrual, and actual payouts.
- WhatsApp evidence is not inherently trusted; ambiguous or risky links must remain reviewable.
- Data manager restore/table edits are high-risk admin operations, not normal business workflows.

## Current Known Tooling Notes

- Use `context-mode` for broad scans, logs, test output, Docker output, and large outputs.
- Use `serena` for symbols, route/service methods, and precise code navigation.
- Use `repomapper` when helpful, but current repo scans have repeatedly returned no usable map; continue with Serena/context-mode when that happens.
- Run `openspec validate --specs --strict --no-interactive` after mapping changes.

## When New Gaps Are Found

1. Add the missing surface to `docs/architecture/blueprint-coverage-audit.md` as `Partial` or `Gap`.
2. Add or update the relevant OpenSpec spec.
3. Add or update the relevant blueprint.
4. Add an audit question if the gap represents a recurring failure mode.
5. Only then implement risky runtime changes.
