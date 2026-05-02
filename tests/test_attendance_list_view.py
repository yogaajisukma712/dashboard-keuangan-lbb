from datetime import date
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
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppMessage,
)
from app.routes.attendance import (
    _build_attendance_list_query,
    _sync_linked_whatsapp_evaluations,
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


def _seed_attendance_sessions():
    curriculum = Curriculum(name="K13")
    level = Level(name="SMA")
    subject_math = Subject(name="Matematika")
    subject_english = Subject(name="Bahasa Inggris")
    student_nadine = Student(student_code="STD-301", name="Nadine")
    student_ratih = Student(student_code="STD-302", name="Ratih")
    tutor_dinda = Tutor(tutor_code="TTR-301", name="Dinda", is_active=True)
    tutor_listya = Tutor(tutor_code="TTR-302", name="Listya", is_active=True)
    db.session.add_all(
        [
            curriculum,
            level,
            subject_math,
            subject_english,
            student_nadine,
            student_ratih,
            tutor_dinda,
            tutor_listya,
        ]
    )
    db.session.flush()

    enrollment_math = Enrollment(
        student_id=student_nadine.id,
        subject_id=subject_math.id,
        tutor_id=tutor_dinda.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="10",
        student_rate_per_meeting=150000,
        tutor_rate_per_meeting=80000,
        status="active",
    )
    enrollment_english = Enrollment(
        student_id=student_ratih.id,
        subject_id=subject_english.id,
        tutor_id=tutor_listya.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="9",
        student_rate_per_meeting=140000,
        tutor_rate_per_meeting=75000,
        status="active",
    )
    db.session.add_all([enrollment_math, enrollment_english])
    db.session.flush()

    april_session = AttendanceSession(
        enrollment_id=enrollment_math.id,
        student_id=student_nadine.id,
        tutor_id=tutor_dinda.id,
        subject_id=subject_math.id,
        session_date=date(2026, 4, 10),
        status="attended",
        student_present=True,
        tutor_present=True,
        tutor_fee_amount=80000,
    )
    may_session = AttendanceSession(
        enrollment_id=enrollment_english.id,
        student_id=student_ratih.id,
        tutor_id=tutor_dinda.id,
        subject_id=subject_english.id,
        session_date=date(2026, 5, 10),
        status="scheduled",
        student_present=False,
        tutor_present=False,
        tutor_fee_amount=75000,
    )
    db.session.add_all([april_session, may_session])
    db.session.commit()
    return {
        "april_session": april_session,
        "may_session": may_session,
        "tutor_dinda": tutor_dinda,
        "tutor_listya": tutor_listya,
    }


def test_build_attendance_list_query_filters_by_month_year_and_tutor():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()

        may_results = _build_attendance_list_query(month=5, year=2026).all()
        april_results = _build_attendance_list_query(month=4, year=2026).all()
        tutor_results = _build_attendance_list_query(
            tutor_id=seeded["tutor_dinda"].id,
            month=5,
            year=2026,
        ).all()

        assert [item.id for item in may_results] == [seeded["may_session"].id]
        assert [item.id for item in april_results] == [seeded["april_session"].id]
        assert [item.id for item in tutor_results] == [seeded["may_session"].id]


def test_attendance_list_template_contains_whatsapp_scan_form_and_year_filter():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "attendance" / "list.html"
    ).read_text(encoding="utf-8")

    assert 'name="year"' in template_text
    assert 'id="scanWhatsappAttendanceForm"' in template_text
    assert "attendance.scan_whatsapp_attendance" in template_text
    assert "default_scan_year" in template_text
    assert "tutor pengganti mengajar" in template_text
    assert 'id="quickAttendanceSearch"' in template_text
    assert 'id="attendanceTableBody"' in template_text
    assert 'class="attendance-row"' in template_text
    assert 'data-attendance-search="' in template_text
    assert 'quickAttendanceSearchEmptyRow' in template_text
    assert 'Tidak ada sesi di halaman ini yang cocok dengan pencarian cepat.' in template_text
    assert 'quickAttendanceSearchInput.addEventListener("input"' in template_text


def test_attendance_form_template_contains_manual_tutor_selector():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "attendance" / "form.html"
    ).read_text(encoding="utf-8")

    assert "Tutor Pengajar" in template_text
    assert "attendance_tutor_map" in template_text
    assert "maybeSyncTutorFromEnrollment" in template_text
    assert "Tidak harus sama dengan tutor bawaan enrollment" in template_text


def test_sync_linked_whatsapp_evaluations_follows_manual_attendance_edit():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        group = WhatsAppGroup(whatsapp_group_id="group-ratih@g.us", name="English Ratih")
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-manual-edit-1",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor Pengganti",
            sent_at=seeded["may_session"].created_at,
            body="Evaluasi",
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Ratih",
            tutor_name="Tutor Pengganti",
            subject_name="Bahasa Inggris",
            attendance_date=seeded["may_session"].session_date,
            matched_student_id=seeded["may_session"].student_id,
            matched_tutor_id=seeded["tutor_listya"].id,
            matched_subject_id=seeded["may_session"].subject_id,
            matched_enrollment_id=seeded["may_session"].enrollment_id,
            attendance_session_id=seeded["may_session"].id,
            match_status="attendance-linked",
        )
        db.session.add_all([group, message, evaluation])
        db.session.flush()

        seeded["may_session"].tutor_id = seeded["tutor_dinda"].id
        _sync_linked_whatsapp_evaluations(seeded["may_session"])

        assert evaluation.matched_tutor_id == seeded["tutor_dinda"].id
        assert evaluation.matched_enrollment_id == seeded["may_session"].enrollment_id
        assert evaluation.matched_student_id == seeded["may_session"].student_id
        assert evaluation.attendance_session_id == seeded["may_session"].id
        assert "Presensi dikoreksi manual" in evaluation.notes
