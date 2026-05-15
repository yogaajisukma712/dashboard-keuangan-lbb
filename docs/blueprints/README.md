# Integration Blueprints

These blueprints are the detailed pipe-and-wiring maps for critical Aplikasi Lembaga workflows. They complement OpenSpec by showing exactly where a change enters, which records are source of truth, which services calculate values, which UI/export/report surfaces consume them, and what must be tested.

## Required Sections

Every critical-flow blueprint should include:

- Purpose
- Source of truth
- Entry points
- Route and service path
- Models and tables
- User-facing surfaces
- Side effects
- Invariants
- Known fragility
- Required checks
- Mermaid flow diagram

## Starting Points

1. `student-payment-to-quota-to-invoice.md`
2. `attendance-to-payroll-to-reconciliation.md`
3. `enrollment-to-schedule-to-attendance.md`
4. `whatsapp-attendance-to-presensi.md`
5. `closing-to-dashboard-balance.md`
6. `recruitment-to-contract-to-tutor.md`
7. `tutor-dashboard-to-ss-meet.md`

When a future change discovers a missing dependency, update the related blueprint before or with the code fix.
