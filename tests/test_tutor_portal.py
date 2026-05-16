from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask

from app import db
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    EnrollmentSchedule,
    Level,
    RecruitmentCandidate,
    Student,
    Subject,
    Tutor,
    TutorMeetLink,
    TutorPortalRequest,
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppMessage,
)
from app.services.tutor_schedule_backfill_service import TutorScheduleBackfillService
from app.routes.tutor_portal import (
    ATTENDANCE_TABLE_PER_PAGE,
    _ListPagination,
    _build_schedule_change_rows,
    _build_schedule_request_display_rows,
    _build_tutor_attendance_calendar,
    _build_tutor_presensi_schedule_grid,
    _coerce_meeting_start_time,
    _delete_tutor_credential,
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


def test_tutor_schedule_backfill_persists_unique_student_schedule_from_january_to_april():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_tutor_portal_attendance()

        result = TutorScheduleBackfillService.backfill_from_attendance()
        schedules = EnrollmentSchedule.query.join(Enrollment).filter(
            Enrollment.tutor_id == seeded["tutor"].id,
            EnrollmentSchedule.is_active.is_(True),
        ).all()

        assert result["created"] == 1
        assert len(schedules) == 1
        assert schedules[0].enrollment_id == seeded["april"].enrollment_id
        assert schedules[0].day_of_week == seeded["april"].session_date.weekday()
        assert schedules[0].start_time.hour == 17

        schedule_grid = _build_tutor_presensi_schedule_grid(seeded["tutor"].id)
        schedule_items = [
            item
            for row in schedule_grid["rows"]
            for cell in row["cells"]
            for item in cell["items"]
        ]
        assert schedule_grid["lesson_count"] == 1
        assert schedule_grid["has_schedule"] is True
        assert [item["enrollment_ref"] for item in schedule_items] == [
            seeded["april"].enrollment.public_id
        ]
        assert schedule_items[0]["weekday"] == seeded["april"].session_date.weekday()
        assert schedule_items[0]["source"] == "enrollment"


def test_tutor_schedule_backfill_uses_attended_sessions_without_whatsapp_review():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        tutor = Tutor(tutor_code="TTR-NOREVIEW", name="Crysant", is_active=True)
        student = Student(student_code="STD-NOREVIEW", name="Joshua")
        db.session.add_all([curriculum, level, subject, tutor, student])
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
        db.session.add(enrollment)
        db.session.flush()
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 4, 22),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                ),
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 4, 24),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                ),
            ]
        )
        db.session.commit()

        result = TutorScheduleBackfillService.backfill_from_attendance()
        schedules = (
            EnrollmentSchedule.query.filter_by(enrollment_id=enrollment.id)
            .order_by(EnrollmentSchedule.day_of_week.asc())
            .all()
        )

        assert result["created"] == 2
        assert [schedule.day_of_week for schedule in schedules] == [
            (date(2026, 4, 22).toordinal() - 1) % 7,
            (date(2026, 4, 24).toordinal() - 1) % 7,
        ]
        assert all(schedule.start_time.hour == 17 for schedule in schedules)


def test_tutor_schedule_backfill_uses_weekly_position_patterns():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        tutor = Tutor(tutor_code="TTR-MULTI", name="Crysant", is_active=True)
        student = Student(student_code="STD-MULTI", name="Joshua")
        db.session.add_all([curriculum, level, subject, tutor, student])
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
        db.session.add(enrollment)
        db.session.flush()
        session_dates = [
            date(2026, 1, 5),
            date(2026, 1, 7),
            date(2026, 1, 9),
            date(2026, 1, 12),
            date(2026, 1, 14),
            date(2026, 1, 17),
            date(2026, 1, 19),
            date(2026, 1, 21),
            date(2026, 1, 23),
            date(2026, 1, 26),
            date(2026, 1, 28),
            date(2026, 1, 30),
        ]
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=session_date,
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                )
                for session_date in session_dates
            ]
        )
        db.session.commit()

        result = TutorScheduleBackfillService.backfill_from_attendance()
        schedules = (
            EnrollmentSchedule.query.filter_by(enrollment_id=enrollment.id, is_active=True)
            .order_by(EnrollmentSchedule.day_of_week.asc())
            .all()
        )

        assert result["created"] == 3
        assert [(schedule.day_name, schedule.start_time.hour) for schedule in schedules] == [
            ("Senin", 17),
            ("Rabu", 17),
            ("Jumat", 17),
        ]


def test_tutor_schedule_backfill_deactivates_students_without_january_april_attendance():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        tutor = Tutor(tutor_code="TTR-STALE", name="Crysant", is_active=True)
        kept_student = Student(student_code="STD-KEPT", name="Joshua")
        stale_student = Student(student_code="STD-STALE", name="Selvino")
        outside_tutor = Tutor(tutor_code="TTR-NEW", name="Tutor Baru", is_active=True)
        outside_student = Student(student_code="STD-NEW", name="Siswa Baru")
        db.session.add_all(
            [
                curriculum,
                level,
                subject,
                tutor,
                kept_student,
                stale_student,
                outside_tutor,
                outside_student,
            ]
        )
        db.session.flush()
        kept_enrollment = Enrollment(
            student_id=kept_student.id,
            subject_id=subject.id,
            tutor_id=tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
        )
        stale_enrollment = Enrollment(
            student_id=stale_student.id,
            subject_id=subject.id,
            tutor_id=tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
        )
        outside_enrollment = Enrollment(
            student_id=outside_student.id,
            subject_id=subject.id,
            tutor_id=outside_tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
        )
        db.session.add_all([kept_enrollment, stale_enrollment, outside_enrollment])
        db.session.flush()
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=kept_enrollment.id,
                    student_id=kept_student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 4, 22),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                ),
                EnrollmentSchedule(
                    enrollment_id=stale_enrollment.id,
                    day_of_week=1,
                    day_name="Selasa",
                    start_time=datetime.strptime("17:00", "%H:%M").time(),
                    end_time=datetime.strptime("18:00", "%H:%M").time(),
                    is_active=True,
                ),
                EnrollmentSchedule(
                    enrollment_id=outside_enrollment.id,
                    day_of_week=2,
                    day_name="Rabu",
                    start_time=datetime.strptime("18:00", "%H:%M").time(),
                    end_time=datetime.strptime("19:00", "%H:%M").time(),
                    is_active=True,
                ),
            ]
        )
        db.session.commit()

        result = TutorScheduleBackfillService.backfill_from_attendance()

        assert result["created"] == 1
        assert result["deactivated_stale"] == 1
        assert (
            EnrollmentSchedule.query.filter_by(enrollment_id=stale_enrollment.id)
            .one()
            .is_active
            is False
        )
        assert (
            EnrollmentSchedule.query.filter_by(enrollment_id=outside_enrollment.id)
            .one()
            .is_active
            is True
        )
        assert (
            EnrollmentSchedule.query.filter_by(enrollment_id=kept_enrollment.id)
            .one()
            .is_active
            is True
        )


def test_tutor_schedule_backfill_deactivates_schedule_when_last_attendance_before_2026():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        tutor = Tutor(tutor_code="TTR-OLD", name="Tutor Lama", is_active=True)
        student = Student(student_code="STD-OLD", name="Siswa Lama")
        db.session.add_all([curriculum, level, subject, tutor, student])
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
        db.session.add(enrollment)
        db.session.flush()
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2025, 12, 20),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                ),
                EnrollmentSchedule(
                    enrollment_id=enrollment.id,
                    day_of_week=0,
                    day_name="Senin",
                    start_time=datetime.strptime("17:00", "%H:%M").time(),
                    end_time=datetime.strptime("18:00", "%H:%M").time(),
                    is_active=True,
                ),
            ]
        )
        db.session.commit()

        result = TutorScheduleBackfillService.backfill_from_attendance()
        schedule = EnrollmentSchedule.query.filter_by(enrollment_id=enrollment.id).one()

        assert result["deactivated_stale"] == 1
        assert schedule.is_active is False


def test_tutor_schedule_backfill_ignores_attendance_after_student_moves_to_other_tutor():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        old_tutor = Tutor(tutor_code="TTR-OLD-TUTOR", name="Crysant", is_active=True)
        new_tutor = Tutor(tutor_code="TTR-NEW-TUTOR", name="Rendi", is_active=True)
        student = Student(student_code="STD-MOVED", name="Rafael Auristo")
        db.session.add_all([curriculum, level, subject, old_tutor, new_tutor, student])
        db.session.flush()
        enrollment = Enrollment(
            student_id=student.id,
            subject_id=subject.id,
            tutor_id=old_tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
        )
        db.session.add(enrollment)
        db.session.flush()
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=old_tutor.id,
                    subject_id=subject.id,
                    session_date=date(2025, 12, 29),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                ),
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=new_tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 4, 21),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                ),
                EnrollmentSchedule(
                    enrollment_id=enrollment.id,
                    day_of_week=1,
                    day_name="Selasa",
                    start_time=datetime.strptime("18:00", "%H:%M").time(),
                    end_time=datetime.strptime("19:00", "%H:%M").time(),
                    is_active=True,
                ),
            ]
        )
        db.session.commit()

        result = TutorScheduleBackfillService.backfill_from_attendance()
        schedule = EnrollmentSchedule.query.filter_by(enrollment_id=enrollment.id).one()

        assert result["created"] == 0
        assert result["deactivated_stale"] == 1
        assert schedule.is_active is False


def test_tutor_portal_schedule_uses_persisted_enrollment_schedule():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_tutor_portal_attendance()
        schedule = EnrollmentSchedule(
            enrollment_id=seeded["april"].enrollment_id,
            day_of_week=2,
            day_name="Rabu",
            start_time=datetime.strptime("18:00", "%H:%M").time(),
            end_time=datetime.strptime("19:00", "%H:%M").time(),
            is_active=True,
        )
        db.session.add(schedule)
        db.session.commit()

        schedule_grid = _build_tutor_presensi_schedule_grid(seeded["tutor"].id)
        schedule_items = [
            item
            for row in schedule_grid["rows"]
            for cell in row["cells"]
            for item in cell["items"]
        ]

        assert schedule_grid["has_schedule"] is True
        assert schedule_grid["source_type"] == "enrollment_schedule"
        assert schedule_items[0]["weekday"] == 2
        assert schedule_items[0]["hour"] == 18


def test_tutor_portal_schedule_falls_back_to_recruitment_availability_for_new_tutor():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        tutor = Tutor(tutor_code="TTR-NEW-RECRUIT", name="Tutor Baru", is_active=True)
        candidate = RecruitmentCandidate(
            google_email="new.tutor@gmail.com",
            email_verified=True,
            name="Tutor Baru",
            status="signed",
            tutor=tutor,
        )
        candidate.availability_slots = [
            {
                "weekday": 0,
                "day_name": "Senin",
                "hour": 16,
                "start_time": "16:00",
                "end_time": "17:00",
                "state": "available",
            },
            {
                "weekday": 1,
                "day_name": "Selasa",
                "hour": 16,
                "start_time": "16:00",
                "end_time": "17:00",
                "state": "unavailable",
            },
        ]
        db.session.add_all([tutor, candidate])
        db.session.commit()

        schedule_grid = _build_tutor_presensi_schedule_grid(tutor.id)
        monday_16 = schedule_grid["rows"][8]["cells"][0]
        tuesday_16 = schedule_grid["rows"][8]["cells"][1]

        assert schedule_grid["has_schedule"] is True
        assert schedule_grid["lesson_count"] == 0
        assert schedule_grid["source_type"] == "candidate_availability"
        assert monday_16["availability"] == "available"
        assert tuesday_16["availability"] == "unavailable"


def test_delete_tutor_credential_removes_tutor_and_dependent_records():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.execute(
            db.text(
                """
                CREATE TABLE student_invoices (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    enrollment_id INTEGER NOT NULL,
                    service_month DATE,
                    amount NUMERIC,
                    billing_type VARCHAR(20),
                    status VARCHAR(20),
                    notes TEXT,
                    completed_payment_id INTEGER,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        db.session.execute(
            db.text(
                """
                CREATE TABLE student_invoice_lines (
                    id INTEGER PRIMARY KEY,
                    invoice_id INTEGER NOT NULL,
                    enrollment_id INTEGER NOT NULL,
                    service_month DATE,
                    billing_type VARCHAR(20),
                    meeting_count INTEGER,
                    student_rate_per_meeting NUMERIC,
                    tutor_rate_per_meeting NUMERIC,
                    nominal_amount NUMERIC,
                    tutor_payable_amount NUMERIC,
                    margin_amount NUMERIC
                )
                """
            )
        )
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        tutor = Tutor(
            tutor_code="TTR-DELETE-LINK",
            name="Tutor Delete",
            email="delete.tutor@example.com",
            is_active=True,
        )
        other_tutor = Tutor(tutor_code="TTR-SESSION-OTHER", name="Tutor Session")
        student = Student(student_code="STD-DELETE-LINK", name="Siswa Delete")
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
        db.session.add(enrollment)
        db.session.flush()

        meet_link = TutorMeetLink(
            enrollment_id=enrollment.id,
            tutor_id=tutor.id,
            student_id=student.id,
            subject_id=subject.id,
            token="delete-link-token",
            room="ss-meet-delete-link",
            join_url="https://meet.example/delete-link",
            status="active",
        )
        attendance_session = AttendanceSession(
            enrollment_id=enrollment.id,
            student_id=student.id,
            tutor_id=tutor.id,
            subject_id=subject.id,
            session_date=date(2026, 5, 16),
            status="attended",
            student_present=True,
            tutor_present=True,
            tutor_fee_amount=80000,
        )
        moved_attendance_session = AttendanceSession(
            enrollment_id=enrollment.id,
            student_id=student.id,
            tutor_id=other_tutor.id,
            subject_id=subject.id,
            session_date=date(2026, 5, 17),
            status="attended",
            student_present=True,
            tutor_present=True,
            tutor_fee_amount=80000,
        )
        request = TutorPortalRequest(
            tutor_id=tutor.id,
            request_type="schedule_change",
            status="pending",
            payload_json={},
        )
        group = WhatsAppGroup(whatsapp_group_id="group-delete-link", name="Kelas Hapus")
        db.session.add_all(
            [meet_link, attendance_session, moved_attendance_session, request, group]
        )
        db.session.flush()
        message = WhatsAppMessage(
            whatsapp_message_id="delete-link-message",
            group_id=group.id,
            sent_at=datetime(2026, 5, 16, 8, 0),
            body="Presensi",
        )
        db.session.add(message)
        db.session.flush()
        evaluation = WhatsAppEvaluation(
            message_id=message.id,
            group_id=group.id,
            attendance_date=attendance_session.session_date,
            matched_tutor_id=tutor.id,
            matched_enrollment_id=enrollment.id,
            attendance_session_id=attendance_session.id,
            manual_review_status="valid",
        )
        db.session.add(evaluation)
        linked_candidate = RecruitmentCandidate(
            google_email="linked.candidate@example.com",
            tutor_id=tutor.id,
            status="contract_sent",
        )
        email_candidate = RecruitmentCandidate(
            google_email="DELETE.TUTOR@example.com",
            status="contract_sent",
        )
        unrelated_candidate = RecruitmentCandidate(
            google_email="unrelated@example.com",
            status="contract_sent",
        )
        db.session.add_all([linked_candidate, email_candidate, unrelated_candidate])
        db.session.execute(
            db.text(
                """
                INSERT INTO student_invoices
                    (id, student_id, enrollment_id, service_month, amount, status)
                VALUES
                    (1, :student_id, :enrollment_id, '2026-05-01', 150000, 'draft')
                """
            ),
            {"student_id": student.id, "enrollment_id": enrollment.id},
        )
        db.session.execute(
            db.text(
                """
                INSERT INTO student_invoice_lines
                    (id, invoice_id, enrollment_id, service_month, meeting_count,
                     nominal_amount)
                VALUES
                    (1, 1, :enrollment_id, '2026-05-01', 1, 150000)
                """
            ),
            {"enrollment_id": enrollment.id},
        )
        db.session.commit()

        tutor_id = tutor.id
        meet_link_id = meet_link.id
        request_id = request.id
        evaluation_id = evaluation.id
        enrollment_id = enrollment.id
        attendance_session_id = attendance_session.id
        moved_attendance_session_id = moved_attendance_session.id
        linked_candidate_id = linked_candidate.id
        email_candidate_id = email_candidate.id
        unrelated_candidate_id = unrelated_candidate.id

        _delete_tutor_credential(tutor)

        invoice_count = db.session.execute(
            db.text("SELECT COUNT(*) FROM student_invoices")
        ).scalar()
        invoice_line_count = db.session.execute(
            db.text("SELECT COUNT(*) FROM student_invoice_lines")
        ).scalar()
        assert db.session.get(Tutor, tutor_id) is None
        assert db.session.get(TutorMeetLink, meet_link_id) is None
        assert db.session.get(TutorPortalRequest, request_id) is None
        assert db.session.get(Enrollment, enrollment_id) is None
        assert db.session.get(AttendanceSession, attendance_session_id) is None
        assert db.session.get(AttendanceSession, moved_attendance_session_id) is None
        assert db.session.get(WhatsAppEvaluation, evaluation_id) is None
        assert db.session.get(RecruitmentCandidate, linked_candidate_id) is None
        assert db.session.get(RecruitmentCandidate, email_candidate_id) is None
        assert db.session.get(RecruitmentCandidate, unrelated_candidate_id) is not None
        assert invoice_count == 0
        assert invoice_line_count == 0


def test_meet_link_time_options_are_24_hour_15_minute_slots():
    assert _coerce_meeting_start_time("07:00", 19).strftime("%H:%M") == "07:00"
    assert _coerce_meeting_start_time("18:45", 19).strftime("%H:%M") == "18:45"
    assert _coerce_meeting_start_time("21:00", 19).strftime("%H:%M") == "21:00"
    assert _coerce_meeting_start_time("", 18).strftime("%H:%M") == "18:00"

    invalid_values = ["06:45", "07:10", "21:15", "09:00 AM", "22:00"]
    for value in invalid_values:
        try:
            _coerce_meeting_start_time(value, 19)
        except ValueError:
            continue
        raise AssertionError(f"{value} should be rejected")


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
    assert "self.portal_visible_password = password" in model_text
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
    assert '@tutor_portal_bp.route("/google/login", methods=["GET"])' in route_text
    assert '@tutor_portal_bp.route("/google/callback", methods=["GET"])' in route_text
    assert "def _fetch_google_userinfo" in route_text
    assert "tutor.portal_must_change_password" in route_text
    assert "Login Google aktif setelah tutor mengganti password awal" in route_text
    assert "session[\"tutor_portal_tutor_id\"] = tutor.id" in route_text
    assert "def _clear_portal_sessions" in route_text
    assert "recruitment_candidate_id" in route_text
    assert "def _default_meeting_hour_for_enrollment" in route_text
    assert "_default_meeting_hour_for_enrollment(enrollment.id)" in route_text
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
    assert "TutorScheduleBackfillService" in (
        PROJECT_ROOT / "app" / "services" / "tutor_schedule_backfill_service.py"
    ).read_text(encoding="utf-8")
    assert "has_schedule" in (
        PROJECT_ROOT / "app" / "routes" / "master.py"
    ).read_text(encoding="utf-8")
    assert "TutorMeetLink.query.filter" in (
        PROJECT_ROOT / "app" / "routes" / "master.py"
    ).read_text(encoding="utf-8")
    assert '"meet_link": meet_links.get(enrollment.id)' in (
        PROJECT_ROOT / "app" / "routes" / "master.py"
    ).read_text(encoding="utf-8")
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
    assert '@tutor_portal_bp.route("/payouts/<string:payout_ref>", methods=["GET"])' in route_text
    assert "def payout_detail" in route_text
    assert "_build_fee_slip_template_context" in route_text
    assert '"payroll/fee_slip.html"' in route_text
    assert "tutor_portal_mode=True" in route_text
    assert 'proof_endpoint="tutor_portal.uploaded_file"' in route_text
    assert "payout.tutor_id != tutor.id" in route_text
    assert '"tutor_portal.uploaded_file"' in route_text
    assert '"tutor_portal.payout_detail"' in route_text
    assert "Mode admin hanya untuk melihat dashboard tutor" in route_text
    assert "admin_credentials" in route_text
    assert "admin_send_credential_whatsapp" in route_text
    assert "admin_send_bulk_credential_whatsapp" in route_text
    assert "admin_reset_bulk_credential_passwords" in route_text
    assert "admin_reset_credential_password" in route_text
    assert "admin_delete_credential_tutor" in route_text
    assert '"/admin/credentials/<string:tutor_ref>/delete"' in route_text
    assert "_reset_tutor_portal_password" in route_text
    assert "_next_bypass_tutor_code" in route_text
    assert "Bypass tutor baru" in route_text
    assert "default_password" in route_text
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
    assert "Bypass Tutor Baru" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Password Default" in (
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
    assert "Hapus Permanen" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Data terkait tutor seperti enrollment, presensi, invoice, payroll, dan SS Meet juga akan terhapus." in (
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
    assert "row.visible_password" in (
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
    assert "Login dengan Google" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "login.html"
    ).read_text(encoding="utf-8")
    assert "tutor_portal.google_login" in (
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
    assert "tutor_portal.payout_detail" in dashboard_text
    fee_slip_text = (
        PROJECT_ROOT / "app" / "templates" / "payroll" / "fee_slip.html"
    ).read_text(encoding="utf-8")
    assert (
        '{% extends "tutor_portal/base.html" if tutor_portal_mode|default(false) else "base.html" %}'
        in fee_slip_text
    )
    assert "tutor_portal_mode" in fee_slip_text
    assert "Dashboard Tutor" in fee_slip_text
    assert "{% block scripts %}{% endblock %}" in base_text
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
    assert "GOOGLE_OAUTH_CLIENT_ID: ${GOOGLE_OAUTH_CLIENT_ID:-}" in compose_text
    assert "GOOGLE_OAUTH_CLIENT_SECRET: ${GOOGLE_OAUTH_CLIENT_SECRET:-}" in compose_text
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
