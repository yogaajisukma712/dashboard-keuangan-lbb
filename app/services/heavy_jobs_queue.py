"""Queue helper untuk heavy_jobs (Neon).

Dashboard (Vercel, serverless) hanya INSERT job; worker VM bot yang polling.
VM mati → job tetap `pending`, diproses saat VM hidup lagi.
"""

import json
import os

from app.extensions import db


def enqueue_job(job_type: str, payload: dict, requested_by: str | None = None) -> int:
    """INSERT satu job heavy_jobs, return id. Membuat koneksi DB baru jika perlu
    (aman dipanggil dari context Flask manapun)."""
    sql = """
        INSERT INTO heavy_jobs (job_type, payload, requested_by)
        VALUES (:job_type, CAST(:payload AS jsonb), :requested_by)
        RETURNING id
    """
    result = db.session.execute(
        __import__("sqlalchemy").text(sql),
        {
            "job_type": job_type,
            "payload": json.dumps(payload),
            "requested_by": requested_by,
        },
    )
    job_id = result.scalar()
    db.session.commit()
    return job_id


def update_job_status(job_id: int, status: str, result: dict | None = None, error: str | None = None):
    """Untuk endpoint worker callback (opsional dipakai worker JS)."""
    from sqlalchemy import text

    db.session.execute(
        text(
            """
            UPDATE heavy_jobs
               SET status = :status,
                   finished_at = CASE WHEN :status IN ('done','failed') THEN now() ELSE finished_at END,
                   result = CAST(:result AS jsonb),
                   error = :error
             WHERE id = :job_id
            """
        ),
        {
            "status": status,
            "result": json.dumps(result or {}),
            "error": error,
            "job_id": job_id,
        },
    )
    db.session.commit()
