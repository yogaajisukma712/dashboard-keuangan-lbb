import os

from dotenv import load_dotenv

from app import create_app, db

# Load environment variables from .env file
load_dotenv()

# Create Flask application instance
app = create_app(os.getenv("FLASK_ENV", "development"))


@app.before_request
def before_request():
    """Before request hook"""
    pass


@app.after_request
def after_request(response):
    """After request hook"""
    return response


@app.cli.command()
def init_db():
    """Initialize the database (create all tables + apply extra DDL patches)."""
    db.create_all()
    _apply_schema_patches()
    print("Database initialized.")


def _apply_schema_patches():
    """
    Apply idempotent DDL patches for columns/tables added after initial deployment.
    Safe to run multiple times — uses IF NOT EXISTS / IF NOT EXISTS guards.
    """
    from sqlalchemy import text

    extra_ddl = [
        # student_invoices table (not managed by ORM)
        """
        CREATE TABLE IF NOT EXISTS student_invoices (
            id            SERIAL PRIMARY KEY,
            student_id    INTEGER NOT NULL REFERENCES students(id),
            enrollment_id INTEGER REFERENCES enrollments(id),
            service_month DATE    NOT NULL,
            amount        NUMERIC(12,2) DEFAULT 0,
            billing_type  VARCHAR(20)   DEFAULT 'prepaid',
            status        VARCHAR(20)   DEFAULT 'draft',
            notes         TEXT,
            created_by    INTEGER REFERENCES users(id),
            completed_payment_id INTEGER REFERENCES student_payments(id),
            created_at    TIMESTAMP DEFAULT NOW(),
            updated_at    TIMESTAMP DEFAULT NOW()
        )
        """,
        "ALTER TABLE student_invoices ADD COLUMN IF NOT EXISTS billing_type VARCHAR(20) DEFAULT 'prepaid'",
        "ALTER TABLE student_invoices ADD COLUMN IF NOT EXISTS completed_payment_id INTEGER REFERENCES student_payments(id)",
        "CREATE INDEX IF NOT EXISTS ix_student_invoices_student_id    ON student_invoices(student_id)",
        "CREATE INDEX IF NOT EXISTS ix_student_invoices_enrollment_id ON student_invoices(enrollment_id)",
        "CREATE TABLE IF NOT EXISTS student_invoice_lines (\n            id            SERIAL PRIMARY KEY,\n            invoice_id     INTEGER NOT NULL REFERENCES student_invoices(id) ON DELETE CASCADE,\n            enrollment_id  INTEGER NOT NULL REFERENCES enrollments(id),\n            service_month  DATE    NOT NULL,\n            billing_type   VARCHAR(20) DEFAULT 'prepaid',\n            meeting_count  INTEGER NOT NULL,\n            student_rate_per_meeting NUMERIC(12,2) DEFAULT 0,\n            tutor_rate_per_meeting   NUMERIC(12,2) DEFAULT 0,\n            nominal_amount           NUMERIC(12,2) DEFAULT 0,\n            tutor_payable_amount     NUMERIC(12,2) DEFAULT 0,\n            margin_amount            NUMERIC(12,2) DEFAULT 0,\n            quota_paid_before        INTEGER DEFAULT 0,\n            quota_used_before        INTEGER DEFAULT 0,\n            quota_remaining_before   INTEGER DEFAULT 0,\n            notes         TEXT,\n            created_at    TIMESTAMP DEFAULT NOW(),\n            updated_at    TIMESTAMP DEFAULT NOW()\n        )",
        "CREATE INDEX IF NOT EXISTS ix_student_invoice_lines_invoice_id    ON student_invoice_lines(invoice_id)",
        "CREATE INDEX IF NOT EXISTS ix_student_invoice_lines_enrollment_id ON student_invoice_lines(enrollment_id)",
        # Payroll proof columns
        "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS proof_image  VARCHAR(500)",
        "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS proof_notes  TEXT",
        # Student columns that may be missing in older schemas
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        # Enrollment columns
        "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS meeting_quota_per_month INTEGER DEFAULT 4",
        # StudentPayment verification columns
        "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS verified_by INTEGER REFERENCES users(id)",
        "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP",
        # PricingRule columns
        "ALTER TABLE pricing_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE pricing_rules ADD COLUMN IF NOT EXISTS default_meeting_quota INTEGER DEFAULT 4",
        # Tutor is_active
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS profile_photo_path VARCHAR(500)",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS cv_file_path VARCHAR(500)",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_username VARCHAR(80)",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_password_hash VARCHAR(255)",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_visible_password VARCHAR(255)",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_must_change_password BOOLEAN DEFAULT TRUE",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_email_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_email_verified_at TIMESTAMP",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tutors_portal_username ON tutors(portal_username) WHERE portal_username IS NOT NULL",
        """
        CREATE TABLE IF NOT EXISTS tutor_meet_links (
            id SERIAL PRIMARY KEY,
            enrollment_id INTEGER NOT NULL REFERENCES enrollments(id),
            tutor_id INTEGER NOT NULL REFERENCES tutors(id),
            student_id INTEGER NOT NULL REFERENCES students(id),
            subject_id INTEGER REFERENCES subjects(id),
            token VARCHAR(96) NOT NULL UNIQUE,
            room VARCHAR(255) NOT NULL,
            join_url TEXT NOT NULL,
            jitsi_url TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            max_joins INTEGER NOT NULL DEFAULT 1,
            source VARCHAR(40) DEFAULT 'tutor_portal',
            valid_from TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_tutor_meet_links_enrollment_id ON tutor_meet_links(enrollment_id)",
        "CREATE INDEX IF NOT EXISTS ix_tutor_meet_links_tutor_id ON tutor_meet_links(tutor_id)",
        "CREATE INDEX IF NOT EXISTS ix_tutor_meet_links_student_id ON tutor_meet_links(student_id)",
        "ALTER TABLE tutor_meet_links ADD COLUMN IF NOT EXISTS valid_from TIMESTAMP",
        "ALTER TABLE tutor_meet_links ALTER COLUMN join_url TYPE TEXT",
        "ALTER TABLE tutor_meet_links ALTER COLUMN jitsi_url TYPE TEXT",
        "CREATE INDEX IF NOT EXISTS ix_tutor_meet_links_status ON tutor_meet_links(status)",
    ]
    for stmt in extra_ddl:
        try:
            db.session.execute(text(stmt.strip()))
        except Exception as exc:
            print(f"[schema-patch] warning (skipping): {exc}")
            db.session.rollback()
    db.session.commit()
    print("[schema-patch] Extra DDL applied.")


@app.cli.command()
def drop_db():
    """Drop the database."""
    if input("Are you sure? (y/n) ").lower() == "y":
        db.drop_all()
        print("Database dropped.")


@app.cli.command()
def seed_db():
    """Seed the database with initial data."""
    from app.models import Curriculum, Level, Subject

    # Add default curriculums
    curriculums = [
        Curriculum(name="Nasional"),
        Curriculum(name="Internasional"),
        Curriculum(name="Cambridge"),
    ]

    # Add default levels
    levels = [
        Level(name="TK"),
        Level(name="SD"),
        Level(name="SMP"),
        Level(name="SMA"),
    ]

    # Add default subjects
    subjects = [
        Subject(name="Matematika"),
        Subject(name="Bahasa Indonesia"),
        Subject(name="Bahasa Inggris"),
        Subject(name="IPA"),
        Subject(name="IPS"),
    ]

    db.session.add_all(curriculums + levels + subjects)
    db.session.commit()
    print("Database seeded with initial data.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        _apply_schema_patches()
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=os.getenv("DEBUG", True),
    )
