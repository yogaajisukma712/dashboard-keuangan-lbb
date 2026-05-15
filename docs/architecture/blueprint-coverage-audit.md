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
| WhatsApp evidence -> presensi | `app/routes/attendance.py`, `app/services/whatsapp_ingest_service.py`, `app/models/whatsapp.py` | Detailed | Keep updated with attendance evidence changes. |
| Closing -> dashboard balance | `app/routes/closings.py`, `app/services/dashboard_service.py` | Detailed | Add more detail when closing locks/backdated edits are changed. |
| Recruitment -> contract -> tutor | `app/routes/recruitment.py`, `app/models/recruitment.py`, `app/models/master.py` | Detailed | Deepen if candidate-to-tutor conversion behavior changes. |
| Tutor dashboard -> SS Meet | `app/routes/tutor_portal.py`, `app/models/tutor_portal.py` | Detailed | Deepen if SS Meet server/API changes. |
| Tutor portal credentials and schedule requests | `app/routes/tutor_portal.py`, `app/models/tutor_portal.py` | Detailed | Keep updated with onboarding, credential, request, and approval changes. |
| WhatsApp management/session backup | `app/routes/whatsapp.py`, bot service, WhatsApp volumes | Detailed | Keep updated with bot/session/backup/sync changes. |
| Data manager SQL export/restore/table editor | `app/routes/data_manager.py` | Detailed | Keep updated before data manager or restore changes. |
| Reports module | `app/routes/reports.py`, `app/services/reporting_service.py` | Detailed | Keep updated with report/export changes. |
| Auth/admin login | `app/routes/auth.py`, `app/models/master.py:User` | Detailed | Keep updated before role/session/security changes. |
| Income and expenses | `app/routes/incomes.py`, `app/routes/expenses.py`, `app/models/income.py`, `app/models/expense.py` | Detailed | Keep updated with cash movement changes. |
| Bulk upload and legacy import | `app/routes/master.py`, `app/services/bulk_import_service.py`, `app/services/legacy_alldata_import_service.py` | Detailed | Keep updated with import dataset/parsing changes. |
| Recruitment CRM dashboard pages | `app/routes/recruitment.py`, recruitment templates | Detailed | Keep updated with candidate CRM and contract changes. |

## Immediate Findings

1. Recruitment and contract routes existed in code but were only mentioned globally. They now have OpenSpec and a first-pass integration blueprint.
2. Tutor dashboard and SS Meet were present in C4 and OpenSpec, but the route/service/model pipe was not explicit. They now have a first-pass integration blueprint.
3. The guardian skill now routes recruitment, contract, SS Meet, tutor portal credentials/requests, WhatsApp management, data manager, bulk import, auth, income/expense, and reports explicitly.
4. RepoMapper currently cannot generate a usable repository map for this project, so Serena and context-mode remain the reliable mapping tools.
5. Audit question suite exists at `docs/architecture/audit-question-suite.md`; initial run found and fixed a bulk-import mapping omission around `_normalize_name`, `_find_student`, and `_find_tutor`.

## Next Detailing Queue

All known global feature surfaces in this audit are now Detailed.

When a future scan finds a feature that is only partial or missing, add it here with `Partial` or `Gap` coverage and create a new blueprint before risky implementation.
