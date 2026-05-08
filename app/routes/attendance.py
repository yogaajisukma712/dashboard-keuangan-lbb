"""
Attendance routes for Dashboard Keuangan LBB Super Smart
Handles presensi tutor and sesi les
"""

import csv
import io
from calendar import monthrange
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import db
from app.forms import AttendanceSessionForm, BulkAttendanceForm
from app.models import (
    AttendancePeriodLock,
    AttendanceSession,
    Enrollment,
    EnrollmentSchedule,
    Student,
    Tutor,
    WhatsAppEvaluation,
)
from app.services import AttendanceService
from app.services.whatsapp_ingest_service import WhatsAppIngestService
from app.utils import DEFAULT_PER_PAGE, PER_PAGE_OPTIONS, decode_public_id

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")

attendance_service = AttendanceService()
INDONESIAN_MONTH_NAMES = [
    "",
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
]
INDONESIAN_DAY_NAMES = {
    "Monday": "Senin",
    "Tuesday": "Selasa",
    "Wednesday": "Rabu",
    "Thursday": "Kamis",
    "Friday": "Jumat",
    "Saturday": "Sabtu",
    "Sunday": "Minggu",
}
INDONESIAN_WEEKDAY_NAMES = [
    "Senin",
    "Selasa",
    "Rabu",
    "Kamis",
    "Jumat",
    "Sabtu",
    "Minggu",
]
WHATSAPP_REVIEW_START_DATE = date(2026, 4, 1)
WHATSAPP_REVIEW_STATUSES = {"pending", "valid", "invalid"}
ATTENDANCE_LIST_STATE_SESSION_KEY = "attendance_list_state"
ATTENDANCE_SORT_OPTIONS = {
    "date_desc",
    "date_asc",
    "student_asc",
    "student_desc",
    "student_asc_date_desc",
    "student_asc_date_asc",
    "student_desc_date_desc",
    "student_desc_date_asc",
}


def _get_session_by_ref_or_404(session_ref):
    """Resolve opaque attendance session ref to model instance."""
    try:
        session_id = decode_public_id(session_ref, "attendance_session")
    except ValueError:
        abort(404)
    return AttendanceSession.query.get_or_404(session_id)


def _normalize_calendar_period(month: int | None, year: int | None):
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year

    if target_month < 1 or target_month > 12:
        target_month = today.month
    if target_year < 2000 or target_year > 2100:
        target_year = today.year
    return target_month, target_year


def _decode_optional_query_ref(param_name: str, kind: str) -> int | None:
    return _decode_optional_ref_value(request.args.get(param_name), kind)


def _decode_optional_ref_value(value: str | None, kind: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return decode_public_id(value, kind)
    except ValueError:
        return None


def _decode_optional_ref_values(values, kind: str) -> list[int]:
    decoded = []
    for value in values or []:
        item_id = _decode_optional_ref_value(value, kind)
        if item_id and item_id not in decoded:
            decoded.append(item_id)
    return decoded


def _get_filter_values(source, key: str) -> list[str]:
    if hasattr(source, "getlist"):
        return [value for value in source.getlist(key) if value]
    value = source.get(key) if source else None
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def _parse_iso_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except (TypeError, ValueError):
        return None


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_attendance_per_page(stored_state: dict | None = None) -> int:
    stored_state = stored_state or {}
    raw_value = request.args.get("per_page") or stored_state.get("per_page")
    value = _safe_int(raw_value, DEFAULT_PER_PAGE)
    return value if value in PER_PAGE_OPTIONS else DEFAULT_PER_PAGE


def _build_lesson_calendar(
    month: int,
    year: int,
    tutor_id: int | None = None,
    student_id: int | None = None,
):
    target_month, target_year = _normalize_calendar_period(month, year)
    period_start = date(target_year, target_month, 1)
    period_end = date(target_year, target_month, monthrange(target_year, target_month)[1])
    attendance_query = AttendanceSession.query.options(
        joinedload(AttendanceSession.enrollment).joinedload(Enrollment.student),
        joinedload(AttendanceSession.enrollment).joinedload(Enrollment.tutor),
        joinedload(AttendanceSession.enrollment).joinedload(Enrollment.subject),
        joinedload(AttendanceSession.tutor),
    ).filter(
        AttendanceSession.session_date.between(period_start, period_end)
    )
    if tutor_id:
        attendance_query = attendance_query.filter(AttendanceSession.tutor_id == tutor_id)
    if student_id:
        attendance_query = attendance_query.filter(AttendanceSession.student_id == student_id)
    attendance_sessions = attendance_query.order_by(
        AttendanceSession.session_date.asc(),
        AttendanceSession.id.asc(),
    ).all()

    enrollment_ids = {
        session.enrollment_id for session in attendance_sessions if session.enrollment_id
    }
    schedule_map = {}
    if enrollment_ids:
        schedules = (
            EnrollmentSchedule.query.filter(
                EnrollmentSchedule.enrollment_id.in_(enrollment_ids),
                EnrollmentSchedule.is_active.is_(True),
            )
            .order_by(
                EnrollmentSchedule.enrollment_id.asc(),
                EnrollmentSchedule.day_of_week.asc(),
                EnrollmentSchedule.start_time.asc(),
            )
            .all()
        )
        for schedule in schedules:
            schedule_map.setdefault(schedule.enrollment_id, {}).setdefault(
                schedule.day_of_week, []
            ).append(schedule)

    items_by_date = {}
    tutor_ids = set()
    student_ids = set()
    for attendance_session in attendance_sessions:
        enrollment = attendance_session.enrollment
        if enrollment is None:
            continue
        tutor_ids.add(attendance_session.tutor_id)
        student_ids.add(attendance_session.student_id)
        matching_schedule = None
        for schedule in schedule_map.get(enrollment.id, {}).get(
            attendance_session.session_date.weekday(), []
        ):
            matching_schedule = schedule
            break
        schedule_label = "Sesi les"
        location = ""
        if matching_schedule is not None:
            schedule_label = f"{matching_schedule.start_time.strftime('%H:%M')}"
            if matching_schedule.end_time:
                schedule_label += f" - {matching_schedule.end_time.strftime('%H:%M')}"
            location = matching_schedule.location or ""
        tutor_name = (
            attendance_session.tutor.name
            if attendance_session.tutor
            else enrollment.tutor.name
            if enrollment.tutor
            else "-"
        )
        student_name = (
            attendance_session.student.name
            if attendance_session.student
            else enrollment.student.name
            if enrollment.student
            else "-"
        )
        student_short_name = " ".join(student_name.split()[:2]) if student_name else "-"
        subject_name = (
            attendance_session.subject.name
            if attendance_session.subject
            else enrollment.subject.name
            if enrollment.subject
            else "-"
        )
        chip_label = " - ".join(
            [schedule_label, tutor_name, subject_name, student_name]
        )
        items_by_date.setdefault(attendance_session.session_date, []).append(
            {
                "date": attendance_session.session_date,
                "tutor_name": tutor_name,
                "student_name": student_name,
                "student_short_name": student_short_name,
                "subject_name": subject_name,
                "grade": enrollment.grade or "-",
                "schedule_label": schedule_label,
                "chip_label": chip_label,
                "location": location,
                "enrollment_ref": enrollment.public_id,
                "attendance_status": attendance_session.status,
                "attendance_ref": attendance_session.public_id,
                "whatsapp_group_name": enrollment.whatsapp_group_name or "",
            }
        )

    for lesson_items in items_by_date.values():
        lesson_items.sort(
            key=lambda item: (
                item["schedule_label"],
                item["tutor_name"].lower(),
                item["student_name"].lower(),
            )
        )

    grid_start = period_start - timedelta(days=period_start.weekday())
    grid_end = period_end + timedelta(days=6 - period_end.weekday())
    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        week_days = []
        for _ in range(7):
            week_days.append(
                {
                    "date": cursor,
                    "in_month": cursor.month == target_month,
                    "is_today": cursor == date.today(),
                    "items": items_by_date.get(cursor, []),
                }
            )
            cursor += timedelta(days=1)
        weeks.append(week_days)

    previous_month = target_month - 1 if target_month > 1 else 12
    previous_year = target_year if target_month > 1 else target_year - 1
    next_month = target_month + 1 if target_month < 12 else 1
    next_year = target_year if target_month < 12 else target_year + 1

    return {
        "month": target_month,
        "year": target_year,
        "title": f"{INDONESIAN_MONTH_NAMES[target_month]} {target_year}",
        "weekday_names": INDONESIAN_WEEKDAY_NAMES,
        "weeks": weeks,
        "lesson_count": len(attendance_sessions),
        "scheduled_day_count": len(items_by_date),
        "scheduled_enrollment_count": len(enrollment_ids),
        "tutor_count": len(tutor_ids),
        "student_count": len(student_ids),
        "previous_month": previous_month,
        "previous_year": previous_year,
        "next_month": next_month,
        "next_year": next_year,
    }


def _build_attendance_list_query(
    enrollment_id: int | None = None,
    student_id: int | None = None,
    tutor_id: int | None = None,
    tutor_ids: list[int] | None = None,
    month: int | None = None,
    year: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    query = AttendanceSession.query

    if enrollment_id:
        query = query.filter_by(enrollment_id=enrollment_id)
    if student_id:
        query = query.filter(AttendanceSession.student_id == student_id)
    if tutor_ids:
        query = query.filter(AttendanceSession.tutor_id.in_(tutor_ids))
    elif tutor_id:
        query = query.filter_by(tutor_id=tutor_id)
    if month:
        query = query.filter(db.extract("month", AttendanceSession.session_date) == month)
    if year:
        query = query.filter(db.extract("year", AttendanceSession.session_date) == year)
    if status:
        query = query.filter_by(status=status)
    if date_from:
        query = query.filter(AttendanceSession.session_date >= date_from)
    if date_to:
        query = query.filter(AttendanceSession.session_date <= date_to)
    return query


def _apply_attendance_list_sort(query, sort_by: str | None):
    if sort_by not in ATTENDANCE_SORT_OPTIONS:
        sort_by = "date_desc"

    if sort_by in {"student_asc", "student_asc_date_desc", "student_asc_date_asc"}:
        date_order = (
            AttendanceSession.session_date.asc()
            if sort_by == "student_asc_date_asc"
            else AttendanceSession.session_date.desc()
        )
        id_order = (
            AttendanceSession.id.asc()
            if sort_by == "student_asc_date_asc"
            else AttendanceSession.id.desc()
        )
        return (
            query.join(Student, AttendanceSession.student_id == Student.id)
            .order_by(
                Student.name.asc(),
                date_order,
                id_order,
            )
        )
    if sort_by in {"student_desc", "student_desc_date_desc", "student_desc_date_asc"}:
        date_order = (
            AttendanceSession.session_date.asc()
            if sort_by == "student_desc_date_asc"
            else AttendanceSession.session_date.desc()
        )
        id_order = (
            AttendanceSession.id.asc()
            if sort_by == "student_desc_date_asc"
            else AttendanceSession.id.desc()
        )
        return (
            query.join(Student, AttendanceSession.student_id == Student.id)
            .order_by(
                Student.name.desc(),
                date_order,
                id_order,
            )
        )
    if sort_by == "date_asc":
        return query.order_by(
            AttendanceSession.session_date.asc(),
            AttendanceSession.id.asc(),
        )
    return query.order_by(
        AttendanceSession.session_date.desc(),
        AttendanceSession.id.desc(),
    )


def _attendance_csv_row(session_item: AttendanceSession, row_number: int) -> list:
    enrollment = session_item.enrollment
    student = session_item.student or (enrollment.student if enrollment else None)
    tutor = session_item.tutor or (enrollment.tutor if enrollment else None)
    subject = session_item.subject or (enrollment.subject if enrollment else None)
    curriculum = enrollment.curriculum if enrollment else None
    level = enrollment.level if enrollment else None
    session_date = session_item.session_date
    day_name = INDONESIAN_DAY_NAMES.get(
        session_date.strftime("%A"),
        session_date.strftime("%A"),
    )
    nominal = int(session_item.tutor_fee_amount or 0)

    return [
        row_number,
        session_date.strftime("%d/%m/%Y"),
        day_name,
        tutor.name if tutor else "",
        student.name if student else "",
        curriculum.name if curriculum else "",
        level.name if level else "",
        subject.name if subject else "",
        nominal,
    ]


def _attendance_redirect_filters():
    stored_state = session.get(ATTENDANCE_LIST_STATE_SESSION_KEY) or {}
    selected_sort = (
        request.args.get("sort")
        or request.form.get("sort")
        or stored_state.get("sort")
        or "date_desc"
    )
    if selected_sort not in ATTENDANCE_SORT_OPTIONS:
        selected_sort = "date_desc"
    return {
        "page": request.args.get("page", type=int) or stored_state.get("page") or 1,
        "per_page": request.args.get("per_page") or stored_state.get("per_page") or "",
        "enrollment_ref": request.args.get("enrollment_ref") or stored_state.get("enrollment_ref") or "",
        "student_ref": request.args.get("student_ref") or stored_state.get("student_ref") or "",
        "tutor_ref": request.args.getlist("tutor_ref")
        or stored_state.get("tutor_ref")
        or "",
        "month": request.args.get("month", type=int) or stored_state.get("month") or "",
        "year": request.args.get("year", type=int) or stored_state.get("year") or "",
        "date_from": request.args.get("date_from") or stored_state.get("date_from") or "",
        "date_to": request.args.get("date_to") or stored_state.get("date_to") or "",
        "sort": selected_sort,
    }


def _compact_attendance_query_state() -> dict[str, str]:
    stored_state = session.get(ATTENDANCE_LIST_STATE_SESSION_KEY) or {}
    keys = (
        "page",
        "per_page",
        "enrollment_ref",
        "student_ref",
        "tutor_ref",
        "month",
        "year",
        "date_from",
        "date_to",
        "sort",
    )
    state = {}
    for key in keys:
        values = request.args.getlist(key)
        values = [value.strip() for value in values if value and value.strip()]
        if values:
            state[key] = values if len(values) > 1 else values[0]
    if "per_page" not in state and stored_state.get("per_page"):
        state["per_page"] = stored_state["per_page"]
    return state


def _restore_attendance_list_state_if_needed():
    if request.args.get("reset_filters") == "1":
        session.pop(ATTENDANCE_LIST_STATE_SESSION_KEY, None)
        return redirect(url_for("attendance.list_attendance"))
    return None


def _remember_attendance_list_state():
    state = _compact_attendance_query_state()
    if state:
        session[ATTENDANCE_LIST_STATE_SESSION_KEY] = state


def _sync_linked_whatsapp_evaluations(session: AttendanceSession):
    linked_evaluations = WhatsAppEvaluation.query.filter_by(
        attendance_session_id=session.id
    ).all()
    for evaluation in linked_evaluations:
        evaluation.matched_student_id = session.student_id
        evaluation.matched_tutor_id = session.tutor_id
        evaluation.matched_subject_id = session.subject_id
        evaluation.matched_enrollment_id = session.enrollment_id
        evaluation.match_status = "attendance-linked"
        manual_note = (
            f"Presensi dikoreksi manual ke tutor #{session.tutor_id} "
            f"dan enrollment #{session.enrollment_id}."
        )
        if not evaluation.notes:
            evaluation.notes = manual_note
        elif manual_note not in evaluation.notes:
            evaluation.notes = f"{evaluation.notes}\n{manual_note}"


def _whatsapp_review_requires_manual_check(session: AttendanceSession) -> bool:
    return bool(session.session_date and session.session_date >= WHATSAPP_REVIEW_START_DATE)


def _build_whatsapp_review_map(sessions: list[AttendanceSession]) -> dict[int, dict]:
    session_ids = [session.id for session in sessions if session.id]
    if not session_ids:
        return {}

    evaluations = (
        WhatsAppEvaluation.query.options(
            joinedload(WhatsAppEvaluation.message),
            joinedload(WhatsAppEvaluation.group),
        )
        .filter(WhatsAppEvaluation.attendance_session_id.in_(session_ids))
        .order_by(WhatsAppEvaluation.id.asc())
        .all()
    )
    evaluations_by_session = {}
    for evaluation in evaluations:
        evaluations_by_session.setdefault(evaluation.attendance_session_id, []).append(
            evaluation
        )

    review_map = {}
    for session in sessions:
        linked_evaluations = evaluations_by_session.get(session.id, [])
        if not linked_evaluations:
            continue
        statuses = {
            (evaluation.manual_review_status or "pending")
            for evaluation in linked_evaluations
        }
        if "invalid" in statuses:
            aggregate_status = "invalid"
        elif statuses == {"valid"}:
            aggregate_status = "valid"
        elif len(statuses) > 1:
            aggregate_status = "mixed"
        else:
            aggregate_status = "pending"
        latest_reviewed_at = max(
            (
                evaluation.manual_reviewed_at
                for evaluation in linked_evaluations
                if evaluation.manual_reviewed_at
            ),
            default=None,
        )
        review_map[session.id] = {
            "status": aggregate_status,
            "count": len(linked_evaluations),
            "requires_review": _whatsapp_review_requires_manual_check(session),
            "latest_reviewed_at": latest_reviewed_at,
            "group_names": sorted(
                {
                    evaluation.group.name
                    for evaluation in linked_evaluations
                    if evaluation.group and evaluation.group.name
                }
            ),
        }
    return review_map


def _set_whatsapp_attendance_manual_review(
    session: AttendanceSession,
    status: str,
    reviewer_id: int | None = None,
    notes: str | None = None,
) -> int:
    if status not in WHATSAPP_REVIEW_STATUSES:
        raise ValueError("Status validasi manual WhatsApp tidak valid.")
    if not _whatsapp_review_requires_manual_check(session):
        return 0

    linked_evaluations = WhatsAppEvaluation.query.filter_by(
        attendance_session_id=session.id
    ).all()
    reviewed_at = datetime.utcnow() if status != "pending" else None
    normalized_notes = (notes or "").strip() or None
    for evaluation in linked_evaluations:
        evaluation.manual_review_status = status
        evaluation.manual_reviewed_at = reviewed_at
        evaluation.manual_reviewed_by = reviewer_id if status != "pending" else None
        evaluation.manual_review_notes = normalized_notes if status != "pending" else None
        evaluation.updated_at = datetime.utcnow()
    return len(linked_evaluations)


def _wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )


def _whatsapp_review_response_payload(
    review_status: str,
    updated_count: int,
    message: str,
) -> dict:
    status_meta = {
        "valid": ("success", "bi-shield-check", "Sudah benar"),
        "invalid": ("warning", "bi-exclamation-triangle", "Perlu koreksi"),
        "pending": ("secondary", "bi-hourglass-split", "Belum crosscheck"),
    }
    badge_class, icon_class, label = status_meta.get(
        review_status,
        status_meta["pending"],
    )
    return {
        "ok": True,
        "status": review_status,
        "updated_count": updated_count,
        "message": message,
        "badge_class": badge_class,
        "icon_class": icon_class,
        "label": label,
        "reviewed_at": (
            datetime.utcnow().strftime("%d %b %Y %H:%M")
            if review_status != "pending" and updated_count
            else ""
        ),
    }


def _unlink_whatsapp_evaluations_before_attendance_delete(
    session: AttendanceSession,
) -> int:
    linked_evaluations = WhatsAppEvaluation.query.filter_by(
        attendance_session_id=session.id
    ).all()
    manual_note = (
        f"Presensi terkait dihapus manual pada {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}."
    )
    for evaluation in linked_evaluations:
        evaluation.attendance_session_id = None
        evaluation.match_status = "manual-unlinked"
        if not evaluation.notes:
            evaluation.notes = manual_note
        elif manual_note not in evaluation.notes:
            evaluation.notes = f"{evaluation.notes}\n{manual_note}"
        evaluation.updated_at = datetime.utcnow()
    return len(linked_evaluations)


def _build_tutor_enrollment_map(enrollments: list[Enrollment]) -> dict[int, int]:
    mapping = {}
    for enrollment in enrollments:
        if enrollment.tutor_id:
            mapping[enrollment.id] = enrollment.tutor_id
    return mapping


def _build_attendance_year_options() -> list[int]:
    current_year = date.today().year
    years = {current_year}
    attendance_year_rows = db.session.query(
        db.extract("year", AttendanceSession.session_date)
    ).all()
    evaluation_year_rows = db.session.query(
        db.extract("year", WhatsAppEvaluation.attendance_date)
    ).all()
    for row in [*attendance_year_rows, *evaluation_year_rows]:
        value = row[0] if row else None
        if value is None:
            continue
        years.add(int(value))
    return sorted(years, reverse=True)


def _get_attendance_period_lock(month: int | None, year: int | None):
    if not month or not year:
        return None
    return AttendancePeriodLock.query.filter_by(month=month, year=year).first()


def _build_attendance_period_lock_options(year_options: list[int], selected_month: int, selected_year: int):
    years = list(dict.fromkeys([selected_year, *year_options]))
    existing_locks = AttendancePeriodLock.query.filter(
        AttendancePeriodLock.year.in_(years)
    ).all()
    locked_keys = {f"{lock.year:04d}-{lock.month:02d}" for lock in existing_locks}
    options = []
    for year in years:
        options.append(
            {
                "year": year,
                "months": [
                    {
                        "month": month,
                        "label": INDONESIAN_MONTH_NAMES[month],
                        "value": f"{year:04d}-{month:02d}",
                        "locked": f"{year:04d}-{month:02d}" in locked_keys,
                        "is_current": month == selected_month and year == selected_year,
                    }
                    for month in range(1, 13)
                ],
            }
        )
    return options, locked_keys


def _get_attendance_lock_for_date(session_date: date | None):
    if not session_date:
        return None
    return _get_attendance_period_lock(session_date.month, session_date.year)


def _attendance_locked_message(session_date: date) -> str:
    return (
        f"Presensi {INDONESIAN_MONTH_NAMES[session_date.month]} {session_date.year} "
        "sedang dikunci. Buka kunci dulu untuk menambah, mengubah, atau menghapus presensi."
    )


def _ensure_attendance_date_unlocked(session_date: date):
    if _get_attendance_lock_for_date(session_date):
        raise ValueError(_attendance_locked_message(session_date))


@attendance_bp.route("/", methods=["GET"])
@login_required
def list_attendance():
    """List all attendance sessions"""
    restored_response = _restore_attendance_list_state_if_needed()
    if restored_response:
        return restored_response

    stored_state = session.get(ATTENDANCE_LIST_STATE_SESSION_KEY) or {}
    page = request.args.get("page", 1, type=int)
    per_page = _get_attendance_per_page(stored_state)
    filter_source = request.args if request.args else stored_state

    # Filter options
    enrollment_id = _decode_optional_ref_value(
        filter_source.get("enrollment_ref"), "enrollment"
    )
    student_id = _decode_optional_ref_value(filter_source.get("student_ref"), "student")
    selected_tutor_refs = _get_filter_values(filter_source, "tutor_ref")
    tutor_ids = _decode_optional_ref_values(selected_tutor_refs, "tutor")
    tutor_id = tutor_ids[0] if len(tutor_ids) == 1 else None
    if enrollment_id is None:
        enrollment_id = request.args.get("enrollment_id", type=int) if request.args else None
    if student_id is None:
        student_id = request.args.get("student_id", type=int) if request.args else None
    if not tutor_ids and tutor_id is None:
        tutor_id = request.args.get("tutor_id", type=int) if request.args else None
        if tutor_id:
            tutor_ids = [tutor_id]
    month = request.args.get("month", type=int) if request.args else _safe_int(stored_state.get("month"))
    year = request.args.get("year", type=int) if request.args else _safe_int(stored_state.get("year"))
    status = None
    date_from = _parse_iso_date(
        request.args.get("date_from") if request.args else stored_state.get("date_from")
    )
    date_to = _parse_iso_date(
        request.args.get("date_to") if request.args else stored_state.get("date_to")
    )
    selected_sort = (request.args.get("sort") if request.args else stored_state.get("sort")) or "date_desc"
    if selected_sort not in ATTENDANCE_SORT_OPTIONS:
        selected_sort = "date_desc"
    _remember_attendance_list_state()

    query = _build_attendance_list_query(
        enrollment_id=enrollment_id,
        student_id=student_id,
        tutor_id=tutor_id,
        tutor_ids=tutor_ids,
        month=month,
        year=year,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )

    sessions = _apply_attendance_list_sort(query, selected_sort).paginate(
        page=page,
        per_page=per_page,
    )
    whatsapp_review_map = _build_whatsapp_review_map(sessions.items)

    # Get enrollments and tutors for filter dropdowns
    enrollments = Enrollment.query.filter_by(status="active").all()
    students = Student.query.order_by(Student.name.asc()).all()
    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
    selected_tutors = [tutor for tutor in tutors if tutor.id in tutor_ids]
    year_options = _build_attendance_year_options()
    lock_month = month or date.today().month
    lock_year = year or date.today().year
    attendance_period_lock = _get_attendance_period_lock(lock_month, lock_year)
    attendance_period_lock_options, locked_period_keys = _build_attendance_period_lock_options(
        year_options, lock_month, lock_year
    )

    return render_template(
        "attendance/list.html",
        sessions=sessions,
        enrollments=enrollments,
        students=students,
        tutors=tutors,
        attendance_tutor_map=_build_tutor_enrollment_map(enrollments),
        year_options=year_options,
        selected_enrollment_id=enrollment_id,
        selected_enrollment_ref=next(
            (enr.public_id for enr in enrollments if enr.id == enrollment_id),
            "",
        ),
        selected_student_id=student_id,
        selected_student_ref=next(
            (student.public_id for student in students if student.id == student_id),
            "",
        ),
        selected_student_name=next(
            (student.name for student in students if student.id == student_id),
            "",
        ),
        selected_tutor_id=tutor_id,
        selected_tutor_ref=selected_tutors[0].public_id if len(selected_tutors) == 1 else "",
        selected_tutor_refs=[tutor.public_id for tutor in selected_tutors],
        selected_tutors=selected_tutors,
        selected_month=month,
        selected_year=year,
        selected_status=None,
        selected_date_from=date_from.isoformat() if date_from else "",
        selected_date_to=date_to.isoformat() if date_to else "",
        selected_sort=selected_sort,
        default_scan_month=month or date.today().month,
        default_scan_year=year or date.today().year,
        lock_month=lock_month,
        lock_year=lock_year,
        attendance_period_lock=attendance_period_lock,
        attendance_period_lock_options=attendance_period_lock_options,
        locked_period_keys=locked_period_keys,
        whatsapp_review_map=whatsapp_review_map,
        whatsapp_review_start_date=WHATSAPP_REVIEW_START_DATE,
    )


@attendance_bp.route("/export-csv", methods=["GET"])
@login_required
def export_attendance_csv():
    """Export filtered attendance sessions as CSV."""
    enrollment_id = _decode_optional_query_ref("enrollment_ref", "enrollment")
    student_id = _decode_optional_query_ref("student_ref", "student")
    selected_tutor_refs = request.args.getlist("tutor_ref")
    tutor_ids = _decode_optional_ref_values(selected_tutor_refs, "tutor")
    tutor_id = tutor_ids[0] if len(tutor_ids) == 1 else None
    if enrollment_id is None:
        enrollment_id = request.args.get("enrollment_id", type=int)
    if student_id is None:
        student_id = request.args.get("student_id", type=int)
    if not tutor_ids and tutor_id is None:
        tutor_id = request.args.get("tutor_id", type=int)
        if tutor_id:
            tutor_ids = [tutor_id]
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    status = None
    date_from = _parse_iso_date(request.args.get("date_from"))
    date_to = _parse_iso_date(request.args.get("date_to"))
    selected_sort = request.args.get("sort", "date_desc")
    if selected_sort not in ATTENDANCE_SORT_OPTIONS:
        selected_sort = "date_desc"

    query = _build_attendance_list_query(
        enrollment_id=enrollment_id,
        student_id=student_id,
        tutor_id=tutor_id,
        tutor_ids=tutor_ids,
        month=month,
        year=year,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    rows = _apply_attendance_list_sort(query, selected_sort).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["No", "Tanggal", "Hari", "Tutor", "Siswa", "Kurikulum", "Jenjang", "Mapel", "Nominal"]
    )
    for index, session_item in enumerate(rows, start=1):
        writer.writerow(_attendance_csv_row(session_item, index))

    filename_parts = ["presensi"]
    if month:
        filename_parts.append(f"{month:02d}")
    if year:
        filename_parts.append(str(year))
    if date_from or date_to:
        filename_parts.append((date_from.isoformat() if date_from else "awal") + "_sd_" + (date_to.isoformat() if date_to else "akhir"))
    filename = "-".join(filename_parts) + ".csv"
    csv_body = "\ufeff" + output.getvalue()

    return Response(
        csv_body,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@attendance_bp.route("/scan-whatsapp", methods=["POST"])
@login_required
def scan_whatsapp_attendance():
    """Scan WhatsApp evaluations for one selected month and link to attendance."""
    month = request.form.get("month", type=int)
    year = request.form.get("year", type=int)
    selected_sort = request.form.get("sort") or "date_desc"
    if selected_sort not in ATTENDANCE_SORT_OPTIONS:
        selected_sort = "date_desc"
    enrollment_ref = (request.form.get("enrollment_ref") or "").strip()
    student_ref = (request.form.get("student_ref") or "").strip()
    tutor_refs = [value for value in request.form.getlist("tutor_ref") if value]
    date_from = (request.form.get("date_from") or "").strip()
    date_to = (request.form.get("date_to") or "").strip()

    redirect_kwargs = {
        "month": month or "",
        "year": year or "",
        "enrollment_ref": enrollment_ref,
        "student_ref": student_ref,
        "tutor_ref": tutor_refs,
        "date_from": date_from,
        "date_to": date_to,
        "sort": selected_sort,
    }

    if not month or not year:
        flash("Pilih bulan dan tahun scan presensi WhatsApp terlebih dahulu.", "warning")
        return redirect(url_for("attendance.list_attendance", **redirect_kwargs))

    try:
        summary = WhatsAppIngestService.scan_attendance_for_month(month, year)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("attendance.list_attendance", **redirect_kwargs))
    except Exception as exc:
        db.session.rollback()
        flash(f"Scan presensi WhatsApp gagal: {exc}", "danger")
        return redirect(url_for("attendance.list_attendance", **redirect_kwargs))

    if summary.get("locked"):
        flash(
            (
                f"Presensi {INDONESIAN_MONTH_NAMES[month]} {year} sedang dikunci. "
                "Scan WhatsApp dilewati agar data manual tidak berubah."
            ),
            "warning",
        )
    elif summary["processed_evaluations"] == 0:
        flash(
            f"Tidak ada evaluasi WhatsApp tersimpan untuk {INDONESIAN_MONTH_NAMES[month]} {year}.",
            "warning",
        )
    else:
        flash(
            (
                f"Scan WhatsApp {INDONESIAN_MONTH_NAMES[month]} {year}: "
                f"{summary['processed_evaluations']} evaluasi diproses, "
                f"{summary['linked_attendance']} presensi ditautkan, "
                f"{summary['ambiguous']} ambigu, "
                f"{summary['unmatched']} belum cocok."
            ),
            "success" if summary["linked_attendance"] else "info",
        )
    return redirect(url_for("attendance.list_attendance", **redirect_kwargs))


@attendance_bp.route("/period-lock", methods=["POST"])
@login_required
def set_attendance_period_lock():
    """Lock or unlock selected attendance months so WhatsApp scan cannot mutate them."""
    current_month = request.form.get("current_month", type=int) or request.form.get(
        "month", type=int
    )
    current_year = request.form.get("current_year", type=int) or request.form.get(
        "year", type=int
    )
    action = (request.form.get("action") or "lock").strip()
    selected_sort = request.form.get("sort") or "date_desc"
    if selected_sort not in ATTENDANCE_SORT_OPTIONS:
        selected_sort = "date_desc"

    redirect_kwargs = {
        "month": current_month or "",
        "year": current_year or "",
        "student_ref": (request.form.get("student_ref") or "").strip(),
        "tutor_ref": [value for value in request.form.getlist("tutor_ref") if value],
        "date_from": (request.form.get("date_from") or "").strip(),
        "date_to": (request.form.get("date_to") or "").strip(),
        "sort": selected_sort,
    }

    period_values = request.form.getlist("period")
    if not period_values and request.form.get("month") and request.form.get("year"):
        period_values = [f"{request.form.get('year')}-{int(request.form.get('month')):02d}"]

    periods = []
    for value in period_values:
        try:
            year_text, month_text = str(value).split("-", 1)
            year = int(year_text)
            month = int(month_text)
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12 and 2000 <= year <= 2100:
            periods.append((month, year))

    periods = list(dict.fromkeys(periods))
    if not periods:
        flash("Pilih minimal satu bulan untuk dikunci atau dibuka.", "danger")
        return redirect(url_for("attendance.list_attendance", **redirect_kwargs))

    changed_count = 0
    if action == "unlock":
        for month, year in periods:
            period_lock = _get_attendance_period_lock(month, year)
            if not period_lock:
                continue
            db.session.delete(period_lock)
            changed_count += 1
        db.session.commit()
        flash(
            f"{changed_count} bulan kunci presensi dibuka."
            if changed_count
            else "Bulan pilihan belum ada yang terkunci.",
            "success" if changed_count else "info",
        )
    else:
        for month, year in periods:
            period_lock = _get_attendance_period_lock(month, year)
            if period_lock:
                continue
            db.session.add(
                AttendancePeriodLock(
                    month=month,
                    year=year,
                    locked_by=current_user.id if current_user.is_authenticated else None,
                )
            )
            changed_count += 1
        db.session.commit()
        flash(
            (
                f"{changed_count} bulan presensi dikunci. "
                "Scan WhatsApp berikutnya tidak akan menambah atau mengubah presensi bulan pilihan."
            ),
            "success" if changed_count else "info",
        )

    return redirect(url_for("attendance.list_attendance", **redirect_kwargs))


@attendance_bp.route("/<string:session_ref>/whatsapp-review", methods=["POST"])
@login_required
def review_whatsapp_attendance(session_ref):
    """Mark linked WhatsApp-scanned attendance as manually crosschecked."""
    session = _get_session_by_ref_or_404(session_ref)
    review_status = (request.form.get("review_status") or "").strip()
    review_notes = request.form.get("review_notes")
    wants_json = _wants_json_response()

    if _get_attendance_lock_for_date(session.session_date):
        message = _attendance_locked_message(session.session_date)
        if wants_json:
            return jsonify({"ok": False, "error": message}), 423
        flash(message, "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    try:
        updated_count = _set_whatsapp_attendance_manual_review(
            session,
            review_status,
            reviewer_id=getattr(current_user, "id", None),
            notes=review_notes,
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        if wants_json:
            return jsonify({"ok": False, "error": str(exc)}), 400
        flash(str(exc), "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))
    except Exception as exc:
        db.session.rollback()
        if wants_json:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Validasi manual WhatsApp gagal: {exc}",
                    }
                ),
                500,
            )
        flash(f"Validasi manual WhatsApp gagal: {exc}", "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    if updated_count == 0:
        message = "Tidak ada evaluasi WhatsApp yang perlu divalidasi untuk sesi ini."
        flash_category = "warning"
    elif review_status == "valid":
        message = "Presensi WhatsApp ditandai sudah benar secara manual."
        flash_category = "success"
    elif review_status == "invalid":
        message = "Presensi WhatsApp ditandai perlu koreksi manual."
        flash_category = "warning"
    else:
        message = "Status validasi manual WhatsApp direset."
        flash_category = "info"
    if wants_json:
        return jsonify(
            _whatsapp_review_response_payload(review_status, updated_count, message)
        )
    flash(message, flash_category)
    return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))


@attendance_bp.route("/bulk-whatsapp-review", methods=["POST"])
@login_required
def bulk_review_whatsapp_attendance():
    """Bulk mark selected WhatsApp-scanned attendance as manually crosschecked."""
    session_refs = request.form.getlist("attendance_refs")
    review_status = (request.form.get("review_status") or "").strip()
    review_notes = request.form.get("review_notes")

    if review_status not in WHATSAPP_REVIEW_STATUSES:
        flash("Status validasi manual WhatsApp tidak valid.", "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))
    if not session_refs:
        flash("Pilih minimal satu presensi WhatsApp terlebih dahulu.", "warning")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    session_ids = []
    for session_ref in session_refs:
        try:
            session_ids.append(decode_public_id(session_ref, "attendance_session"))
        except ValueError:
            continue

    if not session_ids:
        flash("Tidak ada presensi valid yang dipilih.", "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    sessions_to_review = AttendanceSession.query.filter(
        AttendanceSession.id.in_(session_ids)
    ).all()
    locked_session = next(
        (
            attendance_session
            for attendance_session in sessions_to_review
            if _get_attendance_lock_for_date(attendance_session.session_date)
        ),
        None,
    )
    if locked_session:
        flash(_attendance_locked_message(locked_session.session_date), "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    try:
        updated_count = 0
        for attendance_session in sessions_to_review:
            updated_count += _set_whatsapp_attendance_manual_review(
                attendance_session,
                review_status,
                reviewer_id=getattr(current_user, "id", None),
                notes=review_notes,
            )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))
    except Exception as exc:
        db.session.rollback()
        flash(f"Validasi bulk WhatsApp gagal: {exc}", "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    if updated_count == 0:
        flash("Tidak ada evaluasi WhatsApp yang perlu divalidasi dari pilihan ini.", "warning")
    else:
        action_label = {
            "valid": "ditandai sudah benar",
            "invalid": "ditandai perlu koreksi",
            "pending": "direset status validasinya",
        }.get(review_status, "diperbarui")
        flash(f"{updated_count} evaluasi WhatsApp berhasil {action_label}.", "success")
    return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))


@attendance_bp.route("/calendar", methods=["GET"])
@login_required
def calendar_view():
    """Monthly lesson calendar built from enrollment schedules."""
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    tutor_id = _decode_optional_query_ref("tutor_ref", "tutor")
    student_id = _decode_optional_query_ref("student_ref", "student")
    if tutor_id is None:
        tutor_id = request.args.get("tutor_id", type=int)
    if student_id is None:
        student_id = request.args.get("student_id", type=int)
    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
    students = Student.query.order_by(Student.name.asc()).all()
    calendar_data = _build_lesson_calendar(
        month, year, tutor_id=tutor_id, student_id=student_id
    )
    return render_template(
        "attendance/calendar.html",
        tutors=tutors,
        students=students,
        selected_tutor_id=tutor_id,
        selected_tutor_ref=next(
            (tutor.public_id for tutor in tutors if tutor.id == tutor_id),
            "",
        ),
        selected_student_id=student_id,
        selected_student_ref=next(
            (student.public_id for student in students if student.id == student_id),
            "",
        ),
        month_options=list(enumerate(INDONESIAN_MONTH_NAMES))[1:],
        calendar_data=calendar_data,
    )


@attendance_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_attendance():
    """Add new attendance session"""
    form = AttendanceSessionForm()

    if form.validate_on_submit():
        try:
            enrollment = Enrollment.query.get_or_404(form.enrollment_id.data)
            selected_subject_id = form.subject_id.data or enrollment.subject_id
            _ensure_attendance_date_unlocked(form.session_date.data)

            session = AttendanceSession(
                enrollment_id=form.enrollment_id.data,
                student_id=enrollment.student_id,
                tutor_id=form.tutor_id.data,
                session_date=form.session_date.data,
                status="attended",
                student_present=form.student_present.data,
                tutor_present=form.tutor_present.data,
                subject_id=selected_subject_id,
                tutor_fee_amount=form.tutor_fee_amount.data,
                notes=form.notes.data,
            )

            db.session.add(session)
            db.session.commit()

            flash("Presensi berhasil dicatat", "success")
            return redirect(url_for("attendance.list_attendance"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    # Get enrollments for dropdown
    enrollments = Enrollment.query.filter_by(status="active").all()

    return render_template(
        "attendance/form.html",
        form=form,
        enrollments=enrollments,
        attendance_tutor_map=_build_tutor_enrollment_map(enrollments),
        title="Tambah Presensi",
    )


@attendance_bp.route("/<string:session_ref>/edit", methods=["GET", "POST"])
@login_required
def edit_attendance(session_ref):
    """Edit attendance session"""
    session = _get_session_by_ref_or_404(session_ref)
    form = AttendanceSessionForm()

    if form.validate_on_submit():
        try:
            enrollment = Enrollment.query.get_or_404(form.enrollment_id.data)
            selected_subject_id = form.subject_id.data or enrollment.subject_id
            _ensure_attendance_date_unlocked(session.session_date)
            _ensure_attendance_date_unlocked(form.session_date.data)

            session.enrollment_id = form.enrollment_id.data
            session.student_id = enrollment.student_id
            session.tutor_id = form.tutor_id.data
            session.session_date = form.session_date.data
            session.student_present = form.student_present.data
            session.tutor_present = form.tutor_present.data
            session.subject_id = selected_subject_id
            session.tutor_fee_amount = form.tutor_fee_amount.data
            session.notes = form.notes.data
            session.updated_at = datetime.utcnow()
            _sync_linked_whatsapp_evaluations(session)

            db.session.commit()

            flash("Presensi berhasil diperbarui", "success")
            return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    elif request.method == "GET":
        form.enrollment_id.data = session.enrollment_id
        form.tutor_id.data = session.tutor_id
        form.session_date.data = session.session_date
        form.student_present.data = session.student_present
        form.tutor_present.data = session.tutor_present
        form.subject_id.data = session.subject_id
        form.tutor_fee_amount.data = session.tutor_fee_amount
        form.notes.data = session.notes

    enrollments = Enrollment.query.filter_by(status="active").all()

    return render_template(
        "attendance/form.html",
        form=form,
        session=session,
        enrollments=enrollments,
        attendance_tutor_map=_build_tutor_enrollment_map(enrollments),
        title="Edit Presensi",
    )


@attendance_bp.route("/<string:session_ref>/delete", methods=["POST"])
@login_required
def delete_attendance(session_ref):
    """Delete attendance session"""
    session = _get_session_by_ref_or_404(session_ref)
    if _get_attendance_lock_for_date(session.session_date):
        flash(_attendance_locked_message(session.session_date), "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    try:
        unlinked_count = _unlink_whatsapp_evaluations_before_attendance_delete(session)
        db.session.delete(session)
        db.session.commit()
        if unlinked_count:
            flash(
                (
                    "Presensi berhasil dihapus. "
                    f"{unlinked_count} evaluasi WhatsApp tetap disimpan dan dilepas dari presensi ini."
                ),
                "success",
            )
        else:
            flash("Presensi berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))


@attendance_bp.route("/monthly-summary", methods=["GET"])
@login_required
def monthly_summary():
    """Get monthly attendance summary"""
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not month:
        today = date.today()
        month = today.month
        year = today.year

    summary = attendance_service.get_monthly_summary(month, year)

    return render_template(
        "attendance/monthly_summary.html", summary=summary, month=month, year=year
    )


@attendance_bp.route("/bulk-add", methods=["GET", "POST"])
@login_required
def bulk_add_attendance():
    """Bulk add attendance sessions"""
    form = BulkAttendanceForm()

    if form.validate_on_submit():
        try:
            _ensure_attendance_date_unlocked(form.session_date.data)
            count = attendance_service.create_bulk_attendance(
                form.enrollment_ids.data,
                form.session_date.data,
                form.tutor_fee_amount.data,
            )
            flash(f"{count} presensi berhasil ditambahkan", "success")
            return redirect(url_for("attendance.list_attendance"))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    return render_template(
        "attendance/bulk_form.html", form=form, title="Tambah Presensi Massal"
    )


@attendance_bp.route("/api/get-tutor-fee", methods=["POST"])
@login_required
def api_get_tutor_fee():
    """API endpoint to get tutor fee for enrollment"""
    enrollment_id = request.json.get("enrollment_id")

    try:
        enrollment = Enrollment.query.get(enrollment_id)
        if enrollment:
            return jsonify(
                {"success": True, "tutor_fee": float(enrollment.tutor_rate_per_meeting)}
            )
        else:
            return jsonify({"success": False, "error": "Enrollment not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
