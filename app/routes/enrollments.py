"""
Enrollments routes for Dashboard Keuangan LBB Super Smart
Handles all enrollment-related operations
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_

from app import db
from app.forms import EnrollmentForm
from app.models import AttendanceSession, Curriculum, Enrollment, Level, Student, Subject, Tutor
from app.services.whatsapp_ingest_service import WhatsAppIngestService
from app.utils import decode_public_id, get_per_page

enrollments_bp = Blueprint("enrollments", __name__, url_prefix="/enrollments")


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


def _build_enrollment_list_query(search_term: str = "", status: str = ""):
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

    return query.order_by(Enrollment.updated_at.desc(), Enrollment.id.desc())


@enrollments_bp.route("/", methods=["GET"])
@login_required
def list_enrollments():
    """List all enrollments"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    search_term = request.args.get("q", "", type=str)
    status = request.args.get("status", "", type=str)
    enrollments = _build_enrollment_list_query(search_term, status).paginate(
        page=page, per_page=per_page
    )
    return render_template(
        "enrollments/list.html",
        enrollments=enrollments,
        search_term=search_term,
        selected_status=status,
    )


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
