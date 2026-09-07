# Graph Report - aplikasi lembaga  (2026-09-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2262 nodes · 6066 edges · 124 communities (113 shown, 11 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 220 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a24c9e38`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_whatsapp_ingest_service.py
- Tutor
- routes/master.py
- routes/__init__.py
- BulkImportService
- enrollments.py
- WhatsAppIngestService
- datetime
- test_tutor_portal.py
- utils/__init__.py
- createBrowserManager
- quota_invoice.py
- StudentPayment
- DashboardService
- data_manager.py
- LegacyAlldataImportService
- route
- admin_required
- payments.py
- enhance
- routes/tutor_portal.py
- import_februari_2025.py
- session-runtime.js
- whatsapp-client.js
- forms/__init__.py
- routes/payroll.py
- test_attendance_list_view.py
- route
- PaymentService
- hermes_github_sync.py
- routes/recruitment.py
- ReportingService
- session-backup.js
- routes/attendance.py
- test_dashboard_service.py
- dashboard.py
- services/__init__.py
- PayrollService
- formatters.py
- app/__init__.py
- _delete_attendance_sessions_from_refs
- _ensure_tutor_portal_credentials
- config.js
- parser.js
- reports.py
- MonthlyClosing
- _normalize_email
- form
- package.json
- get_branding_logo_mark_data_uri
- TutorPortalRequest
- student_detail
- .get_monthly_trend
- create_app
- PricingRule
- login_required
- _get_tutor_payable_for_period
- test_payroll_fee_slip_proof_aggregation.py
- EnrollmentService
- OtherIncome
- TutorPayout
- _sync_candidate_documents
- startClient
- lembaga-daily-backup.sh
- payout_detail
- _build_invoice_lines
- reconciliation_service.py
- provision_new_server.sh
- chat-loader.js
- server.js
- AttendanceSession
- RecruitmentCandidate
- test_quota_total_sessions.py
- flask-client.js
- TutorPayoutProof
- TutorMeetLink
- DeletedAttendanceSession
- decode_public_id
- _get_payout_proof_contexts
- build_stored_evaluation_payload
- TutorPayoutForm
- test_attendance_calendar.py
- run.py
- lembaga-weekly-whatsapp-restart.sh
- restore-latest-backup.sh
- AttendanceSessionForm
- test_enrollment_list_view.py
- _delete_tutor_credential
- deploy.sh
- railway.json
- .get_balance
- test_public_id_routes.py
- .get_day_name
- lembaga-daily-backup-retention.fixture.test.sh
- test_global_searchable_select.py
- .get_attendance_count
- _next_tutor_portal_identity
- .get_tutor_salary_details
- run_command
- extensions.py
- .get_total_payable
- .get_active_enrollments
- .set_portal_password
- .check_portal_password
- entrypoint.sh
- run-connector.sh
- push_to_github.sh script
- create_checkpoint.sh

## God Nodes (most connected - your core abstractions)
1. `Tutor` - 108 edges
2. `Enrollment` - 94 edges
3. `AttendanceSession` - 82 edges
4. `Student` - 80 edges
5. `WhatsAppIngestService` - 79 edges
6. `Curriculum` - 66 edges
7. `Level` - 66 edges
8. `Subject` - 66 edges
9. `DashboardService` - 62 edges
10. `decode_public_id()` - 58 edges

## Surprising Connections (you probably didn't know these)
- `import_attendance()` --uses--> `Curriculum`  [INFERRED]
  import_februari_2025.py → app/models/master.py
- `import_payments()` --uses--> `Curriculum`  [INFERRED]
  import_februari_2025.py → app/models/master.py
- `import_attendance()` --uses--> `Level`  [INFERRED]
  import_februari_2025.py → app/models/master.py
- `import_payments()` --uses--> `Level`  [INFERRED]
  import_februari_2025.py → app/models/master.py
- `import_attendance()` --uses--> `Student`  [INFERRED]
  import_februari_2025.py → app/models/master.py

## Import Cycles
- None detected.

## Communities (124 total, 11 thin omitted)

### Community 0 - "test_whatsapp_ingest_service.py"
Cohesion: 0.07
Nodes (55): AttendancePeriodLock, Monthly lock that prevents WhatsApp rescans from mutating attendance., WhatsAppGroupParticipant, WhatsAppStudentValidation, as_date(), build_contact_group_membership_snapshot(), build_student_contact_suggestions(), build_student_group_suggestions() (+47 more)

### Community 1 - "Tutor"
Cohesion: 0.14
Nodes (48): Attendance Forms for Dashboard Keuangan LBB Super Smart Contains WTForms for…, Enrollment forms for Dashboard Keuangan LBB Super Smart Forms for creating and…, Enrollment, Enrollment model - represents a student taking a subject with a tutor, Curriculum, Level, Subject/Mata pelajaran model, Level/Jenjang pendidikan model (+40 more)

### Community 2 - "routes/master.py"
Cohesion: 0.08
Nodes (61): add_curriculum(), add_pricing(), add_student(), add_subject(), add_subject_tutor(), add_tutor(), api_get_pricing(), _build_tutor_subject_summary() (+53 more)

### Community 3 - "routes/__init__.py"
Cohesion: 0.06
Nodes (48): LoginForm, FlaskForm, Authentication forms for Dashboard Keuangan LBB Super Smart Contains LoginForm…, Form for user registration, Check if username already exists, Check if email already exists, RegisterForm, ExpenseForm (+40 more)

### Community 4 - "BulkImportService"
Cohesion: 0.12
Nodes (13): BulkImportService, Import structured CSV datasets into application tables., parametrize, _file_storage(), _make_test_app(), test_import_attendance_preserves_duplicate_sessions_same_student_date(), test_import_dataset_dispatches_every_dataset_handler(), test_import_dataset_rejects_empty_csv() (+5 more)

### Community 5 - "enrollments.py"
Cohesion: 0.08
Nodes (47): EnrollmentForm, EnrollmentScheduleForm, FlaskForm, Form for creating/editing enrollments, Form for creating enrollment schedule, add_enrollment(), _apply_selected_whatsapp_group(), _build_pricing_public_id_maps() (+39 more)

### Community 6 - "WhatsAppIngestService"
Cohesion: 0.12
Nodes (23): WhatsApp ingestion models for tutor attendance automation., WhatsAppEvaluation, WhatsAppGroup, WhatsAppMessage, WhatsAppTutorIdentityAlias, extract_lesson_schedule_subjects(), find_matching_enrollment_group(), merge_student_group_memberships() (+15 more)

### Community 7 - "datetime"
Cohesion: 0.07
Nodes (24): Attendance model for Dashboard Keuangan LBB Super Smart Contains…, Closing model for Dashboard Keuangan LBB Super Smart Contains MonthlyClosing…, DeletedEnrollment, Enrollment models for Dashboard Keuangan LBB Super Smart Contains Enrollment…, Temporary trash record for deleted enrollment and related data., Opaque public id for URLs., Expense model for Dashboard Keuangan LBB Super Smart Contains Expense model for…, Income models for Dashboard Keuangan LBB Super Smart Contains OtherIncome model… (+16 more)

### Community 8 - "test_tutor_portal.py"
Cohesion: 0.10
Nodes (29): EnrollmentSchedule, EnrollmentSchedule model - represents recurring lesson schedule, _attendance_validation_map(), _build_tutor_attendance_calendar(), _build_tutor_presensi_schedule_grid(), dashboard(), _ListPagination, _month_bounds() (+21 more)

### Community 9 - "utils/__init__.py"
Cohesion: 0.06
Nodes (33): login_required_custom(), manager_required(), Decorators utilities for Dashboard Keuangan LBB Super Smart Custom decorators…, Decorator to require manager or admin role, Custom login required decorator, Utils package for Dashboard Keuangan LBB Super Smart This package contains…, get_per_page(), pagination_url() (+25 more)

### Community 10 - "createBrowserManager"
Cohesion: 0.12
Nodes (39): asArray(), buildStorageKey(), createBrowserManager(), bindForm(), bindStandaloneControls(), buildUrlFromForm(), clearControl(), clearLastQuery() (+31 more)

### Community 11 - "quota_invoice.py"
Cohesion: 0.12
Nodes (37): _build_legacy_invoice_lines(), complete_invoice(), _decode_invoice_ref_or_404(), delete_invoice(), _encode_invoice_public_id(), _fetch_invoice(), _fetch_invoice_lines(), _get_student_by_ref_or_404() (+29 more)

### Community 12 - "StudentPayment"
Cohesion: 0.07
Nodes (18): Expense, Expense model for operational costs, Opaque public id for URLs., Convert to dictionary, Student Payment header model, Calculate payment amounts Returns dict with nominal_amount,…, Opaque public id for URLs., Get total nominal from all payment lines (+10 more)

### Community 13 - "DashboardService"
Cohesion: 0.08
Nodes (18): _compute_closing_data(), Calculate all KPI values needed for a monthly closing snapshot. Returns a dict…, DashboardService, Helper: return (month, year) for N months ago (n=1 = previous)., Sortable integer key for month/year comparisons., Service for dashboard calculations and reporting, Get top students by income for the given month/year, Get top subjects by income for the given month/year (+10 more)

### Community 14 - "data_manager.py"
Cohesion: 0.11
Nodes (33): delete_row(), export_sql(), _get_db_size(), _get_row_count(), index(), insert_row(), _parse_sql_statements(), login_required (+25 more)

### Community 15 - "LegacyAlldataImportService"
Cohesion: 0.14
Nodes (11): DatasetFile, LegacyAlldataImportService, Return a corrected payment date if this row should be re-dated, else None. Rows…, main(), _make_test_app(), Path, test_discover_dataset_files_skips_duplicate_content(), test_import_attendance_preserves_duplicate_sessions_same_student_date() (+3 more)

### Community 16 - "route"
Cohesion: 0.10
Nodes (31): add_payout(), api_quick_pay(), api_tutors_for_ocr(), auto_create_payout(), delete_payout(), fee_slip(), fee_slip_verify(), _get_payout_by_ref_or_404() (+23 more)

### Community 17 - "admin_required"
Cohesion: 0.21
Nodes (30): _bot_base_url(), bot_contact_directory(), bot_contact_directory_validate(), bot_contact_directory_validate_student(), bot_group_directory(), bot_group_directory_validate_student(), bot_groups(), _bot_request() (+22 more)

### Community 18 - "payments.py"
Cohesion: 0.14
Nodes (29): add_payment(), delete_payment(), detail_payment(), edit_payment(), _generate_receipt_number(), _get_payment_by_ref_or_404(), _get_student_by_ref_or_404(), get_student_enrollments() (+21 more)

### Community 19 - "enhance"
Cohesion: 0.17
Nodes (27): asArray(), blankOption(), createBrowserManager(), enhance(), buildOption(), chooseOption(), clearInvalid(), getDropdown() (+19 more)

### Community 20 - "routes/tutor_portal.py"
Cohesion: 0.15
Nodes (27): admin_dashboard_select(), admin_request_detail(), admin_requests(), _build_email_verification_url(), _build_google_callback_url(), _build_request_payload_items(), _build_schedule_request_display_rows(), _clear_portal_sessions() (+19 more)

### Community 21 - "import_februari_2025.py"
Cohesion: 0.17
Nodes (28): get_or_create_curriculum(), get_or_create_level(), get_or_create_subject(), get_pricing(), import_attendance(), import_enrollments(), import_expenses(), import_monthly_closing_jan() (+20 more)

### Community 22 - "session-runtime.js"
Cohesion: 0.13
Nodes (27): createInitialAutoSyncState(), createInitialState(), createInitialSyncProgress(), errorMessage(), extractSelfIdentity(), failSyncProgress(), finishSyncProgress(), fs (+19 more)

### Community 23 - "whatsapp-client.js"
Cohesion: 0.12
Nodes (27): buildMessageMedia(), buildSyncPayloadForGroups(), { classifyEvaluationMessage, parseEvaluationMessage }, {
  clearChromiumSingletonLocks,
  createInitialState,
  errorMessage,
  extractSelfIdentity,
  failSyncProgress,
  finishSyncProgress,
  isRecoverableWhatsAppRuntimeError,
  resetSessionState,
  startSyncProgress,
  updateAutoSyncState,
  updateSyncProgress,
}, clearClientReferences(), { Client, LocalAuth, MessageMedia }, config, createReadyPromise() (+19 more)

### Community 24 - "forms/__init__.py"
Cohesion: 0.12
Nodes (21): Forms package for Dashboard Keuangan LBB Super Smart This package contains all…, CurriculumForm, PricingRuleForm, FlaskForm, Master forms for Dashboard Keuangan LBB Super Smart Contains WTForms for…, Form for manual tutor include on a subject detail page., Form for creating/editing curriculum, Form for creating/editing pricing rule (+13 more)

### Community 25 - "routes/payroll.py"
Cohesion: 0.13
Nodes (26): _bot_request(), _build_fee_slip_template_context(), _build_fee_slip_whatsapp_message(), fee_slip_send_whatsapp(), _format_period_label(), _format_rupiah(), _get_tutor_whatsapp_contact_options(), _get_whatsapp_session_status() (+18 more)

### Community 26 - "test_attendance_list_view.py"
Cohesion: 0.18
Nodes (21): _apply_attendance_list_sort(), _attendance_csv_row(), _build_attendance_list_query(), _build_whatsapp_review_map(), _set_whatsapp_attendance_manual_review(), _sync_linked_whatsapp_evaluations(), _unlink_whatsapp_evaluations_before_attendance_delete(), _whatsapp_review_requires_manual_check() (+13 more)

### Community 27 - "route"
Cohesion: 0.16
Nodes (26): agree_interview(), bulk_teaching_options(), _candidate_from_ref(), crm_candidates(), crm_interview(), crm_rejected(), crm_selected(), crm_teaching_options() (+18 more)

### Community 28 - "PaymentService"
Cohesion: 0.12
Nodes (9): PaymentService, Get total income from student payments for specific month/year, Get total tutor payable allocated from student payments, Service class for payment-related operations, Get total margin from student payments, Get payment summary for specific month, Get income breakdown by subject, Get income breakdown by student (+1 more)

### Community 29 - "hermes_github_sync.py"
Cohesion: 0.24
Nodes (23): Any, CompletedProcess, Namespace, copy_file(), current_branch(), ensure_dirs(), ensure_origin_remote(), export_global_context_snapshot() (+15 more)

### Community 30 - "routes/recruitment.py"
Cohesion: 0.14
Nodes (23): _allowed_upload(), _availability_by_slot(), _build_candidate_availability_rows(), _build_contract_message(), _candidate_availability_slots_from_form(), _candidate_call(), _candidate_summary_items(), _contract_token() (+15 more)

### Community 31 - "ReportingService"
Cohesion: 0.11
Nodes (12): Export report to Excel file, Export report to PDF file, Get total income from student payments, Get total other income, Get total tutor payable from attendance, Get payable amount for specific tutor, Get paid amount for specific tutor, Service for generating reports and aggregations (+4 more)

### Community 32 - "session-backup.js"
Cohesion: 0.16
Nodes (23): backupPathFor(), { clearChromiumSingletonLocks }, config, createSessionBackup(), createTarArchive(), crypto, deleteSessionBackup(), ensureDir() (+15 more)

### Community 33 - "routes/attendance.py"
Cohesion: 0.17
Nodes (22): _attendance_session_delete_snapshot(), _build_attendance_period_lock_options(), _build_attendance_year_options(), _build_tutor_enrollment_map(), _compact_attendance_query_state(), _create_deleted_attendance_record(), _decode_optional_query_ref(), _decode_optional_ref_value() (+14 more)

### Community 34 - "test_dashboard_service.py"
Cohesion: 0.15
Nodes (14): Get tutor salary already paid/confirmed for this service month. Only…, Alias for tutor payout cash-out used by dashboard labels., Grand tutor payable outstanding (cumulative up to this month). Formula:…, Get grand total saldo = opening + income + other_income - expenses. Corresponds…, Get grand profit = Grand Total Saldo - Grand Hutang Gaji (cumulative tutor…, Estimasi sisa saldo = Grand Total Saldo - Estimasi Gaji Tutor (accrual), Find earliest month/year that can anchor cumulative dashboard math., Get opening cash balance (= previous month estimated remaining balance). (+6 more)

### Community 35 - "dashboard.py"
Cohesion: 0.17
Nodes (21): api_get_kpi(), api_get_payroll_summary(), api_get_trend(), architecture_diagram(), income_dashboard(), owner_dashboard(), _parse_month_year(), payroll_dashboard() (+13 more)

### Community 36 - "services/__init__.py"
Cohesion: 0.12
Nodes (11): AttendanceService, Attendance Service for Dashboard Keuangan LBB Super Smart Handles business…, Get attendance records for specific tutor, Calculate total salary for tutor based on attendance, Create multiple attendance records at once Args: enrollment_ids: List of…, Service class for attendance operations, Update attendance session, Cancel an attendance session (+3 more)

### Community 37 - "PayrollService"
Cohesion: 0.14
Nodes (12): PayrollService, Get list of tutors with unpaid balance, Create tutor payout record, Mark tutor payment for specific month, Get detailed salary information per tutor Includes: payable, paid, balance,…, Service class for payroll operations, Get overall payroll summary for the month, Get raw attendance total (sum of tutor_fee_amount for attended sessions).… (+4 more)

### Community 38 - "formatters.py"
Cohesion: 0.09
Nodes (21): format_bool(), format_currency(), format_currency_short(), format_date(), format_number(), format_percentage(), format_phone(), format_status() (+13 more)

### Community 39 - "app/__init__.py"
Cohesion: 0.12
Nodes (14): Return True if the current request expects a JSON response., _request_wants_json(), User model for authentication, Hash and set password, Check if password is correct, User, Config, DevelopmentConfig (+6 more)

### Community 40 - "_delete_attendance_sessions_from_refs"
Cohesion: 0.14
Nodes (21): _attendance_locked_message(), _attendance_redirect_filters(), bulk_delete_attendance(), bulk_review_whatsapp_attendance(), delete_attendance(), _delete_attendance_sessions_from_refs(), edit_attendance(), _ensure_attendance_date_unlocked() (+13 more)

### Community 41 - "_ensure_tutor_portal_credentials"
Cohesion: 0.20
Nodes (21): admin_credentials(), admin_delete_credential_tutor(), admin_reset_bulk_credential_passwords(), admin_reset_credential_password(), admin_send_bulk_credential_whatsapp(), admin_send_credential_whatsapp(), _bot_request(), _build_tutor_credential_whatsapp_template() (+13 more)

### Community 42 - "config.js"
Cohesion: 0.13
Nodes (14): { normalizeSyncStartAt }, { parseExcludedGroupNames }, path, isExcludedGroupName(), normalizeGroupName(), parseExcludedGroupNames(), normalizeSyncStartAt(), partitionMessagesBySyncStart() (+6 more)

### Community 43 - "parser.js"
Cohesion: 0.25
Nodes (19): classifyEvaluationMessage(), cleanQuotedLabelValue(), extractEvaluationBody(), extractTutorName(), findTitleMatch(), hasEvaluationKeyword(), hasLikelyTimeRange(), INDONESIAN_MONTHS (+11 more)

### Community 44 - "reports.py"
Cohesion: 0.13
Nodes (21): export_report(), monthly_report(), login_required, route, Reports routes for Dashboard Keuangan LBB Super Smart Handles report generation…, # TODO: Get reconciliation data, Landing page for reports module., Generate monthly financial report (+13 more)

### Community 45 - "MonthlyClosing"
Cohesion: 0.16
Nodes (17): MonthlyClosing, Monthly closing/snapshot model, _apply_closing_data(), closing_detail(), confirm_closing(), create_closing(), delete_closing(), monthly_closing() (+9 more)

### Community 46 - "_normalize_email"
Cohesion: 0.14
Nodes (20): _build_google_callback_url(), _bypass_tutor_for_candidate(), _candidate_from_contract_token(), _candidate_has_dashboard_access(), _candidate_has_submitted_form(), _candidate_profile_complete(), _create_tutor_from_candidate(), _fetch_google_userinfo() (+12 more)

### Community 47 - "form"
Cohesion: 0.27
Nodes (15): form(), _candidate(), _make_app(), test_bypass_tutor_profile_submit_generates_contract(), test_bypass_tutor_sees_profile_form(), test_contract_message_uses_gender_based_call(), test_dashboard_document_response_renders_html_document(), test_recruitment_availability_defaults_to_unavailable() (+7 more)

### Community 48 - "package.json"
Cohesion: 0.10
Nodes (19): dotenv, express, qrcode, dependencies, dotenv, express, qrcode, whatsapp-web.js (+11 more)

### Community 49 - "get_branding_logo_mark_data_uri"
Cohesion: 0.18
Nodes (14): Register context processors for templates, register_context_processors(), _branding_asset_candidates(), _file_to_data_uri(), get_branding_logo_data_uri(), get_branding_logo_mark_data_uri(), Branding and QR helpers., Return file content as a data URI if the file exists. (+6 more)

### Community 50 - "TutorPortalRequest"
Cohesion: 0.16
Nodes (17): Admin-reviewed request submitted by a tutor., TutorPortalRequest, _active_tutor_enrollments(), _allowed_upload(), _build_schedule_change_payload(), _build_schedule_change_rows(), _current_tutor(), payout_detail() (+9 more)

### Community 51 - "student_detail"
Cohesion: 0.16
Nodes (19): student_detail(), students_list(), build_postpaid_month_options(), _build_quota_summary(), calc_unpaid_attendance_by_month(), _first_of_month(), _get_student_invoice_history(), _get_student_quota_alert_map() (+11 more)

### Community 52 - ".get_monthly_trend"
Cohesion: 0.15
Nodes (8): Get total margin this month, Get estimated profit this month = margin + other_income - expenses, Monthly net cash = income + other_income - expenses (no opening balance).…, Get trend data for last N months using proper month arithmetic., Get total income from student payments this month, Get monthly income summary, Get other income (non-student) this month, Get total expenses this month

### Community 53 - "create_app"
Cohesion: 0.06
Nodes (61): create_app(), Register small presentation helpers used by templates., Register all blueprints, Register response hooks such as anti-cache headers for HTML pages., Register error handlers, Setup application logging, register_blueprints(), register_error_handlers() (+53 more)

### Community 54 - "PricingRule"
Cohesion: 0.22
Nodes (5): PricingRule, Pricing Rule model for managing student and tutor rates, Calculate margin per meeting, Calculate margin percentage, Get active pricing rule based on criteria

### Community 55 - "login_required"
Cohesion: 0.16
Nodes (18): add_attendance(), api_get_tutor_fee(), attendance_trash(), bulk_add_attendance(), calendar_view(), monthly_summary(), login_required, route (+10 more)

### Community 56 - "_get_tutor_payable_for_period"
Cohesion: 0.13
Nodes (18): api_tutor_balance(), api_tutor_info(), _get_carried_shortfall_for_period(), _get_tutor_attendance_for_period(), _get_tutor_by_ref_or_404(), _get_tutor_paid_for_period(), _get_tutor_payable_for_period(), Display list of pending transfers Can be exported to Excel for bulk transfer (+10 more)

### Community 57 - "test_payroll_fee_slip_proof_aggregation.py"
Cohesion: 0.34
Nodes (17): _get_display_payout_proof_contexts(), Aggregate transfer proofs across every payout shown on this slip. A…, fixture, app(), _line(), _payout(), _proof(), Functional tests for period-wide transfer-proof aggregation on fee slips. These… (+9 more)

### Community 58 - "EnrollmentService"
Cohesion: 0.12
Nodes (10): EnrollmentService, Enrollment service for Dashboard Keuangan LBB Super Smart Contains business…, Calculate remaining meetings for this month Args: enrollment_id: Enrollment ID…, Service class for enrollment-related operations, Deactivate enrollment (mark as completed/inactive) Args: enrollment_id:…, Get active enrollments Args: student_id: Filter by student (optional) tutor_id:…, Calculate total tutor payable for this enrollment in given month Args:…, Create new enrollment Args: student_id: Student ID subject_id: Subject ID… (+2 more)

### Community 59 - "OtherIncome"
Cohesion: 0.22
Nodes (5): OtherIncome, Other income model - Pemasukan lain-lain, Opaque public id for URLs., Get month from income_date, Get year from income_date

### Community 61 - "TutorPayout"
Cohesion: 0.09
Nodes (14): Tutor Payout model - Header pembayaran gaji tutor Satu baris = satu transaksi…, Opaque public id for URLs., Get all service months in this payout, Tutor Payout Line model - Detail pembayaran per bulan layanan Satu payout bisa…, Get human-readable service period, TutorPayout, TutorPayoutLine, Dashboard Service for Dashboard Keuangan LBB Super Smart Handles all KPI… (+6 more)

### Community 62 - "_sync_candidate_documents"
Cohesion: 0.21
Nodes (16): _application_kind(), _build_contract_text(), _build_offering_text(), _candidate_applications(), _candidate_file_flags(), contract(), _crop_signature_data_url(), dashboard() (+8 more)

### Community 63 - "startClient"
Cohesion: 0.27
Nodes (15): clearChromiumSingletonLocks(), checkReadyClient(), destroyClientInstance(), handleRuntimeFailure(), logBotEvent(), logout(), recoverFromRuntimeError(), rejectReadyPromise() (+7 more)

### Community 64 - "lembaga-daily-backup.sh"
Cohesion: 0.13
Nodes (14): BACKUP_ROOT, BOT_BACKUP_URL, BOT_CONTAINER, BOT_LOCAL_RETENTION, CONFIG_DIR, DB_CONTAINER, GITHUB_RETENTION, GITHUB_TOKEN_FILE (+6 more)

### Community 65 - "payout_detail"
Cohesion: 0.18
Nodes (14): fee_slip_pdf(), _get_display_payout_lines(), _get_period_payouts_for_display(), _get_sessions_for_payout(), _is_previous_shortfall_line(), payout_detail(), Display payout detail with session list for review., Return list of AttendanceSession records covered by this payout. (+6 more)

### Community 66 - "_build_invoice_lines"
Cohesion: 0.18
Nodes (14): _build_invoice_lines(), _coerce_int_list(), create_invoice(), _error_response(), _parse_service_month(), Konversi aman ke integer., Parse YYYY-MM atau YYYY-MM-DD menjadi tanggal awal bulan., Ubah list/string menjadi list integer unik dengan urutan terjaga. (+6 more)

### Community 67 - "reconciliation_service.py"
Cohesion: 0.16
Nodes (9): Reconciliation Service for Dashboard Keuangan LBB Super Smart Handles…, Get reconciliation data for specific tutor, Get reconciliation data for all tutors, Service for reconciliation operations, Get total tutor payable amount from student collections This is the hutang gaji…, Get total tutor salary accrual from attendance sessions This is based on actual…, Get total tutor payout that has been paid, Get reconciliation gap analysis Returns gap between payable from collection and… (+1 more)

### Community 68 - "provision_new_server.sh"
Cohesion: 0.37
Nodes (12): compose(), die(), env_set_if_missing_or_placeholder(), log(), main(), need_cmd(), random_secret(), restore_archive() (+4 more)

### Community 70 - "chat-loader.js"
Cohesion: 0.31
Nodes (11): createDirectGroupChat(), errorMessage(), fetchMessagesByGroupId(), listBrowserGroupIds(), listChatsResilient(), loadChatsInBatches(), serializeDirectMessageId(), serializeWid() (+3 more)

### Community 71 - "server.js"
Cohesion: 0.18
Nodes (11): app, { backupPathFor }, config, express, pngDimensions(), puppeteer, pxToInches(), renderHtmlToSinglePagePdf() (+3 more)

### Community 72 - "AttendanceSession"
Cohesion: 0.12
Nodes (12): AttendanceSession, Attendance/Presensi model - tracks each lesson session, Mark session as attended, Mark session as cancelled, Get month from session date, Get year from session date, Manual include/exclude override for tutor visibility on subject detail., SubjectTutorAssignment (+4 more)

### Community 74 - "RecruitmentCandidate"
Cohesion: 0.18
Nodes (5): Hash and set the candidate dashboard password., Check the candidate dashboard password., Tutor applicant captured from the recruitment form., RecruitmentCandidate, setter

### Community 75 - "test_quota_total_sessions.py"
Cohesion: 0.18
Nodes (9): Replace payment lines from submitted enrollment/session rows., _sync_payment_lines_from_form(), calc_quota(), count_quota_alerts(), Hitung total quota berbayar vs total terpakai untuk sebuah enrollment.…, Hitung jumlah siswa aktif yang memiliki minimal satu enrollment dengan sisa…, _make_test_app(), test_generate_receipt_number_increments_per_payment_date() (+1 more)

### Community 76 - "flask-client.js"
Cohesion: 0.24
Nodes (9): chunkMessages(), config, mergeSyncResult(), postSingleSyncPayload(), postSyncPayload(), assert, {
  chunkMessages,
  postSyncPayload,
}, configPath (+1 more)

### Community 77 - "TutorPayoutProof"
Cohesion: 0.20
Nodes (6): Uploaded transfer proof files for one tutor payout., TutorPayoutProof, _backfill_legacy_payout_proof(), Upload one or more transfer proof files., Copy legacy single proof_image into the multi-proof table once., upload_proof()

### Community 78 - "TutorMeetLink"
Cohesion: 0.18
Nodes (10): Reusable SS Meet link generated from the tutor portal., TutorMeetLink, _active_meet_links_for_enrollments(), _attach_meet_links_to_schedule_grid(), _coerce_meeting_start_time(), create_meet_link(), _default_meeting_hour_for_enrollment(), _meeting_window_from_form() (+2 more)

### Community 80 - "DeletedAttendanceSession"
Cohesion: 0.22
Nodes (8): DeletedAttendanceSession, Temporary trash record for attendance sessions deleted from the UI., _get_deleted_attendance_by_ref_or_404(), _parse_snapshot_date(), _parse_snapshot_datetime(), Restore one deleted attendance session from the temporary trash., _restore_attendance_session_from_trash(), restore_deleted_attendance()

### Community 81 - "decode_public_id"
Cohesion: 0.22
Nodes (9): edit_pricing(), _get_level_by_ref_or_404(), _get_pricing_by_ref_or_404(), Resolve opaque pricing rule ref to model instance., Resolve opaque level ref to model instance., decode_public_id(), _get_serializer(), Public ID helpers for opaque URLs. (+1 more)

### Community 82 - "_get_payout_proof_contexts"
Cohesion: 0.22
Nodes (10): _build_proof_context(), _get_payout_proof_contexts(), _payroll_proof_upload_dir(), _proof_context_from_path(), _proof_download_url(), _proof_file_exists(), Build the correct proof URL for admin payroll or tutor portal views., Prepare URLs and file metadata for uploaded proof files. (+2 more)

### Community 83 - "build_stored_evaluation_payload"
Cohesion: 0.27
Nodes (8): build_stored_evaluation_payload(), extract_labeled_value(), extract_student_hint(), extract_subject_hint(), is_stored_evaluation_message(), parse_loose_reported_date(), date, truncate_text()

### Community 85 - "TutorPayoutForm"
Cohesion: 0.22
Nodes (6): FlaskForm, Payroll forms for Dashboard Keuangan LBB Super Smart Contains WTForms for tutor…, Form for creating tutor payout, Validate amount is positive, Validate tutor exists, TutorPayoutForm

### Community 86 - "test_attendance_calendar.py"
Cohesion: 0.44
Nodes (7): _build_lesson_calendar(), _normalize_calendar_period(), _make_test_app(), date, _seed_calendar_data(), test_build_lesson_calendar_filters_by_student_and_tutor_from_attendance(), test_build_lesson_calendar_uses_attendance_sessions_as_source()

### Community 87 - "run.py"
Cohesion: 0.28
Nodes (6): command, _apply_schema_patches(), drop_db(), init_db(), Initialize the database (create all tables + apply extra DDL patches)., Apply idempotent DDL patches for columns/tables added after initial deployment.…

### Community 88 - "lembaga-weekly-whatsapp-restart.sh"
Cohesion: 0.25
Nodes (8): BACKUP_ROOT, BOT_CONTAINER, BOT_SESSION_URL, HEALTH_TIMEOUT_SECONDS, LOCK_FILE, MAX_BACKUP_AGE_SECONDS, session_ready(), lembaga-weekly-whatsapp-restart.sh script

### Community 89 - "restore-latest-backup.sh"
Cohesion: 0.56
Nodes (8): compose(), die(), log(), main(), restore_database(), restore_whatsapp(), restore-latest-backup.sh script, wait_for_database()

### Community 91 - "AttendanceSessionForm"
Cohesion: 0.29
Nodes (6): _attendance_enrollment_label(), AttendanceSessionForm, BulkAttendanceForm, FlaskForm, Form for recording attendance session, Form for bulk adding attendance

### Community 92 - "test_enrollment_list_view.py"
Cohesion: 0.57
Nodes (5): _build_enrollment_list_query(), _make_test_app(), _seed_enrollments(), test_build_enrollment_list_query_filters_by_status_and_search_term(), test_build_enrollment_list_query_matches_tutor_subject_and_group_name()

### Community 93 - "_delete_tutor_credential"
Cohesion: 0.48
Nodes (7): _delete_student_invoices(), _delete_student_payment_lines(), _delete_tutor_credential(), _delete_tutor_payouts(), _execute_ids(), _student_invoice_ids_for_enrollments(), _student_payment_ids_for_enrollments()

### Community 94 - "deploy.sh"
Cohesion: 0.52
Nodes (6): err(), info(), ok(), deploy.sh script, step(), warn()

### Community 95 - "railway.json"
Cohesion: 0.29
Nodes (6): build, builder, deploy, restartPolicyMaxRetries, startCommand, $schema

### Community 97 - ".get_balance"
Cohesion: 0.33
Nodes (3): Get total payable amount for this tutor If month is provided, get for specific…, Get total paid amount for this tutor If month is provided, get for specific…, Get unpaid balance for this tutor

### Community 99 - "test_public_id_routes.py"
Cohesion: 0.60
Nodes (5): _read(), test_quota_invoice_list_attaches_public_invoice_refs(), test_routes_decode_public_refs_for_master_attendance_and_payroll(), test_target_models_expose_public_id_properties(), test_templates_use_public_refs_in_links_and_browser_fetches()

### Community 100 - ".get_day_name"
Cohesion: 0.50
Nodes (4): Convert day number to day name, _apply_approved_request(), _apply_weekly_schedule_grid_request(), review_request()

### Community 101 - "lembaga-daily-backup-retention.fixture.test.sh"
Cohesion: 0.40
Nodes (4): GITHUB_RETENTION, RETENTION_DELETE_LIMIT, lembaga-daily-backup-retention.fixture.test.sh script, tag

### Community 102 - "test_global_searchable_select.py"
Cohesion: 0.70
Nodes (4): _read(), test_base_inline_enhancer_is_fallback_only(), test_base_layouts_reference_shared_searchable_select_assets(), test_shared_module_contract()

### Community 104 - "_next_tutor_portal_identity"
Cohesion: 0.50
Nodes (4): _collect_used_portal_identity_sequences(), _next_portal_username(), _next_tutor_portal_identity(), _portal_identity_date()

### Community 106 - "run_command"
Cohesion: 0.67
Nodes (3): main(), Run a shell command and return success status, run_command()

## Knowledge Gaps
- **100 isolated node(s):** `TableSpec`, `assert`, `filters`, `test`, `GITHUB_RETENTION` (+95 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Tutor` connect `Tutor` to `test_whatsapp_ingest_service.py`, `routes/master.py`, `BulkImportService`, `enrollments.py`, `WhatsAppIngestService`, `datetime`, `test_tutor_portal.py`, `StudentPayment`, `LegacyAlldataImportService`, `routes/tutor_portal.py`, `import_februari_2025.py`, `forms/__init__.py`, `routes/payroll.py`, `test_attendance_list_view.py`, `routes/recruitment.py`, `routes/attendance.py`, `test_dashboard_service.py`, `app/__init__.py`, `_ensure_tutor_portal_credentials`, `_normalize_email`, `test_payroll_fee_slip_proof_aggregation.py`, `TutorPayout`, `reconciliation_service.py`, `AttendanceSession`, `test_quota_total_sessions.py`, `TutorPayoutForm`, `test_attendance_calendar.py`, `test_enrollment_list_view.py`, `.get_balance`, `.set_portal_password`, `.check_portal_password`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `decode_public_id()` connect `decode_public_id` to `routes/master.py`, `routes/__init__.py`, `enrollments.py`, `utils/__init__.py`, `quota_invoice.py`, `route`, `payments.py`, `routes/tutor_portal.py`, `routes/payroll.py`, `route`, `routes/recruitment.py`, `routes/attendance.py`, `_delete_attendance_sessions_from_refs`, `_ensure_tutor_portal_credentials`, `TutorPortalRequest`, `_get_tutor_payable_for_period`, `TutorMeetLink`, `DeletedAttendanceSession`, `.get_day_name`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `create_app()` connect `create_app` to `app/__init__.py`, `DashboardService`, `LegacyAlldataImportService`, `form`, `get_branding_logo_mark_data_uri`, `import_februari_2025.py`, `run.py`, `TutorPayout`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 58 inferred relationships involving `datetime` (e.g. with `.get_attendance_by_tutor()` and `.get_monthly_summary()`) actually correct?**
  _`datetime` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Tutor` (e.g. with `AttendanceSession` and `TutorPayout`) actually correct?**
  _`Tutor` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `AttendanceSession` (e.g. with `Enrollment` and `Tutor`) actually correct?**
  _`AttendanceSession` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Student` (e.g. with `import_attendance()` and `import_enrollments()`) actually correct?**
  _`Student` has 3 INFERRED edges - model-reasoned connections that need verification._