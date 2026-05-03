from datetime import date, datetime
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
)
from app.routes.attendance import _build_lesson_calendar


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _seed_calendar_data(target_date: date):
    curriculum = Curriculum(name="K13")
    level = Level(name="SMA")
    subject = Subject(name="Matematika")
    student = Student(student_code="STD-100", name="Nadine")
    student_second = Student(student_code="STD-101", name="Ratih")
    tutor = Tutor(tutor_code="TTR-100", name="Dinda", is_active=True)

    db.session.add_all([curriculum, level, subject, student, student_second, tutor])
    db.session.flush()

    first_enrollment = Enrollment(
        student_id=student.id,
        subject_id=subject.id,
        tutor_id=tutor.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="10 SMA",
        meeting_quota_per_month=4,
        student_rate_per_meeting=150000,
        tutor_rate_per_meeting=80000,
        status="active",
        is_active=True,
        start_date=datetime(target_date.year, target_date.month, 1),
        whatsapp_group_name="English Nadine",
    )
    second_enrollment = Enrollment(
        student_id=student_second.id,
        subject_id=subject.id,
        tutor_id=tutor.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="9 SMP",
        meeting_quota_per_month=4,
        student_rate_per_meeting=140000,
        tutor_rate_per_meeting=75000,
        status="active",
        is_active=True,
        start_date=datetime(target_date.year, target_date.month, 1),
    )
    db.session.add_all([first_enrollment, second_enrollment])
    db.session.flush()
    db.session.add_all(
        [
            AttendanceSession(
                enrollment_id=first_enrollment.id,
                student_id=first_enrollment.student_id,
                tutor_id=first_enrollment.tutor_id,
                subject_id=first_enrollment.subject_id,
                session_date=target_date,
                status="attended",
                student_present=True,
                tutor_present=True,
                tutor_fee_amount=80000,
            ),
            AttendanceSession(
                enrollment_id=second_enrollment.id,
                student_id=second_enrollment.student_id,
                tutor_id=second_enrollment.tutor_id,
                subject_id=second_enrollment.subject_id,
                session_date=target_date,
                status="scheduled",
                student_present=False,
                tutor_present=False,
                tutor_fee_amount=75000,
            ),
        ]
    )
    db.session.commit()


def test_build_lesson_calendar_uses_attendance_sessions_as_source():
    app = _make_test_app()
    target_date = date(2026, 4, 7)

    with app.app_context():
        db.create_all()
        _seed_calendar_data(target_date)

        calendar_data = _build_lesson_calendar(4, 2026)
        lesson_items = []
        for week in calendar_data["weeks"]:
            for day in week:
                if day["date"] == target_date:
                    lesson_items.extend(day["items"])

        assert calendar_data["month"] == 4
        assert calendar_data["year"] == 2026
        assert calendar_data["title"] == "April 2026"
        assert calendar_data["lesson_count"] == 2
        assert calendar_data["scheduled_day_count"] >= 1
        assert calendar_data["scheduled_enrollment_count"] == 2
        assert calendar_data["tutor_count"] == 1
        assert calendar_data["student_count"] == 2
        assert len(lesson_items) == 2
        assert lesson_items[0]["tutor_name"] == "Dinda"
        assert lesson_items[0]["student_name"] == "Nadine"
        assert lesson_items[0]["subject_name"] == "Matematika"
        assert lesson_items[0]["attendance_status"] == "attended"
        assert lesson_items[0]["schedule_label"] == "Sesi les"
        assert lesson_items[0]["location"] == ""
        assert lesson_items[0]["whatsapp_group_name"] == "English Nadine"
        assert lesson_items[1]["student_name"] == "Ratih"
        assert lesson_items[1]["attendance_status"] == "scheduled"


def test_calendar_route_and_sidebar_link_exist_in_source():
    project_root = Path(__file__).resolve().parents[1]
    attendance_routes = (project_root / "app" / "routes" / "attendance.py").read_text(
        encoding="utf-8"
    )
    sidebar_template = (project_root / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )
    calendar_template = (
        project_root / "app" / "templates" / "attendance" / "calendar.html"
    ).read_text(encoding="utf-8")

    assert '@attendance_bp.route("/calendar", methods=["GET"])' in attendance_routes
    assert 'def calendar_view():' in attendance_routes
    assert "_build_lesson_calendar" in attendance_routes
    assert "url_for('attendance.calendar_view')" in sidebar_template
    assert "Kalender Les" in sidebar_template
    assert "calendar_data.weeks" in calendar_template
    assert "Presensi Sesi Les" in calendar_template
    assert "Detail enrollment" in calendar_template
    assert "day['items']" in calendar_template
    assert "day.items" not in calendar_template
    assert 'name="tutor_ref"' in calendar_template
    assert "tutor.public_id" in calendar_template
    assert "selected_tutor_ref" in calendar_template
