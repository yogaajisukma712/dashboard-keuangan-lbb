from datetime import date

from flask import Flask

from app import db
from app.models import AttendanceSession, Curriculum, Enrollment, Level, Student, Subject, Tutor
from app.routes.quota_invoice import quota_invoice_bp
from app.routes.master import master_bp
from app.routes.dashboard import dashboard_bp
from app.routes.auth import auth_bp


def test_missing_invoice_list_filters_attendance_and_service_month():
    app = Flask(__name__, template_folder="../app/templates")
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        LOGIN_DISABLED=True,
    )
    db.init_app(app)
    app.register_blueprint(quota_invoice_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    @app.context_processor
    def _test_template_context():
        from types import SimpleNamespace
        from flask import request
        return {"current_user": SimpleNamespace(is_authenticated=False, get_id=lambda: "guest"),
                "request": request, "quota_alert_count": 0}

    with app.app_context():
        db.create_all()
        db.session.execute(db.text("""
            CREATE TABLE student_invoices (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                enrollment_id INTEGER,
                service_month DATE,
                amount NUMERIC,
                billing_type VARCHAR(20),
                status VARCHAR(20),
                notes TEXT,
                completed_payment_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        curriculum, level = Curriculum(name="Nasional"), Level(name="SMA")
        subject, tutor = Subject(name="Matematika"), Tutor(tutor_code="T-MISS", name="Tutor")
        missing = Student(student_code="S-MISS", name="Belum Invoice")
        invoiced = Student(student_code="S-HAS", name="Sudah Invoice")
        absent = Student(student_code="S-ABS", name="Tidak Hadir")
        db.session.add_all([curriculum, level, subject, tutor, missing, invoiced, absent])
        db.session.flush()
        enrollments = [
            Enrollment(student_id=s.id, subject_id=subject.id, tutor_id=tutor.id,
                       curriculum_id=curriculum.id, level_id=level.id, grade="10",
                       student_rate_per_meeting=50000, tutor_rate_per_meeting=30000,
                       status="active", is_active=True)
            for s in (missing, invoiced, absent)
        ]
        db.session.add_all(enrollments)
        db.session.flush()
        # 'missing' hadir 2x di September, 'invoiced' 1x; keduanya hadir September.
        db.session.add_all([
            AttendanceSession(student_id=missing.id, enrollment_id=enrollments[0].id,
                              subject_id=subject.id, tutor_id=tutor.id,
                              session_date=date(2026, 9, 12), status="attended",
                              student_present=True, tutor_present=True),
            AttendanceSession(student_id=missing.id, enrollment_id=enrollments[0].id,
                              subject_id=subject.id, tutor_id=tutor.id,
                              session_date=date(2026, 9, 19), status="attended",
                              student_present=True, tutor_present=True),
            AttendanceSession(student_id=invoiced.id, enrollment_id=enrollments[1].id,
                              subject_id=subject.id, tutor_id=tutor.id,
                              session_date=date(2026, 9, 12), status="attended",
                              student_present=True, tutor_present=True),
        ])
        # Invoice layanan September dibuat Oktober => service_month = 2026-10.
        # 'invoiced' sudah ditagih; 'missing' belum.
        db.session.execute(db.text("""
            INSERT INTO student_invoices (student_id, enrollment_id, service_month, status)
            VALUES (:student_id, :enrollment_id, :service_month, 'draft')
        """), {"student_id": invoiced.id, "enrollment_id": enrollments[1].id,
              "service_month": "2026-10-01"})
        db.session.commit()

        response = app.test_client().get("/quota/missing-invoices?month=9&year=2026")
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Belum Invoice" in body
        assert "S-MISS" in body
        assert "Matematika" in body
        # Jumlah pertemuan September milik 'missing' = 2.
        assert ">2<" in body
        assert "Sudah Invoice" not in body
        assert "Tidak Hadir" not in body

        # Kontrol balik: invoice bertanda service_month September (bukan bulan tagih)
        # TIDAK boleh dianggap sebagai sudah-ditagih untuk layanan September.
        db.session.execute(db.text("""
            INSERT INTO student_invoices (student_id, enrollment_id, service_month, status)
            VALUES (:student_id, :enrollment_id, :service_month, 'draft')
        """), {"student_id": missing.id, "enrollment_id": enrollments[0].id,
              "service_month": "2026-09-01"})
        db.session.commit()
        body2 = app.test_client().get("/quota/missing-invoices?month=9&year=2026").get_data(as_text=True)
        assert "S-MISS" in body2  # tetap muncul: invoice Sept bukan bulan tagih (Okt)

        db.session.remove()
        db.drop_all()
