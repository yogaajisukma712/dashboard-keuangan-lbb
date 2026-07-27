from datetime import date, datetime

from flask import Flask

from app import db
from app.models import AttendanceSession, WhatsAppEvaluation, WhatsAppGroup, WhatsAppMessage
from ops.restore.cleanup_whatsapp_fallback_duplicates import execute_plan


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_execute_plan_replaces_inconsistent_canonical_evaluation():
    app = _make_test_app()
    with app.app_context():
        db.create_all()
        group = WhatsAppGroup(
            whatsapp_group_id="120363000000000000@g.us",
            name="Student Group",
        )
        canonical_message = WhatsAppMessage(
            whatsapp_message_id="false_120363000000000000@g.us_ABCDEF",
            group=group,
            sent_at=datetime(2026, 5, 14, 12, 0),
            body="Unreadable rescan payload",
        )
        fallback_message = WhatsAppMessage(
            whatsapp_message_id="120363000000000000@g.us-1770000000",
            group=group,
            sent_at=datetime(2026, 5, 14, 12, 0),
            body="Valid evaluation report",
            filter_status="relevant",
        )
        canonical_attendance = AttendanceSession(
            enrollment_id=10,
            student_id=20,
            tutor_id=30,
            subject_id=40,
            session_date=date(2026, 5, 14),
            status="attended",
            student_present=True,
            tutor_present=True,
            tutor_fee_amount=40000,
        )
        fallback_attendance = AttendanceSession(
            enrollment_id=11,
            student_id=20,
            tutor_id=30,
            subject_id=41,
            session_date=date(2026, 5, 14),
            status="attended",
            student_present=True,
            tutor_present=True,
            tutor_fee_amount=40000,
        )
        canonical_evaluation = WhatsAppEvaluation(
            message=canonical_message,
            group=group,
            attendance_date=date(2026, 5, 14),
            attendance_session=canonical_attendance,
        )
        fallback_evaluation = WhatsAppEvaluation(
            message=fallback_message,
            group=group,
            attendance_date=date(2026, 5, 14),
            attendance_session=fallback_attendance,
        )
        db.session.add_all(
            [
                group,
                canonical_message,
                fallback_message,
                canonical_attendance,
                fallback_attendance,
                canonical_evaluation,
                fallback_evaluation,
            ]
        )
        db.session.commit()
        canonical_message_id = canonical_message.id
        fallback_message_id = fallback_message.id
        canonical_evaluation_id = canonical_evaluation.id
        fallback_evaluation_id = fallback_evaluation.id
        canonical_attendance_id = canonical_attendance.id
        fallback_attendance_id = fallback_attendance.id

        execute_plan(
            [
                {
                    "fallback": fallback_message,
                    "canonical": canonical_message,
                    "action": "replace-canonical-evaluation",
                    "attendance_to_delete": canonical_attendance,
                }
            ]
        )
        db.session.commit()

        canonical = db.session.get(WhatsAppMessage, canonical_message_id)
        assert canonical.body == "Valid evaluation report"
        assert canonical.evaluation.id == fallback_evaluation_id
        assert canonical.evaluation.attendance_session_id == fallback_attendance_id
        assert db.session.get(WhatsAppMessage, fallback_message_id) is None
        assert db.session.get(WhatsAppEvaluation, canonical_evaluation_id) is None
        assert db.session.get(AttendanceSession, canonical_attendance_id) is None
        assert db.session.get(AttendanceSession, fallback_attendance_id) is not None
