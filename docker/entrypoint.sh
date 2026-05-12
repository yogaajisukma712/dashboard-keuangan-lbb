#!/bin/sh
set -e

echo "Starting Dashboard Keuangan LBB Super Smart – billing.supersmart.click"

# ── Defaults ────────────────────────────────────────────────────────────────
: "${FLASK_ENV:=production}"
: "${PORT:=5000}"
: "${GUNICORN_WORKERS:=4}"

export FLASK_ENV PORT GUNICORN_WORKERS

# ── Wait for DB + init schema ────────────────────────────────────────────────
if [ -n "$DATABASE_URL" ]; then
  echo "[entrypoint] Waiting for database..."
  python docker/wait_for_db.py

  echo "[entrypoint] Initialising base schema (db.create_all)..."
  python - <<'PYEOF'
from run import app
from app import db
with app.app_context():
    db.create_all()
    print("[entrypoint] Base schema ready.")
PYEOF

  echo "[entrypoint] Applying extra DDL (schema patches for all versions)..."
  python - <<'PYEOF'
from run import app
from app import db
EXTRA_DDL = [
    # student_invoices — raw SQL table, not managed by ORM
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
    "CREATE TABLE IF NOT EXISTS student_invoice_lines (\n        id            SERIAL PRIMARY KEY,\n        invoice_id     INTEGER NOT NULL REFERENCES student_invoices(id) ON DELETE CASCADE,\n        enrollment_id  INTEGER NOT NULL REFERENCES enrollments(id),\n        service_month  DATE    NOT NULL,\n        billing_type   VARCHAR(20) DEFAULT 'prepaid',\n        meeting_count  INTEGER NOT NULL,\n        student_rate_per_meeting NUMERIC(12,2) DEFAULT 0,\n        tutor_rate_per_meeting   NUMERIC(12,2) DEFAULT 0,\n        nominal_amount           NUMERIC(12,2) DEFAULT 0,\n        tutor_payable_amount     NUMERIC(12,2) DEFAULT 0,\n        margin_amount            NUMERIC(12,2) DEFAULT 0,\n        quota_paid_before        INTEGER DEFAULT 0,\n        quota_used_before        INTEGER DEFAULT 0,\n        quota_remaining_before   INTEGER DEFAULT 0,\n        notes         TEXT,\n        created_at    TIMESTAMP DEFAULT NOW(),\n        updated_at    TIMESTAMP DEFAULT NOW()\n    )",
    "CREATE INDEX IF NOT EXISTS ix_student_invoice_lines_invoice_id    ON student_invoice_lines(invoice_id)",
    "CREATE INDEX IF NOT EXISTS ix_student_invoice_lines_enrollment_id ON student_invoice_lines(enrollment_id)",
    # Payroll proof of transfer
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS proof_image  VARCHAR(500)",
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS proof_notes  TEXT",
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS whatsapp_last_contact_id VARCHAR(255)",
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS whatsapp_last_message TEXT",
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS whatsapp_last_sent_at TIMESTAMP",
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS whatsapp_last_status VARCHAR(50)",
    # Students — possibly added after initial deploy
    "ALTER TABLE students ADD COLUMN IF NOT EXISTS status    VARCHAR(20)  DEFAULT 'active'",
    "ALTER TABLE students ADD COLUMN IF NOT EXISTS is_active BOOLEAN      DEFAULT TRUE",
    "ALTER TABLE students ADD COLUMN IF NOT EXISTS whatsapp_group_memberships_json JSONB",
    # Tutors
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS status    VARCHAR(20)  DEFAULT 'active'",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS is_active BOOLEAN      DEFAULT TRUE",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS profile_photo_path VARCHAR(500)",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS cv_file_path VARCHAR(500)",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_username VARCHAR(80)",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_password_hash VARCHAR(255)",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_must_change_password BOOLEAN DEFAULT TRUE",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_email_verified BOOLEAN DEFAULT FALSE",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS portal_email_verified_at TIMESTAMP",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_tutors_portal_username ON tutors(portal_username)",
    # Enrollments
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS is_active                BOOLEAN  DEFAULT TRUE",
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS meeting_quota_per_month  INTEGER  DEFAULT 4",
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS whatsapp_group_id        VARCHAR(255)",
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS whatsapp_group_name      VARCHAR(255)",
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS whatsapp_group_memberships_json JSONB",
    # Student payments — verification workflow
    "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS is_verified  BOOLEAN   DEFAULT FALSE",
    "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS verified_by  INTEGER   REFERENCES users(id)",
    "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS verified_at  TIMESTAMP",
    # Pricing rules
    "ALTER TABLE pricing_rules ADD COLUMN IF NOT EXISTS is_active              BOOLEAN  DEFAULT TRUE",
    "ALTER TABLE pricing_rules ADD COLUMN IF NOT EXISTS default_meeting_quota  INTEGER  DEFAULT 4",
    # TutorPayout — session exclusion list and status default fix
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS excluded_session_ids JSONB DEFAULT '[]'",
    # WhatsApp evaluation manual audit marker; does not affect attendance/payroll math
    "ALTER TABLE whatsapp_evaluations ADD COLUMN IF NOT EXISTS manual_review_status VARCHAR(20) DEFAULT 'pending' NOT NULL",
    "ALTER TABLE whatsapp_evaluations ADD COLUMN IF NOT EXISTS manual_reviewed_at TIMESTAMP",
    "ALTER TABLE whatsapp_evaluations ADD COLUMN IF NOT EXISTS manual_reviewed_by INTEGER REFERENCES users(id)",
    "ALTER TABLE whatsapp_evaluations ADD COLUMN IF NOT EXISTS manual_review_notes TEXT",
    "CREATE INDEX IF NOT EXISTS ix_whatsapp_evaluations_manual_review_status ON whatsapp_evaluations(manual_review_status)",
    "CREATE TABLE IF NOT EXISTS attendance_period_locks (\n        id        SERIAL PRIMARY KEY,\n        month     INTEGER NOT NULL,\n        year      INTEGER NOT NULL,\n        notes     TEXT,\n        locked_by INTEGER REFERENCES users(id),\n        locked_at TIMESTAMP DEFAULT NOW() NOT NULL,\n        created_at TIMESTAMP DEFAULT NOW() NOT NULL,\n        updated_at TIMESTAMP DEFAULT NOW() NOT NULL,\n        CONSTRAINT uq_attendance_period_locks_month_year UNIQUE(month, year)\n    )",
    "CREATE INDEX IF NOT EXISTS ix_attendance_period_locks_month ON attendance_period_locks(month)",
    "CREATE INDEX IF NOT EXISTS ix_attendance_period_locks_year ON attendance_period_locks(year)",
    # Manual subject tutor visibility overrides
    "CREATE TABLE IF NOT EXISTS subject_tutor_assignments (\n        id         SERIAL PRIMARY KEY,\n        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,\n        tutor_id   INTEGER NOT NULL REFERENCES tutors(id) ON DELETE CASCADE,\n        status     VARCHAR(20) NOT NULL DEFAULT 'included',\n        notes      TEXT,\n        created_at TIMESTAMP DEFAULT NOW(),\n        updated_at TIMESTAMP DEFAULT NOW(),\n        CONSTRAINT uq_subject_tutor_assignments_subject_tutor UNIQUE(subject_id, tutor_id)\n    )",
    "CREATE TABLE IF NOT EXISTS tutor_portal_requests (\n        id            SERIAL PRIMARY KEY,\n        tutor_id      INTEGER NOT NULL REFERENCES tutors(id) ON DELETE CASCADE,\n        request_type  VARCHAR(40) NOT NULL,\n        status        VARCHAR(20) NOT NULL DEFAULT 'pending',\n        payload_json  JSONB DEFAULT '{}'::jsonb,\n        notes         TEXT,\n        admin_notes   TEXT,\n        requested_at  TIMESTAMP DEFAULT NOW() NOT NULL,\n        reviewed_at   TIMESTAMP,\n        reviewed_by   INTEGER REFERENCES users(id)\n    )",
    "CREATE INDEX IF NOT EXISTS ix_tutor_portal_requests_tutor_id ON tutor_portal_requests(tutor_id)",
    "CREATE INDEX IF NOT EXISTS ix_tutor_portal_requests_request_type ON tutor_portal_requests(request_type)",
    "CREATE INDEX IF NOT EXISTS ix_tutor_portal_requests_status ON tutor_portal_requests(status)",
    "CREATE TABLE IF NOT EXISTS recruitment_candidates (\n        id SERIAL PRIMARY KEY,\n        google_email VARCHAR(160) NOT NULL,\n        email_verified BOOLEAN DEFAULT FALSE NOT NULL,\n        password_hash VARCHAR(255),\n        name VARCHAR(120),\n        phone VARCHAR(40),\n        address TEXT,\n        subject_interest VARCHAR(160),\n        teaching_preferences_json TEXT,\n        last_education_level VARCHAR(40),\n        university_name VARCHAR(160),\n        age INTEGER,\n        gender VARCHAR(20),\n        cv_file_path VARCHAR(500),\n        photo_file_path VARCHAR(500),\n        status VARCHAR(30) NOT NULL DEFAULT 'draft',\n        meet_link VARCHAR(500),\n        interview_notes TEXT,\n        contract_text TEXT,\n        offering_text TEXT,\n        signature_data_url TEXT,\n        invited_at TIMESTAMP,\n        interview_agreed_at TIMESTAMP,\n        contract_sent_at TIMESTAMP,\n        signed_at TIMESTAMP,\n        tutor_id INTEGER REFERENCES tutors(id),\n        created_at TIMESTAMP DEFAULT NOW() NOT NULL,\n        updated_at TIMESTAMP DEFAULT NOW() NOT NULL\n    )",
    "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
    "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS teaching_preferences_json TEXT",
    "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS last_education_level VARCHAR(40)",
    "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS university_name VARCHAR(160)",
    "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS age INTEGER",
    "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS gender VARCHAR(20)",
    "CREATE INDEX IF NOT EXISTS ix_recruitment_candidates_google_email ON recruitment_candidates(google_email)",
    "CREATE INDEX IF NOT EXISTS ix_recruitment_candidates_status ON recruitment_candidates(status)",
    "CREATE INDEX IF NOT EXISTS ix_recruitment_candidates_tutor_id ON recruitment_candidates(tutor_id)",
]
with app.app_context():
    for stmt in EXTRA_DDL:
        try:
            db.session.execute(db.text(stmt.strip()))
        except Exception as exc:
            print(f"[entrypoint] DDL warning (skipping): {exc}")
            db.session.rollback()
    db.session.commit()
    print("[entrypoint] Extra DDL applied.")
PYEOF

else
  echo "[entrypoint] DATABASE_URL not set – skipping DB init."
fi

# ── Create required directories ──────────────────────────────────────────────
mkdir -p logs uploads/payroll_proofs uploads/recruitment/cv uploads/recruitment/photos

# ── Launch ───────────────────────────────────────────────────────────────────
echo "[entrypoint] Launching app on 0.0.0.0:${PORT} with ${GUNICORN_WORKERS} workers..."

if [ "$#" -eq 0 ]; then
  exec gunicorn \
    --workers "$GUNICORN_WORKERS" \
    --bind    "0.0.0.0:${PORT}"  \
    --timeout 120                \
    --access-logfile -           \
    --error-logfile  -           \
    run:app
fi

if [ "$1" = "gunicorn" ]; then
  shift
  exec gunicorn --workers "$GUNICORN_WORKERS" --bind "0.0.0.0:${PORT}" "$@"
fi

exec "$@"
