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
    SubjectTutorAssignment,
    Tutor,
)
from app.routes.master import (
    _build_subject_tutor_summary,
    _scan_subject_tutors_from_attendance_and_enrollment,
)


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_subject_tutor_summary_uses_strict_attendance_match_and_manual_override():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Nasional")
        level = Level(name="SMP")
        subject_math = Subject(name="Matematika")
        subject_english = Subject(name="Bahasa Inggris")
        student = Student(student_code="STD-501", name="Ratih")
        tutor_dinda = Tutor(tutor_code="TTR-501", name="Dinda", is_active=True)
        tutor_listya = Tutor(tutor_code="TTR-502", name="Listya", is_active=True)
        db.session.add_all(
            [
                curriculum,
                level,
                subject_math,
                subject_english,
                student,
                tutor_dinda,
                tutor_listya,
            ]
        )
        db.session.flush()

        english_enrollment = Enrollment(
            student_id=student.id,
            subject_id=subject_english.id,
            tutor_id=tutor_dinda.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="7",
            meeting_quota_per_month=4,
            student_rate_per_meeting=150000,
            tutor_rate_per_meeting=80000,
            status="active",
            is_active=True,
            start_date=datetime(2026, 5, 1),
        )
        db.session.add(english_enrollment)
        db.session.flush()

        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=english_enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor_dinda.id,
                    subject_id=subject_math.id,
                    session_date=date(2026, 5, 10),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                    tutor_fee_amount=80000,
                ),
                AttendanceSession(
                    enrollment_id=english_enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor_dinda.id,
                    subject_id=subject_english.id,
                    session_date=date(2026, 5, 11),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                    tutor_fee_amount=80000,
                ),
                SubjectTutorAssignment(
                    subject_id=subject_math.id,
                    tutor_id=tutor_listya.id,
                    status="included",
                ),
            ]
        )
        db.session.commit()

        math_summary = _build_subject_tutor_summary(subject_math.id)
        english_summary = _build_subject_tutor_summary(subject_english.id)

        assert [item["tutor_name"] for item in math_summary] == ["Listya"]
        assert math_summary[0]["manual_override"] is True
        assert math_summary[0]["attendance_count"] == 0
        assert [item["tutor_name"] for item in english_summary] == ["Dinda"]
        assert english_summary[0]["attendance_count"] == 1
        assert english_summary[0]["active_enrollment_count"] == 1


def test_scan_subject_tutors_persists_tutors_from_active_enrollment():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Nasional")
        level = Level(name="SMP")
        subject_math = Subject(name="Matematika")
        student = Student(student_code="STD-601", name="Nadine")
        tutor = Tutor(tutor_code="TTR-601", name="Dinda", is_active=True)
        db.session.add_all([curriculum, level, subject_math, student, tutor])
        db.session.flush()

        db.session.add_all(
            [
                Enrollment(
                    student_id=student.id,
                    subject_id=subject_math.id,
                    tutor_id=tutor.id,
                    curriculum_id=curriculum.id,
                    level_id=level.id,
                    grade="7",
                    meeting_quota_per_month=4,
                    student_rate_per_meeting=150000,
                    tutor_rate_per_meeting=80000,
                    status="active",
                    is_active=True,
                    start_date=datetime(2026, 5, 1),
                ),
                SubjectTutorAssignment(
                    subject_id=subject_math.id,
                    tutor_id=tutor.id,
                    status="excluded",
                ),
            ]
        )
        db.session.commit()

        result = _scan_subject_tutors_from_attendance_and_enrollment(subject_math.id)
        db.session.commit()

        assignment = SubjectTutorAssignment.query.filter_by(
            subject_id=subject_math.id,
            tutor_id=tutor.id,
        ).one()
        summary = _build_subject_tutor_summary(subject_math.id)

        assert result == {"created": 0, "updated": 1, "found": 1}
        assert assignment.status == "included"
        assert assignment.notes == "Auto-scanned from attendance/enrollment."
        assert [item["tutor_name"] for item in summary] == ["Dinda"]
        assert summary[0]["manual_source_label"] == "Scan Presensi/Enrollment"


def test_subject_detail_route_builds_tutor_summary_and_renders_template():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert '@master_bp.route("/subjects/<string:subject_ref>", methods=["GET"])' in route_text
    assert "def subject_detail(subject_ref):" in route_text
    assert "subject = _get_subject_by_ref_or_404(subject_ref)" in route_text
    assert "tutor_summary = _build_subject_tutor_summary(subject.id)" in route_text
    assert "tutor_assignment_form = SubjectTutorAssignmentForm()" in route_text
    assert '"master/subject_detail.html"' in route_text
    assert "tutor_summary=tutor_summary" in route_text
    assert "tutor_assignment_form=tutor_assignment_form" in route_text
    assert '@master_bp.route("/subjects/<string:subject_ref>/tutors/add", methods=["POST"])' in route_text
    assert "def add_subject_tutor(subject_ref):" in route_text
    assert '@master_bp.route("/subjects/<string:subject_ref>/tutors/scan", methods=["POST"])' in route_text
    assert "def scan_subject_tutors(subject_ref):" in route_text
    assert "_scan_subject_tutors_from_attendance_and_enrollment(subject.id)" in route_text
    assert '@master_bp.route("/subjects/<string:subject_ref>/tutors/<string:tutor_ref>/remove", methods=["POST"])' in route_text
    assert "def remove_subject_tutor(subject_ref, tutor_ref):" in route_text


def test_subject_detail_template_and_subject_list_link_exist():
    project_root = Path(__file__).resolve().parents[1]
    detail_template = (
        project_root / "app" / "templates" / "master" / "subject_detail.html"
    ).read_text(encoding="utf-8")
    list_template = (
        project_root / "app" / "templates" / "master" / "subjects_list.html"
    ).read_text(encoding="utf-8")

    assert "{% block title %}{{ subject.name }}{% endblock %}" in detail_template
    assert "Tutor Pengajar" in detail_template
    assert "Scan Presensi/Enrollment" in detail_template
    assert "Tambah Tutor" in detail_template
    assert "Hapus" in detail_template
    assert "manual_override" in detail_template
    assert "Presensi yang benar-benar match" in detail_template
    assert "Enrollment aktif" in detail_template
    assert "Presensi" in detail_template
    assert "Enrollment Terkait" in detail_template
    assert "url_for('master.tutor_detail', tutor_ref=item.tutor_ref)" in detail_template
    assert "url_for('master.add_subject_tutor', subject_ref=subject.public_id)" in detail_template
    assert "url_for('master.scan_subject_tutors', subject_ref=subject.public_id)" in detail_template
    assert "url_for('master.remove_subject_tutor', subject_ref=subject.public_id, tutor_ref=item.tutor_ref)" in detail_template
    assert "url_for('enrollments.enrollment_detail', enrollment_ref=enrollment.public_id)" in detail_template
    assert "url_for('master.subject_detail', subject_ref=subject.public_id)" in list_template
