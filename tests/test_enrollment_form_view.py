from decimal import Decimal
from datetime import date, datetime
from pathlib import Path

from flask import Flask
from sqlalchemy import text

from app import db
from app import register_template_filters
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    Level,
    Student,
    Subject,
    Tutor,
    TutorMeetLink,
    WhatsAppContact,
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppMessage,
    WhatsAppTutorValidation,
)
from app.routes.enrollments import (
    _apply_selected_whatsapp_group,
    _build_enrollment_list_query,
    _delete_enrollment_dependencies,
    _normalize_rate_form_value,
    _scan_missing_enrollment_whatsapp_groups,
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


def test_normalize_rate_form_value_removes_trailing_decimal_places():
    assert _normalize_rate_form_value(Decimal("43750.00")) == 43750
    assert _normalize_rate_form_value(Decimal("30000.00")) == 30000
    assert _normalize_rate_form_value(None) is None


def test_enrollment_form_template_uses_whole_number_steps_for_rate_fields():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "enrollments.py").read_text(
        encoding="utf-8"
    )
    template_text = (
        project_root / "app" / "templates" / "enrollments" / "form.html"
    ).read_text(encoding="utf-8")
    list_template_text = (
        project_root / "app" / "templates" / "enrollments" / "list.html"
    ).read_text(encoding="utf-8")

    assert "_normalize_rate_form_value(" in route_text
    assert 'form.student_rate_per_meeting(class_="form-control"' in template_text
    assert 'form.tutor_rate_per_meeting(class_="form-control"' in template_text
    assert "step=1" in template_text
    assert "form.whatsapp_group_db_id" in template_text
    assert "Pilih Group WA dari Bot" in template_text
    assert 'id="whatsappGroupSearch"' in template_text
    assert "filterWhatsappGroups" in template_text
    assert "whatsappGroupSearchHint" in template_text
    assert "WhatsAppGroup" in route_text
    assert "scan_missing_whatsapp_groups" in route_text
    assert "Scan Group WA Kosong" in list_template_text
    assert 'name="sort"' in list_template_text
    assert "Presensi terakhir terbaru" in list_template_text
    assert 'default_sort = \'last_attendance_desc\'' in list_template_text
    assert 'name="per_page"' in list_template_text
    assert "page=enrollments.page" in list_template_text
    assert "last_attendance_desc" in route_text
    assert 'DEFAULT_ENROLLMENT_SORT = "last_attendance_desc"' in route_text
    assert "ENROLLMENT_LIST_STATE_KEY" in route_text
    assert "flask_session[ENROLLMENT_LIST_STATE_KEY]" in route_text


def test_build_enrollment_list_query_sorts_by_last_attendance_date():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        student = Student(student_code="STD-901", name="Ratih", is_active=True)
        tutor = Tutor(tutor_code="TTR-901", name="Dinda", is_active=True)
        older_enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="10",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        newer_enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="11",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        no_attendance_enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="12",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        db.session.add_all(
            [
                curriculum,
                level,
                subject,
                student,
                tutor,
                older_enrollment,
                newer_enrollment,
                no_attendance_enrollment,
            ]
        )
        db.session.flush()
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=older_enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 4, 1),
                    status="attended",
                ),
                AttendanceSession(
                    enrollment_id=newer_enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 5, 1),
                    status="attended",
                ),
            ]
        )
        db.session.commit()

        desc_results = _build_enrollment_list_query(
            sort_by="last_attendance_desc"
        ).all()
        asc_results = _build_enrollment_list_query(
            sort_by="last_attendance_asc"
        ).all()

        assert [item.id for item in desc_results] == [
            newer_enrollment.id,
            older_enrollment.id,
            no_attendance_enrollment.id,
        ]
        assert [item.id for item in asc_results] == [
            older_enrollment.id,
            newer_enrollment.id,
            no_attendance_enrollment.id,
        ]


def test_apply_selected_whatsapp_group_updates_enrollment_snapshot():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        group = WhatsAppGroup(
            whatsapp_group_id="group-ratih@g.us",
            name="English Ratih",
        )
        enrollment = Enrollment(
            student_id=1,
            subject_id=1,
            tutor_id=1,
            curriculum_id=1,
            level_id=1,
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        db.session.add_all([group, enrollment])
        db.session.flush()

        _apply_selected_whatsapp_group(enrollment, group.id)

        assert enrollment.whatsapp_group_id == "group-ratih@g.us"
        assert enrollment.whatsapp_group_name == "English Ratih"
        assert enrollment.whatsapp_group_memberships_json == [
            {
                "group_id": group.id,
                "whatsapp_group_id": "group-ratih@g.us",
                "group_name": "English Ratih",
            }
        ]


def test_scan_missing_enrollment_whatsapp_groups_fills_only_empty_enrollments():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        student = Student(
            student_code="STD-900",
            name="Ratih",
            is_active=True,
            whatsapp_group_memberships_json=[
                {
                    "group_id": 9,
                    "whatsapp_group_id": "group-ratih@g.us",
                    "group_name": "English Ratih",
                }
            ],
        )
        tutor = Tutor(tutor_code="TTR-900", name="Dinda", is_active=True)
        contact = WhatsAppContact(
            whatsapp_contact_id="6281234567890@c.us",
            phone_number="6281234567890",
            display_name="Dinda",
            is_group=False,
        )
        empty_enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="10",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        existing_enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="11",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
            whatsapp_group_id="existing@g.us",
            whatsapp_group_name="Existing Group",
            whatsapp_group_memberships_json=[
                {
                    "whatsapp_group_id": "existing@g.us",
                    "group_name": "Existing Group",
                }
            ],
        )
        db.session.add_all(
            [
                curriculum,
                level,
                subject,
                student,
                tutor,
                contact,
                empty_enrollment,
                existing_enrollment,
            ]
        )
        db.session.flush()
        db.session.add(
            WhatsAppTutorValidation(
                contact_id=contact.id,
                tutor_id=tutor.id,
                validated_phone_number="6281234567890",
                group_memberships_json=[
                    {
                        "group_id": 9,
                        "whatsapp_group_id": "group-ratih@g.us",
                        "group_name": "English Ratih",
                    }
                ],
            )
        )
        db.session.commit()

        summary = _scan_missing_enrollment_whatsapp_groups()

        assert summary == {"processed": 1, "matched": 1, "unmatched": 0}
        assert empty_enrollment.whatsapp_group_id == "group-ratih@g.us"
        assert empty_enrollment.whatsapp_group_name == "English Ratih"
        assert existing_enrollment.whatsapp_group_id == "existing@g.us"


def test_delete_enrollment_dependencies_removes_external_blockers():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.execute(
            text(
                """
                CREATE TABLE student_invoices (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    enrollment_id INTEGER REFERENCES enrollments(id)
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TABLE student_invoice_lines (
                    id INTEGER PRIMARY KEY,
                    invoice_id INTEGER NOT NULL REFERENCES student_invoices(id),
                    enrollment_id INTEGER NOT NULL REFERENCES enrollments(id),
                    service_month DATE NOT NULL,
                    meeting_count INTEGER NOT NULL,
                    nominal_amount NUMERIC DEFAULT 0
                )
                """
            )
        )

        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Matematika")
        student = Student(student_code="STD-902", name="Salsa", is_active=True)
        tutor = Tutor(tutor_code="TTR-902", name="Dinda", is_active=True)
        enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="10",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        db.session.add_all([curriculum, level, subject, student, tutor, enrollment])
        db.session.flush()

        attendance_session = AttendanceSession(
            enrollment_id=enrollment.id,
            student_id=student.id,
            tutor_id=tutor.id,
            subject_id=subject.id,
            session_date=date(2026, 5, 18),
            status="attended",
        )
        meet_link = TutorMeetLink(
            enrollment_id=enrollment.id,
            tutor_id=tutor.id,
            student_id=student.id,
            subject_id=subject.id,
            token="enrollment-delete-link-token",
            room="ss-meet-enrollment-delete",
            join_url="https://meet.example/enrollment-delete",
            status="active",
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-enrollment-delete@g.us",
            name="Kelas Delete Enrollment",
        )
        db.session.add_all([attendance_session, meet_link, group])
        db.session.flush()
        message = WhatsAppMessage(
            whatsapp_message_id="msg-enrollment-delete",
            group_id=group.id,
            sent_at=datetime(2026, 5, 18, 8, 0),
            body="Presensi",
        )
        db.session.add(message)
        db.session.flush()
        evaluation = WhatsAppEvaluation(
            message_id=message.id,
            group_id=group.id,
            attendance_date=attendance_session.session_date,
            matched_enrollment_id=enrollment.id,
            attendance_session_id=attendance_session.id,
        )
        db.session.add(evaluation)
        db.session.execute(
            text(
                """
                INSERT INTO student_invoices (id, student_id, enrollment_id)
                VALUES (1, :student_id, :enrollment_id)
                """
            ),
            {"student_id": student.id, "enrollment_id": enrollment.id},
        )
        db.session.execute(
            text(
                """
                INSERT INTO student_invoice_lines
                    (id, invoice_id, enrollment_id, service_month, meeting_count, nominal_amount)
                VALUES (1, 1, :enrollment_id, '2026-05-01', 1, 50000)
                """
            ),
            {"enrollment_id": enrollment.id},
        )
        db.session.commit()

        enrollment_id = enrollment.id
        meet_link_id = meet_link.id
        evaluation_id = evaluation.id

        _delete_enrollment_dependencies(enrollment)
        db.session.delete(enrollment)
        db.session.commit()

        invoice_count = db.session.execute(text("SELECT COUNT(*) FROM student_invoices")).scalar()
        invoice_line_count = db.session.execute(
            text("SELECT COUNT(*) FROM student_invoice_lines")
        ).scalar()
        evaluation_count = db.session.execute(
            text("SELECT COUNT(*) FROM whatsapp_evaluations WHERE id = :id"),
            {"id": evaluation_id},
        ).scalar()
        assert db.session.get(Enrollment, enrollment_id) is None
        assert db.session.get(TutorMeetLink, meet_link_id) is None
        assert evaluation_count == 0
        assert invoice_count == 0
        assert invoice_line_count == 0


def test_enrollment_detail_notes_filter_is_registered_and_escapes_html():
    app = Flask(__name__)
    register_template_filters(app)

    rendered = app.jinja_env.filters["nl2br"]("<b>Baris 1</b>\nBaris 2")

    assert "nl2br" in app.jinja_env.filters
    assert "&lt;b&gt;Baris 1&lt;/b&gt;<br>Baris 2" == str(rendered)
