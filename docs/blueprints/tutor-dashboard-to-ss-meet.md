# Tutor Dashboard To SS Meet

## Purpose

Map the tutor portal dashboard, visible teaching schedule, attendance calendar, active meeting links, and SS Meet link creation flow.

## Source Of Truth

- Tutor identity and credentials: `Tutor` in `app/models/master.py`
- Portal session: tutor portal session keys in `app/routes/tutor_portal.py`
- Tutor request records: `TutorPortalRequest` in `app/models/tutor_portal.py`
- Meeting links: `TutorMeetLink` in `app/models/tutor_portal.py`
- Payout read-only slip context: `TutorPayout` plus payroll fee-slip helper
- Enrollment/schedule context: `Enrollment` and `EnrollmentSchedule`
- Attendance calendar context: `AttendanceSession`
- SS Meet API response: consumed through `_ss_meet_api_request`

## Entry Points

- Login and onboarding: `login`, `google_login`, `google_callback`, `verify`, `verify_email`, `onboarding`, `logout`
- Admin tutor dashboard selection: `admin_dashboard_select`
- Tutor dashboard: `dashboard`
- Tutor payout slip: `payout_detail`, `_build_fee_slip_template_context`
- SS Meet link creation: `create_meet_link`, `_default_meeting_hour_for_enrollment`, `_coerce_meeting_start_time`, `_meeting_window_from_form`
- Schedule/profile requests: `request_schedule_change`, `request_availability`, `request_profile_update`
- Admin request review: `admin_requests`, `admin_request_detail`, `review_request`, `_apply_approved_request`

## Route And Service Path

1. Tutor authenticates through portal credentials, email token, or Google callback.
2. Portal checks onboarding and selected admin view state.
3. Dashboard builds tutor-scoped enrollments, attendance calendar, presensi schedule grid, validated attendance, payout rows, request rows, and active meet links.
4. Active meet links are fetched through `_active_meet_links_for_enrollments` and attached to the schedule grid through `_attach_meet_links_to_schedule_grid`.
5. Tutor or admin creates a meet link through `create_meet_link`; the default meeting hour comes from the first active `EnrollmentSchedule` and then `_ss_meet_api_request` is called.
6. The resulting meeting link is stored in `TutorMeetLink` and shown on the tutor dashboard while active.
7. Tutor opens a payout slip through `payout_detail`; the route aborts unless `payout.tutor_id == tutor.id` and reuses the payroll fee-slip template in tutor portal mode.

## User-Facing Surfaces

- Tutor login, Google login, email verification, onboarding
- Tutor dashboard root `/tutor/`
- Tutor attendance calendar and presensi schedule grid
- Meeting link buttons and active link display
- Read-only tutor payout/fee slip detail
- Admin dashboard-select mode
- Tutor request forms and admin request review pages

## Invariants

- Tutors must only see their own enrollments, schedules, attendance, uploads, requests, and meet links.
- Admin-selected tutor dashboard view must remain read-limited to authorized admin users.
- SS Meet link creation must be tied to an active enrollment context.
- Stored meet links must have enough metadata to determine whether they are active.
- Tutor payout slip routes must be read-only and tutor-scoped.
- Schedule/profile requests must not mutate operational data until approved.
- External SS Meet errors must not corrupt existing schedule or attendance records.

## Known Fragility

- Dashboard combines many contexts: tutor credentials, onboarding, attendance, enrollments, schedules, requests, WhatsApp status, and SS Meet.
- Meeting windows and active link expiration depend on time normalization.
- Admin dashboard-select mode must not accidentally grant mutation access to tutor-only actions.
- SS Meet API configuration is external and may fail independently of the Flask app.
- Meeting time validation accepts 15-minute slots from 07:00 through 21:00; invalid time parsing must fail before calling SS Meet.
- Tutor portal payout slip reuses payroll context and proof-file routing; changing payroll fee-slip helpers can affect tutor-facing slip display.

## Required Checks

- `openspec validate --specs --strict --no-interactive`
- `tests/test_tutor_portal.py` or focused tutor portal tests when dashboard, request, or credential behavior changes
- Payroll/fee-slip focused checks when tutor payout slip rendering changes
- Container route bootstrap when tutor portal imports or app startup change
- Secret-redacted SS Meet configuration check when API integration changes
- Manual dashboard check if templates or meet-link rendering change

## Diagram

```mermaid
flowchart LR
  Login[Tutor login / Google / email token] --> Session[Portal tutor session]
  Session --> Onboarding[Onboarding gate]
  Onboarding --> Dashboard[Tutor dashboard]
  Dashboard --> Enrollments[Active tutor enrollments]
  Dashboard --> Attendance[Attendance calendar and validation]
  Dashboard --> Requests[TutorPortalRequest rows]
  Dashboard --> PayoutSlip[Tutor payout slip]
  Enrollments --> ScheduleGrid[Schedule grid]
  ScheduleGrid --> ActiveLinks[TutorMeetLink active links]
  ScheduleGrid --> CreateMeet[create_meet_link]
  CreateMeet --> SSMeet[_ss_meet_api_request]
  SSMeet --> StoredLink[TutorMeetLink]
  StoredLink --> ActiveLinks
```
