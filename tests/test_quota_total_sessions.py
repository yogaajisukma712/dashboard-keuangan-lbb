from datetime import date, datetime

from flask import Flask

from app import db
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    Level,
    Student,
    StudentPayment,
    StudentPaymentLine,
    Subject,
    Tutor,
)
from app.routes.payments import _sync_payment_lines_from_form
from app.routes.quota_invoice import _build_quota_summary, calc_quota


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_calc_quota_uses_total_purchased_and_total_attended_sessions():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Nasional")
        level = Level(name="SMA")
        subject = Subject(name="Bahasa Inggris")
        student = Student(student_code="STD-QT-001", name="Fajry")
        tutor = Tutor(tutor_code="TTR-QT-001", name="Dinda")
        db.session.add_all([curriculum, level, subject, student, tutor])
        db.session.flush()

        enrollment = Enrollment(
            student_id=student.id,
            subject_id=subject.id,
            tutor_id=tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade="10",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
            is_active=True,
        )
        db.session.add(enrollment)
        db.session.flush()

        feb_payment = StudentPayment(
            student_id=student.id,
            receipt_number="INV-QT-FEB",
            payment_method="cash",
            total_amount=200000,
            payment_date=datetime(2026, 2, 1),
            is_verified=True,
        )
        mar_payment = StudentPayment(
            student_id=student.id,
            receipt_number="INV-QT-MAR",
            payment_method="cash",
            total_amount=100000,
            payment_date=datetime(2026, 3, 1),
            is_verified=True,
        )
        db.session.add_all([feb_payment, mar_payment])
        db.session.flush()
        db.session.add_all(
            [
                StudentPaymentLine(
                    student_payment_id=feb_payment.id,
                    enrollment_id=enrollment.id,
                    service_month=date(2026, 2, 1),
                    meeting_count=4,
                    student_rate_per_meeting=50000,
                    tutor_rate_per_meeting=30000,
                    nominal_amount=200000,
                    tutor_payable_amount=120000,
                    margin_amount=80000,
                ),
                StudentPaymentLine(
                    student_payment_id=mar_payment.id,
                    enrollment_id=enrollment.id,
                    service_month=date(2026, 3, 1),
                    meeting_count=2,
                    student_rate_per_meeting=50000,
                    tutor_rate_per_meeting=30000,
                    nominal_amount=100000,
                    tutor_payable_amount=60000,
                    margin_amount=40000,
                ),
            ]
        )
        db.session.add_all(
            [
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 2, 10),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                    tutor_fee_amount=30000,
                ),
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 3, 10),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                    tutor_fee_amount=30000,
                ),
                AttendanceSession(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=date(2026, 4, 10),
                    status="attended",
                    student_present=True,
                    tutor_present=True,
                    tutor_fee_amount=30000,
                ),
            ]
        )
        db.session.commit()

        quota = calc_quota(enrollment.id, date(2026, 5, 1))

        assert quota == {"paid": 6, "used": 3, "remaining": 3}


def test_quota_summary_exposes_total_session_metrics():
    summary = _build_quota_summary(
        [
            {"paid": 6, "used": 3, "remaining": 3, "deficit": 0},
            {"paid": 2, "used": 4, "remaining": -2, "deficit": 2},
        ]
    )

    assert summary["total_paid_sessions"] == 8
    assert summary["total_used_sessions"] == 7
    assert summary["total_remaining_sessions"] == 1
    assert summary["total_debt_sessions"] == 2


def test_edit_payment_subject_refreshes_total_bought_sessions_source():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Nasional")
        level = Level(name="SMA")
        ipa = Subject(name="IPA")
        science = Subject(name="Science")
        student = Student(name="Dinda", grade="10")
        tutor = Tutor(name="Bu Rani")
        db.session.add_all([curriculum, level, ipa, science, student, tutor])
        db.session.flush()

        ipa_enrollment = Enrollment(
            student_id=student.id,
            tutor_id=tutor.id,
            subject_id=ipa.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
            is_active=True,
        )
        science_enrollment = Enrollment(
            student_id=student.id,
            tutor_id=tutor.id,
            subject_id=science.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            student_rate_per_meeting=60000,
            tutor_rate_per_meeting=35000,
            status="active",
            is_active=True,
        )
        payment = StudentPayment(
            student_id=student.id,
            receipt_number="INV-EDIT-MAPEL",
            payment_method="cash",
            total_amount=100000,
            payment_date=datetime(2026, 5, 1),
            is_verified=True,
        )
        db.session.add_all([ipa_enrollment, science_enrollment, payment])
        db.session.flush()
        db.session.add(
            StudentPaymentLine(
                student_payment_id=payment.id,
                enrollment_id=ipa_enrollment.id,
                service_month=date(2026, 5, 1),
                meeting_count=2,
                student_rate_per_meeting=50000,
                tutor_rate_per_meeting=30000,
                nominal_amount=100000,
                tutor_payable_amount=60000,
                margin_amount=40000,
            )
        )
        db.session.commit()

        assert calc_quota(ipa_enrollment.id, date(2026, 5, 1))["paid"] == 2
        assert calc_quota(science_enrollment.id, date(2026, 5, 1))["paid"] == 0

        with app.test_request_context(
            "/payments/edit",
            method="POST",
            data={
                "enrollment_id[]": [str(science_enrollment.id)],
                "meeting_count[]": ["3"],
            },
        ):
            _sync_payment_lines_from_form(payment)
            db.session.commit()

        assert calc_quota(ipa_enrollment.id, date(2026, 5, 1))["paid"] == 0
        assert calc_quota(science_enrollment.id, date(2026, 5, 1))["paid"] == 3
        assert float(payment.total_amount) == 180000
