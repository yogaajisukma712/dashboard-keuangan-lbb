from pathlib import Path

from flask import Flask

from app import db
from app.models import Curriculum, Enrollment, Level, Student, Subject, Tutor
from app.routes.payments import _sort_payment_enrollments


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_payment_form_template_uses_searchable_selects():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payments" / "form.html"
    ).read_text(encoding="utf-8")

    assert 'data-placeholder="Cari nama siswa..."' in template_text
    assert 'data-placeholder="Cari mapel atau tutor..."' in template_text
    assert "initDynamicSearchableSelect(select)" in template_text
    assert "window.LbbFilterUi.init" in template_text


def test_payment_enrollment_dropdown_sort_is_a_to_z():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        tutor_z = Tutor(tutor_code="TTR-991", name="Zaki", is_active=True)
        tutor_a = Tutor(tutor_code="TTR-992", name="Alya", is_active=True)
        subject_z = Subject(name="Zoologi", is_active=True)
        subject_a = Subject(name="Aljabar", is_active=True)
        student = Student(student_code="STD-991", name="Nadia", is_active=True)
        db.session.add_all([curriculum, level, tutor_z, tutor_a, subject_z, subject_a, student])
        db.session.flush()

        enrollment_z = Enrollment(
            student_id=student.id,
            subject_id=subject_z.id,
            tutor_id=tutor_z.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
        )
        enrollment_a = Enrollment(
            student_id=student.id,
            subject_id=subject_a.id,
            tutor_id=tutor_a.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
        )
        db.session.add_all([enrollment_z, enrollment_a])
        db.session.commit()

        sorted_labels = [
            f"{enrollment.subject.name} — {enrollment.tutor.name}"
            for enrollment in _sort_payment_enrollments([enrollment_z, enrollment_a])
        ]

    assert sorted_labels == ["Aljabar — Alya", "Zoologi — Zaki"]


def test_payments_route_sources_sort_students_and_api_enrollments():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "payments.py").read_text(
        encoding="utf-8"
    )

    assert "order_by(Student.name.asc())" in route_text
    assert "_sort_payment_enrollments(" in route_text
    assert '"label": _payment_enrollment_label(e)' in route_text
