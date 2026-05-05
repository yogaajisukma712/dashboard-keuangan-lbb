"""
Enrollments routes for Dashboard Keuangan LBB Super Smart
Handles all enrollment-related operations
"""

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
from flask_login import login_required
from sqlalchemy import or_

from app import db
from app.forms import EnrollmentForm
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    Level,
    Student,
    Subject,
    Tutor,
    WhatsAppGroup,
)
from app.services.whatsapp_ingest_service import WhatsAppIngestService
from app.utils import decode_public_id, get_per_page

enrollments_bp = Blueprint("enrollments", __name__, url_prefix="/enrollments")
DEFAULT_ENROLLMENT_SORT = "last_attendance_desc"
ENROLLMENT_LIST_STATE_KEY = "enrollment_list_state"
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
        "page": max(page or 1, 1),
        "per_page": max(per_page or 1, 1),
        "q": str(search_term or ""),
        "status": str(status or ""),
        "sort": sort_by if sort_by in ENROLLMENT_SORT_OPTIONS else DEFAULT_ENROLLMENT_SORT,
    }
    flask_session[ENROLLMENT_LIST_STATE_KEY] = state
    return state


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
        return redirect(
            url_for(
                "enrollments.list_enrollments",
                **flask_session[ENROLLMENT_LIST_STATE_KEY],
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
    return render_template(
        "enrollments/list.html",
        enrollments=enrollments,
        search_term=search_term,
        selected_status=status,
        selected_sort=sort_by,
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
    redirect_kwargs = _store_enrollment_list_state(
        page, per_page, search_term, status, sort_by
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
    try:
        db.session.delete(enrollment)
        db.session.commit()
        flash("Enrollment berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("enrollments.list_enrollments"))
