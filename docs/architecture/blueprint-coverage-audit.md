# Blueprint Coverage Audit

Last reviewed: 2026-05-15

This audit compares global project surfaces against the detailed integration blueprints. A feature is considered detailed only when it has an end-to-end blueprint with source of truth, entry points, routes/services/models, UI surfaces, invariants, known fragility, required checks, and a diagram.

## Coverage Levels

- Detailed: has a dedicated pipeline blueprint.
- Partial: mentioned in OpenSpec/C4 or covered as a dependency, but not mapped end-to-end.
- Gap: no meaningful blueprint yet.

## Current Coverage Matrix

| Feature Surface | Code Anchor | Current Coverage | Action |
| --- | --- | --- | --- |
| Payment -> quota -> invoice | `app/routes/payments.py`, `app/routes/quota_invoice.py`, `app/models/payment.py` | Detailed | Keep updated with quota/invoice changes. |
| Attendance -> payroll -> reconciliation | `app/routes/attendance.py`, `app/routes/payroll.py`, `app/services/payroll_service.py`, `app/services/reconciliation_service.py` | Detailed | Keep updated with fee/payroll changes. |
| Enrollment -> schedule -> attendance | `app/routes/enrollments.py`, `app/models/enrollment.py`, `app/routes/attendance.py` | Detailed | Add more detail when schedule editor changes. |
| WhatsApp evidence -> presensi | `app/routes/attendance.py`, `app/services/whatsapp_ingest_service.py`, `app/models/whatsapp.py` | Detailed for attendance evidence, partial for management console | Add management/session blueprint later. |
| Closing -> dashboard balance | `app/routes/closings.py`, `app/services/dashboard_service.py` | Detailed | Add more detail when closing locks/backdated edits are changed. |
| Recruitment -> contract -> tutor | `app/routes/recruitment.py`, `app/models/recruitment.py`, `app/models/master.py` | Detailed in first pass | Deepen if candidate-to-tutor conversion behavior changes. |
| Tutor dashboard -> SS Meet | `app/routes/tutor_portal.py`, `app/models/tutor_portal.py` | Detailed in first pass | Deepen if SS Meet server/API changes. |
| Tutor portal credentials and schedule requests | `app/routes/tutor_portal.py`, `app/models/tutor_portal.py` | Partial | Needs dedicated blueprint if onboarding/credentials/request review changes. |
| WhatsApp management/session backup | `app/routes/whatsapp.py`, bot service, WhatsApp volumes | Partial | Needs dedicated blueprint. |
| Data manager SQL export/restore/table editor | `app/routes/data_manager.py` | Gap | Needs dedicated blueprint before changes. |
| Reports module | `app/routes/reports.py`, reporting templates/services | Gap | Needs inventory and blueprint. |
| Auth/admin login | `app/routes/auth.py`, `app/models/master.py:User` | Gap | Needs blueprint before role/session/security changes. |
| Income and expenses | `app/routes/incomes.py`, `app/routes/expenses.py`, `app/models/income.py`, `app/models/expense.py` | Partial through dashboard/closing | Needs dedicated cash-movement blueprint. |
| Bulk upload and legacy import | `app/routes/master.py`, `app/services/bulk_import_service.py`, `app/services/legacy_alldata_import_service.py` | Partial through enrollment/attendance/payment blueprints | Needs dedicated import-order blueprint. |
| Recruitment CRM dashboard pages | `app/routes/recruitment.py`, recruitment templates | Partial through recruitment blueprint | Deepen with template states and admin permissions later. |

## Immediate Findings

1. Recruitment and contract routes existed in code but were only mentioned globally. They now have OpenSpec and a first-pass integration blueprint.
2. Tutor dashboard and SS Meet were present in C4 and OpenSpec, but the route/service/model pipe was not explicit. They now have a first-pass integration blueprint.
3. The guardian skill did not route recruitment, contract, SS Meet, data manager, reports, auth, income/expense, or bulk import explicitly. It now needs to keep expanding as blueprints are added.
4. RepoMapper currently cannot generate a usable repository map for this project, so Serena and context-mode remain the reliable mapping tools.

## Next Detailing Queue

1. `tutor-portal-credentials-and-requests.md`
2. `whatsapp-management-session-backup.md`
3. `data-manager-export-restore-table-editor.md`
4. `bulk-upload-import-order.md`
5. `auth-admin-session-security.md`
6. `income-expense-cash-movement.md`
7. `reports-and-exports.md`

Use this audit as the handoff list for future mapping chats.
