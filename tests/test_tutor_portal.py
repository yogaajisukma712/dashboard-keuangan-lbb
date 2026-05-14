from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask

from app import db
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    Level,
    Student,
    Subject,
    Tutor,
    TutorPortalRequest,
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppMessage,
)
from app.routes.tutor_portal import (
    ATTENDANCE_TABLE_PER_PAGE,
    _ListPagination,
    _build_schedule_change_rows,
    _build_schedule_request_display_rows,
    _build_tutor_attendance_calendar,
    _build_tutor_presensi_schedule_grid,
    _month_bounds,
    _normalize_portal_attendance_period,
    _validated_tutor_attendance_sessions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _seed_tutor_portal_attendance():
    curriculum = Curriculum(name="K13")
    level = Level(name="SMA")
    subject = Subject(name="Matematika")
    tutor = Tutor(tutor_code="TTR-PORTAL", name="Dinda", is_active=True)
    other_tutor = Tutor(tutor_code="TTR-OTHER", name="Listya", is_active=True)
    student = Student(student_code="STD-PORTAL", name="Nadine")
    db.session.add_all([curriculum, level, subject, tutor, other_tutor, student])
    db.session.flush()

    enrollment = Enrollment(
        student_id=student.id,
        subject_id=subject.id,
        tutor_id=tutor.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="10",
        student_rate_per_meeting=150000,
        tutor_rate_per_meeting=80000,
        status="active",
    )
    other_enrollment = Enrollment(
        student_id=student.id,
        subject_id=subject.id,
        tutor_id=other_tutor.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="10",
        student_rate_per_meeting=150000,
        tutor_rate_per_meeting=80000,
        status="active",
    )
    db.session.add_all([enrollment, other_enrollment])
    db.session.flush()

    valid_may = AttendanceSession(
        enrollment_id=enrollment.id,
        student_id=student.id,
        tutor_id=tutor.id,
        subject_id=subject.id,
        session_date=date(2026, 5, 10),
        status="attended",
        student_present=True,
        tutor_present=True,
        tutor_fee_amount=80000,
    )
    pending_may = AttendanceSession(
        enrollment_id=enrollment.id,
        student_id=student.id,
        tutor_id=tutor.id,
        subject_id=subject.id,
        session_date=date(2026, 5, 11),
        status="attended",
        student_present=True,
        tutor_present=True,
        tutor_fee_amount=80000,
    )
    april = AttendanceSession(
        enrollment_id=enrollment.id,
        student_id=student.id,
        tutor_id=tutor.id,
        subject_id=subject.id,
        session_date=date(2026, 4, 20),
        status="attended",
        student_present=True,
        tutor_present=True,
        tutor_fee_amount=80000,
    )
    other_tutor_session = AttendanceSession(
        enrollment_id=other_enrollment.id,
        student_id=student.id,
        tutor_id=other_tutor.id,
        subject_id=subject.id,
        session_date=date(2026, 5, 12),
        status="attended",
        student_present=True,
        tutor_present=True,
        tutor_fee_amount=80000,
    )
    db.session.add_all([valid_may, pending_may, april, other_tutor_session])
    db.session.flush()

    group = WhatsAppGroup(whatsapp_group_id="group-portal", name="Kelas Nadine")
    db.session.add(group)
    db.session.flush()
    base_time = datetime(2026, 5, 12, 8, 0)
    evaluations = []
    for index, (session, status) in enumerate(
        [
            (valid_may, "valid"),
            (pending_may, "pending"),
            (april, "valid"),
            (other_tutor_session, "valid"),
        ],
        start=1,
    ):
        message = WhatsAppMessage(
            whatsapp_message_id=f"portal-message-{index}",
            group_id=group.id,
            sent_at=base_time + timedelta(minutes=index),
            body="Presensi",
        )
        db.session.add(message)
        db.session.flush()
        evaluations.append(
            WhatsAppEvaluation(
                message_id=message.id,
                group_id=group.id,
                attendance_date=session.session_date,
                attendance_session_id=session.id,
                manual_review_status=status,
                updated_at=base_time + timedelta(minutes=index),
            )
        )
    db.session.add_all(evaluations)
    db.session.commit()
    return {
        "tutor": tutor,
        "valid_may": valid_may,
        "pending_may": pending_may,
        "april": april,
    }


def test_tutor_portal_attendance_period_is_limited_to_april_2026_or_newer():
    assert _normalize_portal_attendance_period(3, 2026, date(2026, 4, 1)) == (4, 2026)
    assert _normalize_portal_attendance_period(4, 2026, date(2026, 4, 1)) == (4, 2026)
    assert _normalize_portal_attendance_period(5, 2026, date(2026, 4, 1)) == (5, 2026)


def test_tutor_portal_attendance_table_uses_selected_month_and_valid_reviews_only():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_tutor_portal_attendance()
        may_start, may_end = _month_bounds(5, 2026)
        april_start, april_end = _month_bounds(4, 2026)

        may_sessions, may_validation_map = _validated_tutor_attendance_sessions(
            seeded["tutor"].id,
            may_start,
            may_end,
        )
        april_sessions, _april_validation_map = _validated_tutor_attendance_sessions(
            seeded["tutor"].id,
            april_start,
            april_end,
        )

        assert [session.id for session in may_sessions] == [seeded["valid_may"].id]
        assert may_validation_map[seeded["valid_may"].id] == "valid"
        assert may_validation_map[seeded["pending_may"].id] == "pending"
        assert [session.id for session in april_sessions] == [seeded["april"].id]


def test_tutor_portal_attendance_calendar_uses_valid_reviews_only():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_tutor_portal_attendance()

        calendar = _build_tutor_attendance_calendar(
            seeded["tutor"].id,
            month=5,
            year=2026,
            min_date=date(2026, 4, 1),
        )
        calendar_items = [
            item
            for week in calendar["weeks"]
            for day in week
            for item in day["items"]
        ]

        assert calendar["session_count"] == 1
        assert calendar["active_day_count"] == 1
        assert [item["id"] for item in calendar_items] == [seeded["valid_may"].id]
        assert all(item["review_status"] == "valid" for item in calendar_items)


def test_tutor_portal_teaching_schedule_uses_validated_january_to_may_attendance():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_tutor_portal_attendance()

        schedule_grid = _build_tutor_presensi_schedule_grid(seeded["tutor"].id)
        schedule_items = [
            item
            for row in schedule_grid["rows"]
            for cell in row["cells"]
            for item in cell["items"]
        ]

        assert schedule_grid["source_period_label"] == "Januari-Mei 2026"
        assert schedule_grid["lesson_count"] == 1
        assert [item["enrollment_ref"] for item in schedule_items] == [
            seeded["valid_may"].enrollment.public_id
        ]
        assert schedule_items[0]["weekday"] == seeded["april"].session_date.weekday()
        assert schedule_items[0]["source"] == "validated_attendance"


def test_tutor_portal_attendance_pagination_limits_table_to_10_rows():
    items = list(range(23))

    first_page = _ListPagination(items, page=1, per_page=ATTENDANCE_TABLE_PER_PAGE)
    third_page = _ListPagination(items, page=3, per_page=ATTENDANCE_TABLE_PER_PAGE)

    assert len(first_page.items) == 10
    assert first_page.first == 1
    assert first_page.last == 10
    assert first_page.total == 23
    assert first_page.pages == 3
    assert first_page.has_next is True
    assert third_page.items == [20, 21, 22]
    assert third_page.first == 21
    assert third_page.last == 23
    assert third_page.has_next is False


def test_schedule_request_payload_is_formatted_as_admin_grid_rows():
    rows = _build_schedule_request_display_rows(
        {
            "mode": "weekly_grid",
            "slots": [
                {
                    "weekday": 0,
                    "day_name": "Senin",
                    "hour": 8,
                    "start_time": "08:00",
                    "end_time": "09:00",
                    "state": "enrollment",
                    "enrollment_id": 1,
                    "student_name": "Nadine",
                    "subject_name": "Matematika",
                },
                {
                    "weekday": 1,
                    "day_name": "Selasa",
                    "hour": 8,
                    "start_time": "08:00",
                    "end_time": "09:00",
                    "state": "available",
                },
                {
                    "weekday": 2,
                    "day_name": "Rabu",
                    "hour": 8,
                    "start_time": "08:00",
                    "end_time": "09:00",
                    "state": "unavailable",
                },
            ],
        }
    )

    first_row = rows[0]
    assert first_row["hour"] == 8
    assert first_row["cells"][0]["class"] == "is-enrollment"
    assert first_row["cells"][0]["items"][0]["label"] == "Nadine - Matematika"
    assert first_row["cells"][1]["class"] == "is-available"
    assert first_row["cells"][1]["items"][0]["label"] == "Available"
    assert first_row["cells"][2]["class"] == "is-unavailable"
    assert first_row["cells"][2]["items"][0]["label"] == "Tidak Available"
    assert first_row["cells"][3]["class"] == "is-empty"


def test_schedule_change_rows_use_latest_approved_availability_snapshot():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        tutor = Tutor(tutor_code="TTR-SCHEDULE-SNAPSHOT", name="Dinda", is_active=True)
        db.session.add(tutor)
        db.session.flush()
        db.session.add(
            TutorPortalRequest(
                tutor_id=tutor.id,
                request_type="schedule_change",
                status="approved",
                reviewed_at=datetime(2026, 5, 14, 3, 31),
                payload_json={
                    "mode": "weekly_grid",
                    "slots": [
                        {"weekday": 0, "hour": 17, "state": "unavailable"},
                        {"weekday": 1, "hour": 10, "state": "available"},
                    ],
                },
            )
        )
        db.session.commit()

        rows = _build_schedule_change_rows(tutor.id)
        cells = {
            (cell["weekday"], cell["hour"]): cell
            for row in rows
            for cell in row["cells"]
        }

        assert cells[(0, 17)]["selected"] == "unavailable"
        assert cells[(1, 10)]["selected"] == "available"


def test_tutor_portal_routes_and_templates_are_registered_in_source():
    init_text = (PROJECT_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    routes_init = (PROJECT_ROOT / "app" / "routes" / "__init__.py").read_text(
        encoding="utf-8"
    )
    route_text = (PROJECT_ROOT / "app" / "routes" / "tutor_portal.py").read_text(
        encoding="utf-8"
    )
    config_text = (PROJECT_ROOT / "config.py").read_text(encoding="utf-8")
    model_text = (PROJECT_ROOT / "app" / "models" / "master.py").read_text(
        encoding="utf-8"
    )
    dashboard_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "dashboard.html"
    ).read_text(encoding="utf-8")
    base_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "base.html"
    ).read_text(encoding="utf-8")
    admin_select_text = (
        PROJECT_ROOT
        / "app"
        / "templates"
        / "tutor_portal"
        / "admin_dashboard_select.html"
    ).read_text(encoding="utf-8")

    assert "tutor_portal_bp" in routes_init
    assert "app.register_blueprint(tutor_portal_bp)" in init_text
    assert "URLSafeTimedSerializer" in route_text
    assert "portal_username" in model_text
    assert "set_portal_password" in model_text
    assert "check_portal_password" in route_text
    assert "portal_must_change_password" in route_text
    assert "login_method == \"email\"" not in route_text
    assert "def _tutor_onboarding_step" not in route_text
    assert "tutor.set_portal_password(new_password)" in route_text
    assert "tutor.email = email" in route_text
    assert "Password baru dan Gmail sudah disimpan" in route_text
    assert "Admin perlu cek koneksi SMTP" in route_text
    assert "verify_email" in route_text
    assert "email.endswith(\"@gmail.com\")" in route_text
    assert "TUTOR_PORTAL_MIN_DATE" in route_text
    assert "_normalize_portal_attendance_period" in route_text
    assert "_validated_tutor_attendance_sessions" in route_text
    assert "ATTENDANCE_TABLE_PER_PAGE = 10" in route_text
    assert "_ListPagination" in route_text
    assert "validation_map.get(session.id) == \"valid\"" in route_text
    assert "_build_tutor_attendance_calendar" in route_text
    assert "AttendanceSession.session_date.between(period_start, period_end)" in route_text
    assert "validation_map.get(session_item.id) == \"valid\"" in route_text
    assert "_attach_meet_links_to_schedule_grid(" in route_text
    assert "_build_tutor_weekly_schedule_grid(tutor.id)" in route_text
    assert "Januari-Mei 2026" in route_text
    assert "TutorPortalRequest" in route_text
    assert "request_schedule_change" in route_text
    assert 'methods=["GET", "POST"]' in route_text
    assert "_build_schedule_change_payload" in route_text
    assert "_apply_weekly_schedule_grid_request" in route_text
    assert "def admin_request_detail" in route_text
    assert "_build_request_payload_items" in route_text
    assert "_build_tutor_weekly_schedule_grid(tutor_id)" in route_text
    assert "request_availability" in route_text
    assert "request_profile_update" in route_text
    assert "def admin_dashboard_select" in route_text
    assert "tutor_portal_admin_tutor_id" in route_text
    assert "_current_user_can_view_tutor_dashboard" in route_text
    assert '"tutor_portal.uploaded_file"' in route_text
    assert "Mode admin hanya untuk melihat dashboard tutor" in route_text
    assert "admin_credentials" in route_text
    assert "admin_send_credential_whatsapp" in route_text
    assert "admin_send_bulk_credential_whatsapp" in route_text
    assert "admin_reset_bulk_credential_passwords" in route_text
    assert "admin_reset_credential_password" in route_text
    assert "_reset_tutor_portal_password" in route_text
    assert "_selected_credential_tutors" in route_text
    assert "\"/messages/send\"" in route_text
    assert "Cara login pertama" in route_text
    assert "Fungsi dashboard tutor" in route_text
    assert "_normalize_whatsapp_phone" in route_text
    assert "https://tutor.supersmart.click" in route_text
    assert "request.form.get(\"message_template\")" in route_text
    assert "def _render_tutor_credential_whatsapp_message" in route_text
    assert '"https://tutor.supersmart.click"' in config_text
    assert "Approval Dashboard Tutor" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_requests.html"
    ).read_text(encoding="utf-8")
    assert "Credential Tutor" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Kirim WA" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Kirim WA Terpilih" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Reset Password Terpilih" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "credential-select-all" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "active_filter='inactive'" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Template Pesan WhatsApp" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "whatsapp_message_template" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "formaction" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Aktivasi Akun Tutor" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "onboarding.html"
    ).read_text(encoding="utf-8")
    assert "Password Baru" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "onboarding.html"
    ).read_text(encoding="utf-8")
    assert "Simpan Password, Gmail, dan Kirim Verifikasi" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "onboarding.html"
    ).read_text(encoding="utf-8")
    assert "Kirim Link Login" not in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "login.html"
    ).read_text(encoding="utf-8")
    assert "Login Admin" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "login.html"
    ).read_text(encoding="utf-8")
    assert "tutor_portal.admin_dashboard_select" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "login.html"
    ).read_text(encoding="utf-8")
    assert "Presensi Tutor" in dashboard_text
    assert "Lihat Dashboard Tutor" in dashboard_text
    assert "admin_tutor_options" in dashboard_text
    assert "Mode admin: hanya melihat dashboard tutor" in dashboard_text
    assert "hanya yang sudah divalidasi admin" in dashboard_text
    assert "attendance_pagination" in dashboard_text
    assert "Menampilkan presensi" in dashboard_text
    assert "attendance_calendar.can_view_previous" in dashboard_text
    assert "Kalender Presensi" in dashboard_text
    assert "attendance_calendar.weeks" in dashboard_text
    assert "Bulan Sebelumnya" in dashboard_text
    assert "Jadwal sama dengan jadwal tutor di Dashboard Lembaga" in dashboard_text
    assert "Pilih Tutor" in base_text
    assert "Keluar Admin" in base_text
    assert "Mode Admin" in admin_select_text
    assert "Lihat Dashboard Tutor" in admin_select_text
    assert "Slip Gaji" in dashboard_text
    assert "Ajukan Jadwal Merah/Hijau" not in dashboard_text
    assert "master/_tutor_schedule_grid.html" in dashboard_text
    assert "Perubahan Jadwal" in dashboard_text
    assert "schedule-editor-table" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "schedule_change.html"
    ).read_text(encoding="utf-8")
    assert "scheduleCellModal" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "schedule_change.html"
    ).read_text(encoding="utf-8")
    assert "Waitinglist" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "schedule_change.html"
    ).read_text(encoding="utf-8")
    assert "Ada siswa di waitinglist" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "schedule_change.html"
    ).read_text(encoding="utf-8")
    assert "Pengajuan tetap bisa dikirim" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "schedule_change.html"
    ).read_text(encoding="utf-8")
    admin_requests_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_requests.html"
    ).read_text(encoding="utf-8")
    assert "tutor_portal.admin_request_detail" in admin_requests_text
    assert "payload_items(item.payload_json)" in admin_requests_text
    admin_request_detail_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_request_detail.html"
    ).read_text(encoding="utf-8")
    assert "approval-schedule-table" in admin_request_detail_text
    assert "schedule_rows" in admin_request_detail_text
    assert "payload_items" in admin_request_detail_text
    assert "setCell(currentOwner, 'available', 'Available')" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "schedule_change.html"
    ).read_text(encoding="utf-8")


def test_tutor_portal_docker_service_and_mail_config_exist():
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_path = PROJECT_ROOT / ".env.example"
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    entrypoint_text = (PROJECT_ROOT / "docker" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )

    assert "tutor_web:" in compose_text
    assert "${TUTOR_PORTAL_PORT:-6003}:5000" in compose_text
    assert "TUTOR_PORTAL_BASE_URL" in compose_text
    assert "TUTOR_PORTAL_BASE_URL: ${TUTOR_PORTAL_BASE_URL:-https://tutor.supersmart.click}" in compose_text
    assert "MAIL_SERVER" in compose_text
    if env_text:
        assert "TUTOR_PORTAL_PORT=6003" in env_text
        assert "tutor.supersmart.click" in env_text
        assert "MAIL_SERVER=smtp.gmail.com" in env_text
        assert "MAIL_USERNAME=lbbsupersmart@gmail.com" in env_text
        assert "MAIL_DEFAULT_SENDER=lbbsupersmart@gmail.com" in env_text
    assert "CREATE TABLE IF NOT EXISTS tutor_portal_requests" in entrypoint_text
    assert "profile_photo_path" in entrypoint_text
    assert "cv_file_path" in entrypoint_text
    assert "portal_username" in entrypoint_text
    assert "portal_password_hash" in entrypoint_text
    assert "portal_must_change_password" in entrypoint_text
    assert "portal_email_verified" in entrypoint_text
