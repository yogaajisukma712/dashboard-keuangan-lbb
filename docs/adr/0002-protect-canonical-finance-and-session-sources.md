# ADR 0002: Protect Canonical Finance And Session Sources

## Status

Accepted

## Context

Payment, quota, invoice, attendance, payroll, reconciliation, and dashboard views all depend on overlapping financial and academic data. Previous quota issues showed that derived totals can become stale when payment headers change without synchronizing payment lines.

## Decision

Use canonical records for critical calculations:

- Bought sessions come from `StudentPaymentLine.meeting_count`.
- Used sessions come from attended `AttendanceSession` rows.
- Student quota and invoice math must use the same cumulative calculation path.
- Tutor attendance accrual comes from attendance records.
- Tutor payout state comes from payout headers and payout lines.
- Reconciliation must compare collection payable, attendance accrual, and actual payouts instead of collapsing them into one hidden number.

Derived summaries may be shown in the UI, but they must be refreshable or recomputable from canonical records.

## Consequences

- New finance features must identify their source-of-truth rows before coding.
- Templates should display calculated service results, not reimplement formulas.
- Tests must cover shared calculation paths when a change affects payment, quota, invoice, attendance, payroll, reconciliation, or dashboard totals.
- Blueprints must be updated when a source of truth changes.
