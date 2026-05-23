"""
Enrollments routes for Dashboard Keuangan LBB Super Smart
Handles all enrollment-related operations
"""

from datetime import datetime
from decimal import Decimal

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session as flask_session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import bindparam, inspect, or_, text
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.forms import EnrollmentForm
from app.models import (
    AttendanceSession,
    Curriculum,
    DeletedEnrollment,
    Enrollment,
    EnrollmentSchedule,
    Level,
    Student,
    StudentPayment,
    StudentPaymentLine,
    Subject,
    Tutor,
    TutorMeetLink,
    WhatsAppEvaluation,
    WhatsAppGroup,
)
from app.services.whatsapp_ingest_service import WhatsAppIngestService
from app.utils import decode_public_id, get_per_page

enrollments_bp = Blueprint("enrollments", __name__, url_prefix="/enrollments")
DEFAULT_ENROLLMENT_SORT = "last_attendance_desc"
ENROLLMENT_LIST_STATE_KEY = "enrollment_list_state"
ENROLLMENT_LIST_STATE_VERSION = 2
ENROLLMENT_SORT_OPTIONS = {
    "updated_desc",
    "last_attendance_desc",
    "last_attendance_asc",
}


def _normalize_rate_form_value(value):
    """Render DB numeric values into whole-number form defaults."""
    if value is None:
        return None
    return int(value)


def _get_enrollment_by_ref_or_404(enrollment_ref: str):
    """Resolve opaque enrollment ref to model instance."""
    try:
        enrollment_id = decode_public_id(enrollment_ref, "enrollment")
    except ValueError:
        abort(404)
    return Enrollment.query.get_or_404(enrollment_id)


def _build_pricing_public_id_maps():
    return {
        "curriculum_public_ids": {
            str(curriculum.id): curriculum.public_id for curriculum in Curriculum.query.all()
        },
        "level_public_ids": {str(level.id): level.public_id for level in Level.query.all()},
    }


def _apply_selected_whatsapp_group(enrollment: Enrollment, group_id: int | None):
    group = db.session.get(WhatsAppGroup, group_id) if group_id else None
    if group is None:
        enrollment.whatsapp_group_id = None
        enrollment.whatsapp_group_name = None
        enrollment.whatsapp_group_memberships_json = []
        return

    enrollment.whatsapp_group_id = group.whatsapp_group_id
    enrollment.whatsapp_group_name = group.name
    enrollment.whatsapp_group_memberships_json = [
        {
            "group_id": group.id,
            "whatsapp_group_id": group.whatsapp_group_id,
            "group_name": group.name,
        }
    ]


def _enrollment_has_whatsapp_group(enrollment: Enrollment) -> bool:
    return bool(
        str(enrollment.whatsapp_group_id or "").strip()
        or (enrollment.whatsapp_group_memberships_json or [])
    )


def _scan_missing_enrollment_whatsapp_groups() -> dict:
    summary = {
        "processed": 0,
        "matched": 0,
        "unmatched": 0,
    }
    enrollments = Enrollment.query.filter_by(status="active").order_by(Enrollment.id.asc()).all()
    for enrollment in enrollments:
        if _enrollment_has_whatsapp_group(enrollment):
            continue
        summary["processed"] += 1
        result = WhatsAppIngestService.sync_enrollment_whatsapp_group(enrollment)
        if result["matched"]:
            summary["matched"] += 1
        else:
            summary["unmatched"] += 1
    return summary


def _build_enrollment_list_query(
    search_term: str = "",
    status: str = "",
    sort_by: str = DEFAULT_ENROLLMENT_SORT,
):
    query = (
        Enrollment.query.join(Student, Enrollment.student_id == Student.id)
        .join(Tutor, Enrollment.tutor_id == Tutor.id)
        .join(Subject, Enrollment.subject_id == Subject.id)
    )

    normalized_status = str(status or "").strip().lower()
    if normalized_status:
        query = query.filter(Enrollment.status == normalized_status)

    normalized_search = str(search_term or "").strip()
    if normalized_search:
        like_term = f"%{normalized_search}%"
        query = query.filter(
            or_(
                Student.name.ilike(like_term),
                Student.student_code.ilike(like_term),
                Tutor.name.ilike(like_term),
                Tutor.tutor_code.ilike(like_term),
                Subject.name.ilike(like_term),
                Enrollment.grade.ilike(like_term),
                Enrollment.whatsapp_group_name.ilike(like_term),
                Enrollment.whatsapp_group_id.ilike(like_term),
            )
        )

    if sort_by in {"last_attendance_desc", "last_attendance_asc"}:
        last_attendance = (
            db.session.query(
                AttendanceSession.enrollment_id.label("enrollment_id"),
                db.func.max(AttendanceSession.session_date).label("last_attendance_date"),
            )
            .group_by(AttendanceSession.enrollment_id)
            .subquery()
        )
        query = query.outerjoin(
            last_attendance,
            Enrollment.id == last_attendance.c.enrollment_id,
        )
        if sort_by == "last_attendance_asc":
            return query.order_by(
                db.func.coalesce(
                    last_attendance.c.last_attendance_date,
                    "9999-12-31",
                ).asc(),
                Enrollment.id.asc(),
            )
        return query.order_by(
            db.func.coalesce(
                last_attendance.c.last_attendance_date,
                "1900-01-01",
            ).desc(),
            Enrollment.id.desc(),
        )

    return query.order_by(Enrollment.updated_at.desc(), Enrollment.id.desc())


def _store_enrollment_list_state(
    page: int,
    per_page: int,
    search_term: str,
    status: str,
    sort_by: str,
) -> dict:
    state = {
        "v": ENROLLMENT_LIST_STATE_VERSION,
        "page": max(page or 1, 1),
        "per_page": max(per_page or 1, 1),
        "q": str(search_term or ""),
        "status": str(status or ""),
        "sort": sort_by if sort_by in ENROLLMENT_SORT_OPTIONS else DEFAULT_ENROLLMENT_SORT,
    }
    flask_session[ENROLLMENT_LIST_STATE_KEY] = state
    return state


def _public_enrollment_list_state(state: dict | None) -> dict:
    return {key: value for key, value in (state or {}).items() if key != "v"}


def _list_redirect_kwargs_from_request() -> dict:
    return {
        key: value
        for key, value in {
            "q": request.args.get("q", "", type=str),
            "status": request.args.get("status", "", type=str),
            "sort": request.args.get("sort", DEFAULT_ENROLLMENT_SORT, type=str),
            "page": request.args.get("page", 1, type=int),
            "per_page": request.args.get("per_page", get_per_page(), type=int),
        }.items()
        if value not in (None, "")
    }


def _json_value(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _parse_datetime(value):
    return datetime.fromisoformat(value) if value else None


def _parse_date(value):
    from datetime import date

    return date.fromisoformat(value) if value else None


def _parse_time(value):
    from datetime import time

    return time.fromisoformat(value) if value else None


def _model_payload(model, fields: tuple[str, ...]) -> dict:
    return {field: _json_value(getattr(model, field)) for field in fields}


def _restore_original_id_if_free(model_class, model, original_id):
    if original_id and db.session.get(model_class, original_id) is None:
        model.id = original_id


def _raw_table_rows(table_name: str, where_sql: str, params: dict) -> list[dict]:
    if table_name not in set(inspect(db.engine).get_table_names()):
        return []
    rows = db.session.execute(text(f"SELECT * FROM {table_name} WHERE {where_sql}"), params)
    return [
        {key: _json_value(value) for key, value in dict(row._mapping).items()}
        for row in rows
    ]


def _raw_table_rows_by_ids(table_name: str, id_column: str, ids: list[int]) -> list[dict]:
    if not ids or table_name not in set(inspect(db.engine).get_table_names()):
        return []
    rows = db.session.execute(
        text(f"SELECT * FROM {table_name} WHERE {id_column} IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": ids},
    )
    return [
        {key: _json_value(value) for key, value in dict(row._mapping).items()}
        for row in rows
    ]


def _insert_raw_rows(table_name: str, rows: list[dict]) -> None:
    if not rows or table_name not in set(inspect(db.engine).get_table_names()):
        return
    columns = list(rows[0].keys())
    column_sql = ", ".join(columns)
    value_sql = ", ".join(f":{column}" for column in columns)
    db.session.execute(
        text(f"INSERT INTO {table_name} ({column_sql}) VALUES ({value_sql})"),
        rows,
    )


def _enrollment_delete_snapshot(enrollment: Enrollment) -> dict:
    enrollment_id = enrollment.id
    attendance_sessions = AttendanceSession.query.filter_by(
        enrollment_id=enrollment_id
    ).all()
    attendance_ids = [item.id for item in attendance_sessions]
    payment_lines = StudentPaymentLine.query.filter_by(enrollment_id=enrollment_id).all()
    payment_ids = sorted({line.student_payment_id for line in payment_lines})
    payment_headers = (
        StudentPayment.query.filter(StudentPayment.id.in_(payment_ids)).all()
        if payment_ids
        else []
    )
    legacy_invoices = _raw_table_rows(
        "student_invoices",
        "enrollment_id = :enrollment_id",
        {"enrollment_id": enrollment_id},
    )
    legacy_invoice_ids = [row["id"] for row in legacy_invoices]
    legacy_invoice_lines = _raw_table_rows(
        "student_invoice_lines",
        "enrollment_id = :enrollment_id",
        {"enrollment_id": enrollment_id},
    )
    if legacy_invoice_ids:
        legacy_invoice_lines.extend(
            _raw_table_rows_by_ids(
                "student_invoice_lines", "invoice_id", legacy_invoice_ids
            )
        )

    return {
        "enrollment": _model_payload(
            enrollment,
            (
                "id",
                "student_id",
                "subject_id",
                "tutor_id",
                "curriculum_id",
                "level_id",
                "grade",
                "meeting_quota_per_month",
                "student_rate_per_meeting",
                "tutor_rate_per_meeting",
                "start_date",
                "end_date",
                "status",
                "notes",
                "is_active",
                "whatsapp_group_id",
                "whatsapp_group_name",
                "whatsapp_group_memberships_json",
                "created_at",
                "updated_at",
            ),
        ),
        "label": {
            "student_name": enrollment.student.name if enrollment.student else "",
            "tutor_name": enrollment.tutor.name if enrollment.tutor else "",
            "subject_name": enrollment.subject.name if enrollment.subject else "",
            "curriculum_name": enrollment.curriculum.name if enrollment.curriculum else "",
            "level_name": enrollment.level.name if enrollment.level else "",
        },
        "schedules": [
            _model_payload(
                schedule,
                (
                    "id",
                    "day_of_week",
                    "day_name",
                    "start_time",
                    "end_time",
                    "location",
                    "is_active",
                    "created_at",
                    "updated_at",
                ),
            )
            for schedule in EnrollmentSchedule.query.filter_by(
                enrollment_id=enrollment_id
            ).all()
        ],
        "attendance_sessions": [
            _model_payload(
                item,
                (
                    "id",
                    "student_id",
                    "tutor_id",
                    "subject_id",
                    "session_date",
                    "status",
                    "student_present",
                    "tutor_present",
                    "tutor_fee_amount",
                    "notes",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in attendance_sessions
        ],
        "student_payments": [
            _model_payload(
                payment,
                (
                    "id",
                    "payment_date",
                    "student_id",
                    "receipt_number",
                    "payment_method",
                    "total_amount",
                    "notes",
                    "is_verified",
                    "verified_by",
                    "verified_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for payment in payment_headers
        ],
        "student_payment_lines": [
            _model_payload(
                line,
                (
                    "id",
                    "student_payment_id",
                    "service_month",
                    "meeting_count",
                    "student_rate_per_meeting",
                    "tutor_rate_per_meeting",
                    "nominal_amount",
                    "tutor_payable_amount",
                    "margin_amount",
                    "notes",
                    "created_at",
                    "updated_at",
                ),
            )
            for line in payment_lines
        ],
        "tutor_meet_links": [
            _model_payload(
                link,
                (
                    "id",
                    "tutor_id",
                    "student_id",
                    "subject_id",
                    "token",
                    "room",
                    "join_url",
                    "jitsi_url",
                    "status",
                    "max_joins",
                    "source",
                    "valid_from",
                    "expires_at",
                    "created_at",
                    "updated_at",
                ),
            )
            for link in list(enrollment.tutor_meet_links)
        ],
        "whatsapp_evaluations": [
            _model_payload(
                evaluation,
                (
                    "id",
                    "message_id",
                    "group_id",
                    "student_name",
                    "tutor_name",
                    "subject_name",
                    "focus_topic",
                    "summary_text",
                    "source_language",
                    "reported_lesson_date",
                    "reported_time_label",
                    "attendance_date",
                    "matched_student_id",
                    "matched_tutor_id",
                    "matched_subject_id",
                    "attendance_session_id",
                    "match_status",
                    "confidence_score",
                    "notes",
                    "manual_review_status",
                    "manual_reviewed_at",
                    "manual_reviewed_by",
                    "manual_review_notes",
                    "created_at",
                    "updated_at",
                ),
            )
            for evaluation in WhatsAppEvaluation.query.filter(
                or_(
                    WhatsAppEvaluation.matched_enrollment_id == enrollment_id,
                    WhatsAppEvaluation.attendance_session_id.in_(attendance_ids)
                    if attendance_ids
                    else False,
                )
            ).all()
        ],
        "legacy_student_invoices": legacy_invoices,
        "legacy_student_invoice_lines": list(
            {row["id"]: row for row in legacy_invoice_lines}.values()
        ),
    }


def _create_deleted_enrollment_record(
    enrollment: Enrollment,
    *,
    deleted_by_id: int | None = None,
    payload: dict | None = None,
) -> DeletedEnrollment:
    deleted_record = DeletedEnrollment(
        original_enrollment_id=enrollment.id,
        payload_json=payload or _enrollment_delete_snapshot(enrollment),
        deleted_by=deleted_by_id,
    )
    db.session.add(deleted_record)
    db.session.flush()
    return deleted_record


def _restore_deleted_enrollment_record(
    deleted_record: DeletedEnrollment,
    *,
    restored_by_id: int | None = None,
) -> Enrollment:
    if deleted_record.restored_at:
        raise ValueError("Enrollment ini sudah pernah direstore.")

    payload = deleted_record.payload_json or {}
    data = payload["enrollment"]
    enrollment = Enrollment(
        student_id=data["student_id"],
        subject_id=data["subject_id"],
        tutor_id=data["tutor_id"],
        curriculum_id=data["curriculum_id"],
        level_id=data["level_id"],
        grade=data.get("grade"),
        meeting_quota_per_month=data.get("meeting_quota_per_month") or 4,
        student_rate_per_meeting=data["student_rate_per_meeting"],
        tutor_rate_per_meeting=data["tutor_rate_per_meeting"],
        start_date=_parse_datetime(data.get("start_date")),
        end_date=_parse_datetime(data.get("end_date")),
        status=data.get("status") or "active",
        notes=data.get("notes"),
        is_active=data.get("is_active", True),
        whatsapp_group_id=data.get("whatsapp_group_id"),
        whatsapp_group_name=data.get("whatsapp_group_name"),
        whatsapp_group_memberships_json=data.get("whatsapp_group_memberships_json"),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )
    _restore_original_id_if_free(Enrollment, enrollment, data.get("id"))
    db.session.add(enrollment)
    db.session.flush()
    old_enrollment_id = data.get("id")
    attendance_id_map = {}

    for schedule_data in payload.get("schedules", []):
        schedule = EnrollmentSchedule(
            enrollment_id=enrollment.id,
            day_of_week=schedule_data["day_of_week"],
            day_name=schedule_data.get("day_name"),
            start_time=_parse_time(schedule_data.get("start_time")),
            end_time=_parse_time(schedule_data.get("end_time")),
            location=schedule_data.get("location"),
            is_active=schedule_data.get("is_active", True),
            created_at=_parse_datetime(schedule_data.get("created_at")),
            updated_at=_parse_datetime(schedule_data.get("updated_at")),
        )
        _restore_original_id_if_free(EnrollmentSchedule, schedule, schedule_data.get("id"))
        db.session.add(schedule)

    for item_data in payload.get("attendance_sessions", []):
        session_item = AttendanceSession(
            enrollment_id=enrollment.id,
            student_id=item_data["student_id"],
            tutor_id=item_data["tutor_id"],
            subject_id=item_data.get("subject_id"),
            session_date=_parse_date(item_data.get("session_date")),
            status=item_data.get("status") or "scheduled",
            student_present=item_data.get("student_present", False),
            tutor_present=item_data.get("tutor_present", False),
            tutor_fee_amount=item_data.get("tutor_fee_amount") or 0,
            notes=item_data.get("notes"),
            created_at=_parse_datetime(item_data.get("created_at")),
            updated_at=_parse_datetime(item_data.get("updated_at")),
        )
        old_id = item_data.get("id")
        _restore_original_id_if_free(AttendanceSession, session_item, old_id)
        db.session.add(session_item)
        db.session.flush()
        if old_id:
            attendance_id_map[old_id] = session_item.id

    for payment_data in payload.get("student_payments", []):
        if db.session.get(StudentPayment, payment_data["id"]):
            continue
        payment = StudentPayment(
            payment_date=_parse_datetime(payment_data.get("payment_date")),
            student_id=payment_data["student_id"],
            receipt_number=payment_data["receipt_number"],
            payment_method=payment_data["payment_method"],
            total_amount=payment_data["total_amount"],
            notes=payment_data.get("notes"),
            is_verified=payment_data.get("is_verified", False),
            verified_by=payment_data.get("verified_by"),
            verified_at=_parse_datetime(payment_data.get("verified_at")),
            created_at=_parse_datetime(payment_data.get("created_at")),
            updated_at=_parse_datetime(payment_data.get("updated_at")),
        )
        payment.id = payment_data["id"]
        db.session.add(payment)
    db.session.flush()

    for line_data in payload.get("student_payment_lines", []):
        if db.session.get(StudentPaymentLine, line_data["id"]):
            continue
        line = StudentPaymentLine(
            student_payment_id=line_data["student_payment_id"],
            enrollment_id=enrollment.id,
            service_month=_parse_date(line_data.get("service_month")),
            meeting_count=line_data["meeting_count"],
            student_rate_per_meeting=line_data["student_rate_per_meeting"],
            tutor_rate_per_meeting=line_data["tutor_rate_per_meeting"],
            nominal_amount=line_data["nominal_amount"],
            tutor_payable_amount=line_data["tutor_payable_amount"],
            margin_amount=line_data["margin_amount"],
            notes=line_data.get("notes"),
            created_at=_parse_datetime(line_data.get("created_at")),
            updated_at=_parse_datetime(line_data.get("updated_at")),
        )
        line.id = line_data["id"]
        db.session.add(line)

    for link_data in payload.get("tutor_meet_links", []):
        if db.session.get(TutorMeetLink, link_data["id"]):
            continue
        link = TutorMeetLink(
            enrollment_id=enrollment.id,
            tutor_id=link_data["tutor_id"],
            student_id=link_data["student_id"],
            subject_id=link_data.get("subject_id"),
            token=link_data["token"],
            room=link_data["room"],
            join_url=link_data["join_url"],
            jitsi_url=link_data.get("jitsi_url"),
            status=link_data.get("status") or "active",
            max_joins=link_data.get("max_joins") or 1,
            source=link_data.get("source"),
            valid_from=_parse_datetime(link_data.get("valid_from")),
            expires_at=_parse_datetime(link_data.get("expires_at")),
            created_at=_parse_datetime(link_data.get("created_at")),
            updated_at=_parse_datetime(link_data.get("updated_at")),
        )
        link.id = link_data["id"]
        db.session.add(link)

    for evaluation_data in payload.get("whatsapp_evaluations", []):
        if db.session.get(WhatsAppEvaluation, evaluation_data["id"]):
            continue
        evaluation = WhatsAppEvaluation(
            message_id=evaluation_data["message_id"],
            group_id=evaluation_data["group_id"],
            student_name=evaluation_data.get("student_name"),
            tutor_name=evaluation_data.get("tutor_name"),
            subject_name=evaluation_data.get("subject_name"),
            focus_topic=evaluation_data.get("focus_topic"),
            summary_text=evaluation_data.get("summary_text"),
            source_language=evaluation_data.get("source_language"),
            reported_lesson_date=_parse_date(evaluation_data.get("reported_lesson_date")),
            reported_time_label=evaluation_data.get("reported_time_label"),
            attendance_date=_parse_date(evaluation_data.get("attendance_date")),
            matched_student_id=evaluation_data.get("matched_student_id"),
            matched_tutor_id=evaluation_data.get("matched_tutor_id"),
            matched_subject_id=evaluation_data.get("matched_subject_id"),
            matched_enrollment_id=enrollment.id,
            attendance_session_id=attendance_id_map.get(
                evaluation_data.get("attendance_session_id"),
                evaluation_data.get("attendance_session_id"),
            ),
            match_status=evaluation_data.get("match_status"),
            confidence_score=evaluation_data.get("confidence_score") or 0,
            notes=evaluation_data.get("notes"),
            manual_review_status=evaluation_data.get("manual_review_status") or "pending",
            manual_reviewed_at=_parse_datetime(evaluation_data.get("manual_reviewed_at")),
            manual_reviewed_by=evaluation_data.get("manual_reviewed_by"),
            manual_review_notes=evaluation_data.get("manual_review_notes"),
            created_at=_parse_datetime(evaluation_data.get("created_at")),
            updated_at=_parse_datetime(evaluation_data.get("updated_at")),
        )
        evaluation.id = evaluation_data["id"]
        db.session.add(evaluation)

    _insert_raw_rows("student_invoices", payload.get("legacy_student_invoices", []))
    _insert_raw_rows(
        "student_invoice_lines",
        payload.get("legacy_student_invoice_lines", []),
    )

    deleted_record.restored_enrollment_id = enrollment.id
    deleted_record.restored_by = restored_by_id
    deleted_record.restored_at = datetime.utcnow()
    db.session.flush()
    return enrollment


def _get_deleted_enrollment_by_ref_or_404(deleted_ref: str):
    try:
        deleted_id = decode_public_id(deleted_ref, "deleted_enrollment")
    except ValueError:
        abort(404)
    return DeletedEnrollment.query.get_or_404(deleted_id)


def _delete_legacy_invoice_rows_for_enrollment(enrollment_id: int) -> None:
    table_names = set(inspect(db.engine).get_table_names())
    invoice_ids = []
    if "student_invoices" in table_names:
        invoice_ids = [
            invoice_id
            for (invoice_id,) in db.session.execute(
                text(
                    """
                    SELECT id
                    FROM student_invoices
                    WHERE enrollment_id = :enrollment_id
                    """
                ),
                {"enrollment_id": enrollment_id},
            ).all()
        ]
    if "student_invoice_lines" in table_names:
        db.session.execute(
            text("DELETE FROM student_invoice_lines WHERE enrollment_id = :enrollment_id"),
            {"enrollment_id": enrollment_id},
        )
        if invoice_ids:
            db.session.execute(
                text(
                    "DELETE FROM student_invoice_lines WHERE invoice_id IN :invoice_ids"
                ).bindparams(bindparam("invoice_ids", expanding=True)),
                {"invoice_ids": invoice_ids},
            )
    if "student_invoices" in table_names:
        db.session.execute(
            text("DELETE FROM student_invoices WHERE enrollment_id = :enrollment_id"),
            {"enrollment_id": enrollment_id},
        )


def _delete_enrollment_dependencies(enrollment: Enrollment) -> None:
    enrollment_id = enrollment.id
    attendance_session_ids = [
        session_id
        for (session_id,) in AttendanceSession.query.with_entities(AttendanceSession.id)
        .filter_by(enrollment_id=enrollment_id)
        .all()
    ]

    attendance_session_id_set = set(attendance_session_ids)
    for loaded_object in list(db.session.identity_map.values()):
        if not isinstance(loaded_object, WhatsAppEvaluation):
            continue
        if (
            loaded_object.matched_enrollment_id == enrollment_id
            or loaded_object.attendance_session_id in attendance_session_id_set
        ):
            db.session.delete(loaded_object)
    db.session.flush()

    db.session.execute(
        text(
            """
            DELETE FROM whatsapp_evaluations
            WHERE matched_enrollment_id = :enrollment_id
            """
        ),
        {"enrollment_id": enrollment_id},
    )
    if attendance_session_ids:
        db.session.execute(
            text(
                """
                DELETE FROM whatsapp_evaluations
                WHERE attendance_session_id IN :attendance_session_ids
                """
            ).bindparams(bindparam("attendance_session_ids", expanding=True)),
            {"attendance_session_ids": attendance_session_ids},
        )
    for meet_link in list(enrollment.tutor_meet_links):
        db.session.delete(meet_link)
    _delete_legacy_invoice_rows_for_enrollment(enrollment_id)
    db.session.flush()


@enrollments_bp.route("/", methods=["GET"])
@login_required
def list_enrollments():
    """List all enrollments"""
    if request.args.get("reset") == "1":
        flask_session.pop(ENROLLMENT_LIST_STATE_KEY, None)
        return redirect(
            url_for("enrollments.list_enrollments", sort=DEFAULT_ENROLLMENT_SORT)
        )

    if not request.args and flask_session.get(ENROLLMENT_LIST_STATE_KEY):
        saved_state = dict(flask_session[ENROLLMENT_LIST_STATE_KEY])
        if saved_state.get("v") != ENROLLMENT_LIST_STATE_VERSION:
            saved_state["sort"] = DEFAULT_ENROLLMENT_SORT
            saved_state["v"] = ENROLLMENT_LIST_STATE_VERSION
            flask_session[ENROLLMENT_LIST_STATE_KEY] = saved_state
        return redirect(
            url_for(
                "enrollments.list_enrollments",
                **_public_enrollment_list_state(saved_state),
            )
        )

    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    search_term = request.args.get("q", "", type=str)
    status = request.args.get("status", "", type=str)
    sort_by = request.args.get("sort", DEFAULT_ENROLLMENT_SORT, type=str)
    if sort_by not in ENROLLMENT_SORT_OPTIONS:
        sort_by = DEFAULT_ENROLLMENT_SORT
    _store_enrollment_list_state(page, per_page, search_term, status, sort_by)
    enrollments = _build_enrollment_list_query(search_term, status, sort_by).paginate(
        page=page, per_page=per_page
    )
    deleted_enrollment_count = DeletedEnrollment.query.filter(
        DeletedEnrollment.restored_at.is_(None)
    ).count()
    return render_template(
        "enrollments/list.html",
        enrollments=enrollments,
        search_term=search_term,
        selected_status=status,
        selected_sort=sort_by,
        deleted_enrollment_count=deleted_enrollment_count,
    )


@enrollments_bp.route("/scan-missing-whatsapp-groups", methods=["POST"])
@login_required
def scan_missing_whatsapp_groups():
    """Fill missing enrollment WhatsApp groups from validated student/tutor data."""
    search_term = request.form.get("q", "", type=str)
    status = request.form.get("status", "", type=str)
    page = request.form.get("page", 1, type=int)
    per_page = request.form.get("per_page", get_per_page(), type=int)
    sort_by = request.form.get("sort", DEFAULT_ENROLLMENT_SORT, type=str)
    if sort_by not in ENROLLMENT_SORT_OPTIONS:
        sort_by = DEFAULT_ENROLLMENT_SORT
    redirect_kwargs = _public_enrollment_list_state(
        _store_enrollment_list_state(
            page, per_page, search_term, status, sort_by
        )
    )
    try:
        summary = _scan_missing_enrollment_whatsapp_groups()
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Scan Group WA enrollment gagal: {exc}", "danger")
        return redirect(url_for("enrollments.list_enrollments", **redirect_kwargs))

    if summary["processed"] == 0:
        flash("Semua enrollment aktif sudah memiliki Group WA.", "info")
    else:
        flash(
            (
                "Scan Group WA enrollment selesai: "
                f"{summary['processed']} enrollment kosong diproses, "
                f"{summary['matched']} berhasil diisi, "
                f"{summary['unmatched']} belum match."
            ),
            "success" if summary["matched"] else "warning",
        )
    return redirect(url_for("enrollments.list_enrollments", **redirect_kwargs))


@enrollments_bp.route("/trash", methods=["GET"])
@login_required
def enrollment_trash():
    """List deleted enrollments that can still be restored."""
    page = request.args.get("page", 1, type=int)
    deleted_enrollments = (
        DeletedEnrollment.query.filter(DeletedEnrollment.restored_at.is_(None))
        .order_by(DeletedEnrollment.deleted_at.desc(), DeletedEnrollment.id.desc())
        .paginate(page=page, per_page=25)
    )
    return render_template(
        "enrollments/trash.html",
        deleted_enrollments=deleted_enrollments,
    )


@enrollments_bp.route("/trash/<string:deleted_ref>/restore", methods=["POST"])
@login_required
def restore_deleted_enrollment(deleted_ref):
    """Restore one deleted enrollment and its deleted dependent data."""
    deleted_record = _get_deleted_enrollment_by_ref_or_404(deleted_ref)
    try:
        enrollment = _restore_deleted_enrollment_record(
            deleted_record,
            restored_by_id=getattr(current_user, "id", None),
        )
        db.session.commit()
        flash(
            (
                "Enrollment berhasil direstore beserta presensi dan pembayaran "
                f"untuk {enrollment.student.name} - {enrollment.subject.name}."
            ),
            "success",
        )
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    except SQLAlchemyError as exc:
        db.session.rollback()
        flash(f"Restore enrollment gagal: {exc}", "danger")
    return redirect(url_for("enrollments.enrollment_trash"))


@enrollments_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_enrollment():
    """Add new enrollment"""
    form = EnrollmentForm()

    if form.validate_on_submit():
        try:
            enrollment = Enrollment(
                student_id=form.student_id.data,
                subject_id=form.subject_id.data,
                tutor_id=form.tutor_id.data,
                curriculum_id=form.curriculum_id.data,
                level_id=form.level_id.data,
                grade=form.grade.data,
                meeting_quota_per_month=form.meeting_quota_per_month.data,
                student_rate_per_meeting=form.student_rate_per_meeting.data,
                tutor_rate_per_meeting=form.tutor_rate_per_meeting.data,
                status="active",
            )
            if form.whatsapp_group_db_id.data:
                _apply_selected_whatsapp_group(enrollment, form.whatsapp_group_db_id.data)
            else:
                WhatsAppIngestService.sync_enrollment_whatsapp_group(enrollment)
            db.session.add(enrollment)
            db.session.commit()
            flash("Enrollment berhasil ditambahkan", "success")
            return redirect(url_for("enrollments.list_enrollments"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")

    return render_template(
        "enrollments/form.html",
        form=form,
        title="Tambah Enrollment",
        **_build_pricing_public_id_maps(),
    )


@enrollments_bp.route("/<string:enrollment_ref>", methods=["GET"])
@login_required
def enrollment_detail(enrollment_ref):
    """Get enrollment detail"""
    enrollment = _get_enrollment_by_ref_or_404(enrollment_ref)
    recent_sessions = (
        AttendanceSession.query.filter_by(enrollment_id=enrollment.id)
        .order_by(AttendanceSession.session_date.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "enrollments/detail.html",
        enrollment=enrollment,
        recent_sessions=recent_sessions,
    )


@enrollments_bp.route("/<string:enrollment_ref>/edit", methods=["GET", "POST"])
@login_required
def edit_enrollment(enrollment_ref):
    """Edit enrollment"""
    enrollment = _get_enrollment_by_ref_or_404(enrollment_ref)
    form = EnrollmentForm()

    if form.validate_on_submit():
        try:
            enrollment.student_id = form.student_id.data
            enrollment.subject_id = form.subject_id.data
            enrollment.tutor_id = form.tutor_id.data
            enrollment.curriculum_id = form.curriculum_id.data
            enrollment.level_id = form.level_id.data
            enrollment.grade = form.grade.data
            enrollment.meeting_quota_per_month = form.meeting_quota_per_month.data
            enrollment.student_rate_per_meeting = form.student_rate_per_meeting.data
            enrollment.tutor_rate_per_meeting = form.tutor_rate_per_meeting.data
            if form.whatsapp_group_db_id.data:
                _apply_selected_whatsapp_group(enrollment, form.whatsapp_group_db_id.data)
            else:
                WhatsAppIngestService.sync_enrollment_whatsapp_group(enrollment)
            db.session.commit()
            flash("Enrollment berhasil diupdate", "success")
            return redirect(
                url_for(
                    "enrollments.enrollment_detail",
                    enrollment_ref=enrollment.public_id,
                )
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")
    elif request.method == "GET":
        form.student_id.data = enrollment.student_id
        form.subject_id.data = enrollment.subject_id
        form.tutor_id.data = enrollment.tutor_id
        form.curriculum_id.data = enrollment.curriculum_id
        form.level_id.data = enrollment.level_id
        form.grade.data = enrollment.grade
        form.meeting_quota_per_month.data = enrollment.meeting_quota_per_month
        form.student_rate_per_meeting.data = _normalize_rate_form_value(
            enrollment.student_rate_per_meeting
        )
        form.tutor_rate_per_meeting.data = _normalize_rate_form_value(
            enrollment.tutor_rate_per_meeting
        )
        form.whatsapp_group_db_id.data = next(
            (
                group.id
                for group in WhatsAppGroup.query.all()
                if group.whatsapp_group_id == enrollment.whatsapp_group_id
            ),
            0,
        )

    return render_template(
        "enrollments/form.html",
        form=form,
        enrollment=enrollment,
        title="Edit Enrollment",
        **_build_pricing_public_id_maps(),
    )


@enrollments_bp.route("/<string:enrollment_ref>/delete", methods=["POST"])
@login_required
def delete_enrollment(enrollment_ref):
    """Delete enrollment"""
    enrollment = _get_enrollment_by_ref_or_404(enrollment_ref)
    redirect_kwargs = _list_redirect_kwargs_from_request()
    try:
        delete_snapshot = _enrollment_delete_snapshot(enrollment)
        _delete_enrollment_dependencies(enrollment)
        _create_deleted_enrollment_record(
            enrollment,
            deleted_by_id=getattr(current_user, "id", None),
            payload=delete_snapshot,
        )
        db.session.delete(enrollment)
        db.session.commit()
        flash("Enrollment dipindahkan ke tempat sampah dan bisa direstore.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash(
            "Enrollment gagal dihapus karena masih terhubung dengan data lain. "
            "Silakan coba lagi atau hubungi admin.",
            "danger",
        )

    return redirect(url_for("enrollments.list_enrollments", **redirect_kwargs))
