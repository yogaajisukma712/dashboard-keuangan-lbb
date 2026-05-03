"""
Attendance routes for Dashboard Keuangan LBB Super Smart
Handles presensi tutor and sesi les
"""

from calendar import monthrange
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import db
from app.forms import AttendanceSessionForm, BulkAttendanceForm
from app.models import (
    AttendanceSession,
    Enrollment,
    EnrollmentSchedule,
    Student,
    Tutor,
    WhatsAppEvaluation,
)
from app.services import AttendanceService
from app.services.whatsapp_ingest_service import WhatsAppIngestService
from app.utils import decode_public_id, get_per_page

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
    value = (request.args.get(param_name) or "").strip()
    if not value:
        return None
    try:
        return decode_public_id(value, kind)
    except ValueError:
        return None


def _build_lesson_calendar(month: int, year: int, tutor_id: int | None = None):
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
        items_by_date.setdefault(attendance_session.session_date, []).append(
            {
                "date": attendance_session.session_date,
                "tutor_name": attendance_session.tutor.name if attendance_session.tutor else "-",
                "student_name": enrollment.student.name if enrollment.student else "-",
                "subject_name": enrollment.subject.name if enrollment.subject else "-",
                "grade": enrollment.grade or "-",
                "schedule_label": schedule_label,
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
    tutor_id: int | None = None,
    month: int | None = None,
    year: int | None = None,
    status: str | None = None,
):
    query = AttendanceSession.query

    if enrollment_id:
        query = query.filter_by(enrollment_id=enrollment_id)
    if tutor_id:
        query = query.filter_by(tutor_id=tutor_id)
    if month:
        query = query.filter(db.extract("month", AttendanceSession.session_date) == month)
    if year:
        query = query.filter(db.extract("year", AttendanceSession.session_date) == year)
    if status:
        query = query.filter_by(status=status)
    return query


def _attendance_redirect_filters():
    return {
        "page": request.args.get("page", 1, type=int),
        "enrollment_ref": request.args.get("enrollment_ref") or "",
        "tutor_ref": request.args.get("tutor_ref") or "",
        "month": request.args.get("month", type=int) or "",
        "year": request.args.get("year", type=int) or "",
        "status": request.args.get("status") or "",
    }


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


@attendance_bp.route("/", methods=["GET"])
@login_required
def list_attendance():
    """List all attendance sessions"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()

    # Filter options
    enrollment_id = _decode_optional_query_ref("enrollment_ref", "enrollment")
    tutor_id = _decode_optional_query_ref("tutor_ref", "tutor")
    if enrollment_id is None:
        enrollment_id = request.args.get("enrollment_id", type=int)
    if tutor_id is None:
        tutor_id = request.args.get("tutor_id", type=int)
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    status = request.args.get("status")

    query = _build_attendance_list_query(
        enrollment_id=enrollment_id,
        tutor_id=tutor_id,
        month=month,
        year=year,
        status=status,
    )

    sessions = query.order_by(AttendanceSession.session_date.desc()).paginate(
        page=page, per_page=per_page
    )
    whatsapp_review_map = _build_whatsapp_review_map(sessions.items)

    # Get enrollments and tutors for filter dropdowns
    enrollments = Enrollment.query.filter_by(status="active").all()
    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
    year_options = _build_attendance_year_options()

    return render_template(
        "attendance/list.html",
        sessions=sessions,
        enrollments=enrollments,
        tutors=tutors,
        attendance_tutor_map=_build_tutor_enrollment_map(enrollments),
        year_options=year_options,
        selected_enrollment_id=enrollment_id,
        selected_enrollment_ref=next(
            (enr.public_id for enr in enrollments if enr.id == enrollment_id),
            "",
        ),
        selected_tutor_id=tutor_id,
        selected_tutor_ref=next(
            (tutor.public_id for tutor in tutors if tutor.id == tutor_id),
            "",
        ),
        selected_month=month,
        selected_year=year,
        selected_status=status,
        default_scan_month=month or date.today().month,
        default_scan_year=year or date.today().year,
        whatsapp_review_map=whatsapp_review_map,
        whatsapp_review_start_date=WHATSAPP_REVIEW_START_DATE,
    )


@attendance_bp.route("/scan-whatsapp", methods=["POST"])
@login_required
def scan_whatsapp_attendance():
    """Scan WhatsApp evaluations for one selected month and link to attendance."""
    month = request.form.get("month", type=int)
    year = request.form.get("year", type=int)
    status = request.form.get("status")
    enrollment_ref = (request.form.get("enrollment_ref") or "").strip()
    tutor_ref = (request.form.get("tutor_ref") or "").strip()

    redirect_kwargs = {
        "month": month or "",
        "year": year or "",
        "enrollment_ref": enrollment_ref,
        "tutor_ref": tutor_ref,
        "status": status or "",
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

    if summary["processed_evaluations"] == 0:
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


@attendance_bp.route("/<string:session_ref>/whatsapp-review", methods=["POST"])
@login_required
def review_whatsapp_attendance(session_ref):
    """Mark linked WhatsApp-scanned attendance as manually crosschecked."""
    session = _get_session_by_ref_or_404(session_ref)
    review_status = (request.form.get("review_status") or "").strip()
    review_notes = request.form.get("review_notes")

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
        flash(str(exc), "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))
    except Exception as exc:
        db.session.rollback()
        flash(f"Validasi manual WhatsApp gagal: {exc}", "danger")
        return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))

    if updated_count == 0:
        flash(
            "Tidak ada evaluasi WhatsApp yang perlu divalidasi untuk sesi ini.",
            "warning",
        )
    elif review_status == "valid":
        flash("Presensi WhatsApp ditandai sudah benar secara manual.", "success")
    elif review_status == "invalid":
        flash("Presensi WhatsApp ditandai perlu koreksi manual.", "warning")
    else:
        flash("Status validasi manual WhatsApp direset.", "info")
    return redirect(url_for("attendance.list_attendance", **_attendance_redirect_filters()))


@attendance_bp.route("/calendar", methods=["GET"])
@login_required
def calendar_view():
    """Monthly lesson calendar built from enrollment schedules."""
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    tutor_id = _decode_optional_query_ref("tutor_ref", "tutor")
    if tutor_id is None:
        tutor_id = request.args.get("tutor_id", type=int)
    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
    calendar_data = _build_lesson_calendar(month, year, tutor_id=tutor_id)
    return render_template(
        "attendance/calendar.html",
        tutors=tutors,
        selected_tutor_id=tutor_id,
        selected_tutor_ref=next(
            (tutor.public_id for tutor in tutors if tutor.id == tutor_id),
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

    try:
        db.session.delete(session)
        db.session.commit()
        flash("Presensi berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("attendance.list_attendance"))


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
