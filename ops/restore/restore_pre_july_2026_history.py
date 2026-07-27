#!/usr/bin/env python3
"""Restore pre-July 2026 WhatsApp attendance history from an isolated backup DB."""

import argparse
import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db  # noqa: E402


SOURCE_DATABASE = "lbb_pre_restore_20260711"
DATE_CUTOFF = "2026-07-01"
MESSAGE_CUTOFF = "2026-06-30 17:00:00"
LOCK_KEY = "restore-pre-july-2026-history"


@dataclass(frozen=True)
class TableSpec:
    name: str
    historical_where: str
    current_where: str


TABLES = (
    TableSpec(
        "whatsapp_messages",
        f"sent_at < TIMESTAMP '{MESSAGE_CUTOFF}'",
        f"sent_at >= TIMESTAMP '{MESSAGE_CUTOFF}'",
    ),
    TableSpec(
        "attendance_sessions",
        f"session_date < DATE '{DATE_CUTOFF}'",
        f"session_date >= DATE '{DATE_CUTOFF}'",
    ),
    TableSpec(
        "whatsapp_evaluations",
        f"attendance_date < DATE '{DATE_CUTOFF}'",
        f"attendance_date >= DATE '{DATE_CUTOFF}'",
    ),
)

PARENT_REFERENCES = {
    "whatsapp_messages": (
        ("group_id", "whatsapp_groups"),
        ("author_contact_id", "whatsapp_contacts"),
    ),
    "attendance_sessions": (
        ("enrollment_id", "enrollments"),
        ("student_id", "students"),
        ("tutor_id", "tutors"),
        ("subject_id", "subjects"),
    ),
    "whatsapp_evaluations": (
        ("group_id", "whatsapp_groups"),
        ("matched_student_id", "students"),
        ("matched_tutor_id", "tutors"),
        ("matched_subject_id", "subjects"),
        ("matched_enrollment_id", "enrollments"),
        ("manual_reviewed_by", "users"),
    ),
}


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def fetch_scalar(connection, query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or ())
        row = cursor.fetchone()
    return row[0] if row else None


def fetch_set(connection, query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or ())
        return {row[0] for row in cursor.fetchall()}


def table_columns(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return [row[0] for row in cursor.fetchall()]


def row_signature(connection, table, where):
    quoted_table = quote_identifier(table)
    query = f"""
        SELECT
            count(*),
            md5(COALESCE(
                string_agg(md5(row_to_json(rows)::text), '' ORDER BY id),
                ''
            ))
        FROM (
            SELECT *
            FROM {quoted_table}
            WHERE {where}
            ORDER BY id
        ) AS rows
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        count, digest = cursor.fetchone()
    return {"count": count, "digest": digest}


def signatures(connection, use_historical):
    result = {}
    for spec in TABLES:
        where = spec.historical_where if use_historical else spec.current_where
        result[spec.name] = row_signature(connection, spec.name, where)
    return result


def find_missing_parent_ids(source_connection, target_connection, spec):
    missing = {}
    for column, parent_table in PARENT_REFERENCES[spec.name]:
        source_ids = fetch_set(
            source_connection,
            f"""
            SELECT DISTINCT {quote_identifier(column)}
            FROM {quote_identifier(spec.name)}
            WHERE {spec.historical_where}
              AND {quote_identifier(column)} IS NOT NULL
            """,
        )
        target_ids = fetch_set(
            target_connection,
            f"SELECT id FROM {quote_identifier(parent_table)}",
        )
        absent = sorted(source_ids - target_ids)
        if absent:
            missing[f"{spec.name}.{column}->{parent_table}.id"] = {
                "count": len(absent),
                "sample": absent[:10],
            }
    return missing


def cross_boundary_conflicts(connection):
    checks = {
        "future_evaluation_to_historical_message": f"""
            SELECT count(*)
            FROM whatsapp_evaluations AS evaluation
            JOIN whatsapp_messages AS message ON message.id = evaluation.message_id
            WHERE evaluation.attendance_date >= DATE '{DATE_CUTOFF}'
              AND message.sent_at < TIMESTAMP '{MESSAGE_CUTOFF}'
        """,
        "future_evaluation_to_historical_attendance": f"""
            SELECT count(*)
            FROM whatsapp_evaluations AS evaluation
            JOIN attendance_sessions AS attendance
              ON attendance.id = evaluation.attendance_session_id
            WHERE evaluation.attendance_date >= DATE '{DATE_CUTOFF}'
              AND attendance.session_date < DATE '{DATE_CUTOFF}'
        """,
        "historical_evaluation_to_future_message": f"""
            SELECT count(*)
            FROM whatsapp_evaluations AS evaluation
            JOIN whatsapp_messages AS message ON message.id = evaluation.message_id
            WHERE evaluation.attendance_date < DATE '{DATE_CUTOFF}'
              AND message.sent_at >= TIMESTAMP '{MESSAGE_CUTOFF}'
        """,
        "historical_evaluation_to_future_attendance": f"""
            SELECT count(*)
            FROM whatsapp_evaluations AS evaluation
            JOIN attendance_sessions AS attendance
              ON attendance.id = evaluation.attendance_session_id
            WHERE evaluation.attendance_date < DATE '{DATE_CUTOFF}'
              AND attendance.session_date >= DATE '{DATE_CUTOFF}'
        """,
        "deleted_record_to_historical_attendance": f"""
            SELECT count(*)
            FROM deleted_attendance_sessions AS deleted
            JOIN attendance_sessions AS attendance
              ON attendance.id = deleted.restored_session_id
            WHERE attendance.session_date < DATE '{DATE_CUTOFF}'
        """,
    }
    conflicts = {}
    for name, query in checks.items():
        count = fetch_scalar(connection, query)
        if count:
            conflicts[name] = count
    return conflicts


def source_link_conflicts(source_connection):
    checks = {
        "historical_evaluation_without_historical_message": f"""
            SELECT count(*)
            FROM whatsapp_evaluations AS evaluation
            LEFT JOIN whatsapp_messages AS message ON message.id = evaluation.message_id
            WHERE evaluation.attendance_date < DATE '{DATE_CUTOFF}'
              AND (
                message.id IS NULL
                OR message.sent_at >= TIMESTAMP '{MESSAGE_CUTOFF}'
              )
        """,
        "historical_evaluation_without_historical_attendance": f"""
            SELECT count(*)
            FROM whatsapp_evaluations AS evaluation
            LEFT JOIN attendance_sessions AS attendance
              ON attendance.id = evaluation.attendance_session_id
            WHERE evaluation.attendance_date < DATE '{DATE_CUTOFF}'
              AND evaluation.attendance_session_id IS NOT NULL
              AND (
                attendance.id IS NULL
                OR attendance.session_date >= DATE '{DATE_CUTOFF}'
              )
        """,
    }
    conflicts = {}
    for name, query in checks.items():
        count = fetch_scalar(source_connection, query)
        if count:
            conflicts[name] = count
    return conflicts


def collision_conflicts(source_connection, target_connection):
    conflicts = {}
    for spec in TABLES:
        source_ids = fetch_set(
            source_connection,
            f"""
            SELECT id FROM {quote_identifier(spec.name)}
            WHERE {spec.historical_where}
            """,
        )
        target_current_ids = fetch_set(
            target_connection,
            f"""
            SELECT id FROM {quote_identifier(spec.name)}
            WHERE {spec.current_where}
            """,
        )
        collisions = sorted(source_ids & target_current_ids)
        if collisions:
            conflicts[f"{spec.name}.historical_id_to_current_id"] = {
                "count": len(collisions),
                "sample": collisions[:10],
            }

    source_message_ids = fetch_set(
        source_connection,
        f"""
        SELECT whatsapp_message_id
        FROM whatsapp_messages
        WHERE sent_at < TIMESTAMP '{MESSAGE_CUTOFF}'
        """,
    )
    target_message_ids = fetch_set(
        target_connection,
        f"""
        SELECT whatsapp_message_id
        FROM whatsapp_messages
        WHERE sent_at >= TIMESTAMP '{MESSAGE_CUTOFF}'
        """,
    )
    message_id_collisions = sorted(source_message_ids & target_message_ids)
    if message_id_collisions:
        conflicts["whatsapp_messages.historical_key_to_current_key"] = {
            "count": len(message_id_collisions),
            "sample": message_id_collisions[:10],
        }
    return conflicts


def preflight(source_connection, target_connection):
    conflicts = {}
    columns = {}
    for spec in TABLES:
        source_columns = table_columns(source_connection, spec.name)
        target_columns = table_columns(target_connection, spec.name)
        columns[spec.name] = target_columns
        if not source_columns or source_columns != target_columns:
            conflicts[f"{spec.name}.schema"] = {
                "source": source_columns,
                "target": target_columns,
            }
        conflicts.update(
            find_missing_parent_ids(source_connection, target_connection, spec)
        )

    conflicts.update(
        {
            f"target.{name}": value
            for name, value in cross_boundary_conflicts(target_connection).items()
        }
    )
    conflicts.update(
        {
            f"source.{name}": value
            for name, value in source_link_conflicts(source_connection).items()
        }
    )
    conflicts.update(collision_conflicts(source_connection, target_connection))
    return columns, conflicts


def export_historical_rows(source_connection, columns):
    exports = {}
    for spec in TABLES:
        buffer = io.StringIO()
        column_sql = ", ".join(quote_identifier(column) for column in columns[spec.name])
        query = f"""
            COPY (
                SELECT {column_sql}
                FROM {quote_identifier(spec.name)}
                WHERE {spec.historical_where}
                ORDER BY id
            ) TO STDOUT WITH (FORMAT CSV, NULL '\\N')
        """
        with source_connection.cursor() as cursor:
            cursor.copy_expert(query, buffer)
        buffer.seek(0)
        exports[spec.name] = buffer
    return exports


def reset_sequence(cursor, table_name):
    cursor.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence(%s, 'id'),
            COALESCE((SELECT max(id) FROM {quote_identifier(table_name)}), 1),
            EXISTS(SELECT 1 FROM {quote_identifier(table_name)})
        )
        """,
        (table_name,),
    )


def execute_restore(
    source_connection,
    target_connection,
    columns,
    source_historical,
    target_current_before,
):
    exports = export_historical_rows(source_connection, columns)
    target_connection.rollback()
    try:
        with target_connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_KEY,))
            cursor.execute(
                """
                LOCK TABLE
                    whatsapp_evaluations,
                    whatsapp_messages,
                    attendance_sessions,
                    deleted_attendance_sessions
                IN ACCESS EXCLUSIVE MODE
                """
            )

        locked_current = signatures(target_connection, use_historical=False)
        if locked_current != target_current_before:
            raise RuntimeError("Current-period rows changed after dry-run preflight.")
        locked_conflicts = cross_boundary_conflicts(target_connection)
        if locked_conflicts:
            raise RuntimeError(
                f"Cross-boundary references appeared before restore: {locked_conflicts}"
            )

        with target_connection.cursor() as cursor:
            cursor.execute(
                f"""
                DELETE FROM whatsapp_evaluations
                WHERE attendance_date < DATE '{DATE_CUTOFF}'
                """
            )
            cursor.execute(
                f"""
                DELETE FROM whatsapp_messages
                WHERE sent_at < TIMESTAMP '{MESSAGE_CUTOFF}'
                """
            )
            cursor.execute(
                f"""
                DELETE FROM attendance_sessions
                WHERE session_date < DATE '{DATE_CUTOFF}'
                """
            )

            for spec in TABLES:
                column_sql = ", ".join(
                    quote_identifier(column) for column in columns[spec.name]
                )
                cursor.copy_expert(
                    f"""
                    COPY {quote_identifier(spec.name)} ({column_sql})
                    FROM STDIN WITH (FORMAT CSV, NULL '\\N')
                    """,
                    exports[spec.name],
                )
                reset_sequence(cursor, spec.name)

        restored_historical = signatures(target_connection, use_historical=True)
        restored_current = signatures(target_connection, use_historical=False)
        if restored_historical != source_historical:
            raise RuntimeError("Restored historical checksum does not match backup.")
        if restored_current != target_current_before:
            raise RuntimeError("Current-period checksum changed during restore.")
        if cross_boundary_conflicts(target_connection):
            raise RuntimeError("Restore created a cross-boundary reference.")

        target_connection.commit()
        return {
            "historical_after": restored_historical,
            "current_period_after": restored_current,
        }
    except Exception:
        target_connection.rollback()
        raise


def run(execute):
    app = create_app(os.getenv("FLASK_ENV", "production"))
    with app.app_context():
        target_database = db.engine.url.database
        if not target_database or target_database == SOURCE_DATABASE:
            raise SystemExit("Target and source databases must be different.")

        source_exists = db.session.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database"),
            {"database": SOURCE_DATABASE},
        ).scalar()
        db.session.rollback()
        if not source_exists:
            raise SystemExit(f"Source database does not exist: {SOURCE_DATABASE}")

        source_engine = create_engine(db.engine.url.set(database=SOURCE_DATABASE))
        source_connection = source_engine.raw_connection()
        target_connection = db.engine.raw_connection()
        try:
            columns, conflicts = preflight(source_connection, target_connection)
            source_historical = signatures(
                source_connection,
                use_historical=True,
            )
            target_historical = signatures(
                target_connection,
                use_historical=True,
            )
            target_current = signatures(
                target_connection,
                use_historical=False,
            )
            summary = {
                "mode": "execute" if execute else "dry-run",
                "source_database": SOURCE_DATABASE,
                "target_database": target_database,
                "cutoff": {
                    "attendance_and_evaluations": DATE_CUTOFF,
                    "messages_utc": MESSAGE_CUTOFF,
                },
                "source_historical": source_historical,
                "target_historical_before": target_historical,
                "target_current_period_preserved": target_current,
                "conflicts": conflicts,
            }

            if conflicts:
                print(json.dumps(summary, indent=2, default=str))
                raise SystemExit("Restore aborted: preflight conflicts found.")

            if execute:
                summary.update(
                    execute_restore(
                        source_connection,
                        target_connection,
                        columns,
                        source_historical,
                        target_current,
                    )
                )
            print(json.dumps(summary, indent=2, default=str))
        finally:
            source_connection.close()
            target_connection.close()
            source_engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Commit the selective restore. Without this flag the command is read-only.",
    )
    args = parser.parse_args()
    run(args.execute)


if __name__ == "__main__":
    main()
