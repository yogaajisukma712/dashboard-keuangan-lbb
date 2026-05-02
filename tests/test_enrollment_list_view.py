from pathlib import Path

from flask import Flask

from app import db
from app.models import Curriculum, Enrollment, Level, Student, Subject, Tutor
from app.routes.enrollments import _build_enrollment_list_query


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _seed_enrollments():
    curriculum = Curriculum(name="K13")
    level = Level(name="SMA")
    subject_math = Subject(name="Matematika")
    subject_english = Subject(name="Bahasa Inggris")
    student_nadine = Student(student_code="STD-001", name="Nadine")
    student_ratih = Student(student_code="STD-002", name="Ratih")
    tutor_dinda = Tutor(tutor_code="TTR-001", name="Dinda")
    tutor_yoga = Tutor(tutor_code="TTR-002", name="Yoga Aji")

    db.session.add_all(
        [
            curriculum,
            level,
            subject_math,
            subject_english,
            student_nadine,
            student_ratih,
            tutor_dinda,
            tutor_yoga,
        ]
    )
    db.session.flush()

    enrollments = [
        Enrollment(
            student_id=student_nadine.id,
            subject_id=subject_math.id,
            tutor_id=tutor_dinda.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            meeting_quota_per_month=4,
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
            whatsapp_group_id="nadine-math@g.us",
            whatsapp_group_name="Grup Nadine Matematika",
        ),
        Enrollment(
            student_id=student_ratih.id,
            subject_id=subject_english.id,
            tutor_id=tutor_yoga.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="9",
            meeting_quota_per_month=4,
            student_rate_per_meeting=140000,
            tutor_rate_per_meeting=75000,
            status="inactive",
            whatsapp_group_id="ratih-english@g.us",
            whatsapp_group_name="Grup Ratih English",
        ),
    ]
    db.session.add_all(enrollments)
    db.session.commit()
    return enrollments


def test_build_enrollment_list_query_filters_by_status_and_search_term():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        enrollments = _seed_enrollments()

        active_results = _build_enrollment_list_query("", "active").all()
        group_results = _build_enrollment_list_query("ratih-english@g.us", "").all()
        student_results = _build_enrollment_list_query("Nadine", "").all()

        assert [item.id for item in active_results] == [enrollments[0].id]
        assert [item.id for item in group_results] == [enrollments[1].id]
        assert [item.id for item in student_results] == [enrollments[0].id]


def test_build_enrollment_list_query_matches_tutor_subject_and_group_name():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        enrollments = _seed_enrollments()

        tutor_results = _build_enrollment_list_query("Dinda", "").all()
        subject_results = _build_enrollment_list_query("Bahasa Inggris", "").all()
        group_name_results = _build_enrollment_list_query("Grup Ratih English", "").all()

        assert [item.id for item in tutor_results] == [enrollments[0].id]
        assert [item.id for item in subject_results] == [enrollments[1].id]
        assert [item.id for item in group_name_results] == [enrollments[1].id]


def test_enrollment_list_template_contains_quick_search_guard():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "enrollments" / "list.html"
    ).read_text(encoding="utf-8")

    assert 'id="quickEnrollmentSearch"' in template_text
    assert 'id="enrollmentTableBody"' in template_text
    assert 'id="quickSearchEmptyRow"' in template_text
    assert 'querySelectorAll(".enrollment-row")' in template_text
    assert 'row.classList.toggle("d-none", !isMatch)' in template_text
