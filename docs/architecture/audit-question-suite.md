# Audit Question Suite

Last reviewed: 2026-05-15

This suite tests whether the architecture map can answer real maintenance questions. If a question cannot be answered from OpenSpec plus the relevant blueprint, the map is incomplete or the underlying logic needs investigation.

## How To Run This Audit

For each question:

1. Identify the matching OpenSpec spec.
2. Identify the matching integration blueprint.
3. Answer the question using source-of-truth records, entry routes, service/helper methods, user-facing surfaces, invariants, known fragility, and required checks.
4. If any required element is missing, add the missing area to `docs/architecture/blueprint-coverage-audit.md` as `Partial` or `Gap`.
5. Fix the blueprint or code understanding before risky implementation.

## Pass Criteria

A question passes when the map can identify:

- Source-of-truth data
- Entry routes
- Service/helper methods
- User-facing surfaces
- Downstream impact
- Invariants
- Known fragility
- Required checks

## Questions

| ID | Audit Question | Expected Blueprint(s) | Required Anchors |
| --- | --- | --- | --- |
| AQ-001 | Payment subject/enrollment is edited, but student bought sessions do not change. Where does the map tell us to start and what must not break? | `student-payment-to-quota-to-invoice.md` | `StudentPaymentLine`, `_sync_payment_lines_from_form`, `calc_quota`, `refresh_student_quota`, quota tests |
| AQ-002 | A tutor attendance row has the wrong nominal fee. Which downstream values can change? | `attendance-to-payroll-to-reconciliation.md` | `AttendanceSession`, `PayrollService`, `ReconciliationService`, dashboard/reporting, attendance export |
| AQ-003 | Admin restores SQL through data manager. Which guardrails must be checked before doing it? | `data-manager-export-restore-table-editor.md` | `TABLE_WHITELIST`, `READONLY_COLUMNS`, `restore_sql`, backup discipline, canonical rows |
| AQ-004 | Tutor requests a schedule change. Where is the pending state, who approves it, and when does data mutate? | `tutor-portal-credentials-and-requests.md`, `tutor-dashboard-to-ss-meet.md` | `TutorPortalRequest`, `request_schedule_change`, `admin_request_detail`, `review_request`, `_apply_approved_request` |
| AQ-005 | SS Meet fails to create a meeting link. Which external boundary and stored records are involved? | `tutor-dashboard-to-ss-meet.md` | `_ss_meet_api_request`, `create_meet_link`, `TutorMeetLink`, active link state, tutor dashboard |
| AQ-006 | Candidate signs a contract but is not yet a tutor. Which lifecycle states and conversion path apply? | `recruitment-to-contract-to-tutor.md` | `RecruitmentCandidate`, `_contract_token`, `_sign_candidate_contract`, `_create_tutor_from_candidate`, contract state |
| AQ-007 | WhatsApp session disappears after restart. Which map covers backup/restore and what must stay secret? | `whatsapp-management-session-backup.md` | bot session, backup, restore, `bot_session_backup`, `bot_session_restore`, secret/session redaction |
| AQ-008 | Bulk CSV import creates duplicate students or tutors. Which helper methods control matching? | `bulk-upload-import-order.md` | `BulkImportService`, `_normalize_name`, `_find_student`, `_find_tutor`, warnings |
| AQ-009 | Excel report values do not match the visible report page. Which route/service path must be compared? | `reports-and-exports.md` | `ReportingService`, `export_to_excel`, visible report, same filters, exported values |
| AQ-010 | Backdated expense after monthly closing changes dashboard totals. Which workflows are involved? | `income-expense-cash-movement.md`, `closing-to-dashboard-balance.md` | `Expense`, `MonthlyClosing`, `DashboardService`, backdated edits, closing period risk |
| AQ-011 | A user can access an admin page without login. Which map defines the security boundary? | `auth-admin-session-security.md` | `auth.login`, `auth.logout`, Flask-Login session, safe redirects, anonymous route checks |
| AQ-012 | WhatsApp evidence links to the wrong student. Which validation and review path should be inspected? | `whatsapp-attendance-to-presensi.md` | WhatsApp models, `whatsapp_ingest_service`, manual review, linked attendance evidence |
| AQ-013 | Tutor chooses invalid SS Meet time. Which helper rejects it before external API call? | `tutor-dashboard-to-ss-meet.md` | `_coerce_meeting_start_time`, `_meeting_window_from_form`, `create_meet_link`, 15-minute slots |
| AQ-014 | Tutor schedule grid shows the wrong source or no schedule. Which source hierarchy should be checked? | `tutor-dashboard-to-ss-meet.md`, `enrollment-to-schedule-to-attendance.md` | `EnrollmentSchedule`, `has_schedule`, `source_type`, `candidate_availability`, active meet links |
| AQ-015 | Tutor opens a salary slip from the tutor portal. Which route prevents cross-tutor access and which template context is reused? | `tutor-dashboard-to-ss-meet.md`, `attendance-to-payroll-to-reconciliation.md` | `payout_detail`, `TutorPayout`, `payout.tutor_id != tutor.id`, `_build_fee_slip_template_context`, `tutor_portal_mode=True` |

## Initial Run Results

Initial automated term-coverage check against the docs:

| ID | Result | Notes |
| --- | --- | --- |
| AQ-001 | Pass | Payment, quota, refresh route, and quota test anchors found. |
| AQ-002 | Pass | Attendance, payroll, reconciliation, dashboard, and export anchors found. |
| AQ-003 | Pass | Data manager whitelist, read-only, restore, and backup anchors found. |
| AQ-004 | Pass | Portal request, admin review, and approved mutation anchors found. |
| AQ-005 | Pass | SS Meet API, create route, meet-link model, and active state anchors found. |
| AQ-006 | Pass | Candidate, token, signature, contract, and conversion anchors found. |
| AQ-007 | Pass | Session, backup, restore, bot route, and secret redaction anchors found. |
| AQ-008 | Fixed | First run failed because `_normalize_name`, `_find_student`, and `_find_tutor` were not named in the blueprint. The blueprint now includes them explicitly. |
| AQ-009 | Pass | Reporting service, Excel export, visible report, filters, and exported-value anchors found. |
| AQ-010 | Pass | Expense, closing, dashboard service, backdated edit, and period-risk anchors found. |
| AQ-011 | Pass | Manual drill scanned route decorators. Two public unauthenticated routes were expected QR verification links: `quota_invoice.invoice_verify` and `payroll.fee_slip_verify`; no unexpected admin page without login was identified. |
| AQ-012 | Pass with caution | Manual drill traced WhatsApp validation/review. Ambiguous or multi-enrollment matches are reviewable; an `invalid` review marks the linked evidence as needing manual correction and does not automatically delete attendance. |
| AQ-013 | Fixed | Focused tests found missing `_coerce_meeting_start_time`; helper was restored and documented in the SS Meet blueprint. |
| AQ-014 | Fixed | Focused tests found schedule-grid drift. Master and tutor portal grids now expose `has_schedule` and source metadata, prefer active `EnrollmentSchedule`, and fall back to candidate availability without inferring new lessons from raw attendance. |
| AQ-015 | Fixed | Focused tests found tutor portal payout slip route drift. `payout_detail` now renders the shared payroll fee-slip context in tutor portal mode and blocks payouts owned by another tutor. |

## Manual Drill Notes

### AQ-011 Auth Gate Drill

Route audit found the admin boundary is documented by `auth-admin-session-security.md`. The unauthenticated routes that looked suspicious were public verification pages, not admin pages:

- `quota_invoice.invoice_verify`: public invoice verification page for QR/barcode scans.
- `payroll.fee_slip_verify`: public fee slip verification page for QR scans.

These routes should remain public unless the product decision changes, but they must not expose admin controls.

### AQ-012 WhatsApp Ambiguity Drill

WhatsApp ambiguity is handled through:

- `WhatsAppIngestService.match_entities_from_group_context`
- `WhatsAppIngestService.find_validated_student_by_group`
- `WhatsAppIngestService.link_or_create_attendance`
- `attendance.review_whatsapp_attendance`
- `attendance.bulk_review_whatsapp_attendance`
- `_set_whatsapp_attendance_manual_review`

Important behavior: if multiple active enrollments share a WhatsApp group, the service can link the first candidate for manual review. Marking review status `invalid` records that the attendance needs manual correction; it does not automatically delete or unlink the attendance row. Future changes must preserve or deliberately revise that behavior with tests.

### AQ-013, AQ-014, AQ-015 Tutor Portal Drill

Focused tutor portal tests exposed three stale or incomplete runtime anchors:

- SS Meet time validation needed `_coerce_meeting_start_time` and default-hour lookup from active `EnrollmentSchedule`.
- Tutor schedule grids needed explicit `has_schedule` and `source_type` metadata so templates and future agents can distinguish enrollment schedule, candidate availability, and empty states.
- Tutor portal payout slip needed a read-only `payout_detail` route that checks `payout.tutor_id != tutor.id` before rendering the shared payroll fee-slip template.

The code was updated and the related blueprints now include these anchors.

## Failure Handling

When an audit question fails:

1. Do not treat the map as complete.
2. Add the missing feature or missing anchor to `blueprint-coverage-audit.md`.
3. Update the relevant blueprint with exact file/symbol anchors.
4. If the map reveals a possible code bug, open an implementation task or OpenSpec change before modifying runtime code.
