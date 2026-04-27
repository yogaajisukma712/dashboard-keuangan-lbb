"""
Enrollments routes for Dashboard Keuangan LBB Super Smart
Handles all enrollment-related operations
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.forms import EnrollmentForm
from app.models import Curriculum, Enrollment, Level, Student, Subject, Tutor

enrollments_bp = Blueprint("enrollments", __name__, url_prefix="/enrollments")


@enrollments_bp.route("/", methods=["GET"])
@login_required
def list_enrollments():
    """List all enrollments"""
    page = request.args.get("page", 1, type=int)
    enrollments = Enrollment.query.paginate(page=page, per_page=20)
    return render_template("enrollments/list.html", enrollments=enrollments)


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
            db.session.add(enrollment)
            db.session.commit()
            flash("Enrollment berhasil ditambahkan", "success")
            return redirect(url_for("enrollments.list_enrollments"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")

    return render_template(
        "enrollments/form.html", form=form, title="Tambah Enrollment"
    )


@enrollments_bp.route("/<int:id>", methods=["GET"])
@login_required
def enrollment_detail(id):
    """Get enrollment detail"""
    enrollment = Enrollment.query.get_or_404(id)
    return render_template("enrollments/detail.html", enrollment=enrollment)


@enrollments_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_enrollment(id):
    """Edit enrollment"""
    enrollment = Enrollment.query.get_or_404(id)
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
            db.session.commit()
            flash("Enrollment berhasil diupdate", "success")
            return redirect(url_for("enrollments.enrollment_detail", id=enrollment.id))
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
        form.student_rate_per_meeting.data = enrollment.student_rate_per_meeting
        form.tutor_rate_per_meeting.data = enrollment.tutor_rate_per_meeting

    return render_template(
        "enrollments/form.html",
        form=form,
        enrollment=enrollment,
        title="Edit Enrollment",
    )


@enrollments_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete_enrollment(id):
    """Delete enrollment"""
    enrollment = Enrollment.query.get_or_404(id)
    try:
        db.session.delete(enrollment)
        db.session.commit()
        flash("Enrollment berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for("enrollments.list_enrollments"))
