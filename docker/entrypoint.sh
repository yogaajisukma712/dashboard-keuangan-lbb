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
        status        VARCHAR(20)   DEFAULT 'draft',
        notes         TEXT,
        created_by    INTEGER REFERENCES users(id),
        created_at    TIMESTAMP DEFAULT NOW(),
        updated_at    TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_student_invoices_student_id    ON student_invoices(student_id)",
    "CREATE INDEX IF NOT EXISTS ix_student_invoices_enrollment_id ON student_invoices(enrollment_id)",
    # Payroll proof of transfer
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS proof_image  VARCHAR(500)",
    "ALTER TABLE tutor_payouts ADD COLUMN IF NOT EXISTS proof_notes  TEXT",
    # Students — possibly added after initial deploy
    "ALTER TABLE students ADD COLUMN IF NOT EXISTS status    VARCHAR(20)  DEFAULT 'active'",
    "ALTER TABLE students ADD COLUMN IF NOT EXISTS is_active BOOLEAN      DEFAULT TRUE",
    # Tutors
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS status    VARCHAR(20)  DEFAULT 'active'",
    "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS is_active BOOLEAN      DEFAULT TRUE",
    # Enrollments
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS is_active                BOOLEAN  DEFAULT TRUE",
    "ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS meeting_quota_per_month  INTEGER  DEFAULT 4",
    # Student payments — verification workflow
    "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS is_verified  BOOLEAN   DEFAULT FALSE",
    "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS verified_by  INTEGER   REFERENCES users(id)",
    "ALTER TABLE student_payments ADD COLUMN IF NOT EXISTS verified_at  TIMESTAMP",
    # Pricing rules
    "ALTER TABLE pricing_rules ADD COLUMN IF NOT EXISTS is_active              BOOLEAN  DEFAULT TRUE",
    "ALTER TABLE pricing_rules ADD COLUMN IF NOT EXISTS default_meeting_quota  INTEGER  DEFAULT 4",
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
mkdir -p logs uploads/payroll_proofs

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
