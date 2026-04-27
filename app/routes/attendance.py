"""
Attendance routes for Dashboard Keuangan LBB Super Smart
Handles presensi tutor and sesi les
"""

from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.forms import AttendanceSessionForm, BulkAttendanceForm
from app.models import AttendanceSession, Enrollment, Student, Tutor
from app.services import AttendanceService

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")

attendance_service = AttendanceService()


@attendance_bp.route("/", methods=["GET"])
@login_required
def list_attendance():
    """List all attendance sessions"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Filter options
    enrollment_id = request.args.get("enrollment_id", type=int)
    tutor_id = request.args.get("tutor_id", type=int)
    month = request.args.get("month", type=int)
    status = request.args.get("status")

    query = AttendanceSession.query

    if enrollment_id:
        query = query.filter_by(enrollment_id=enrollment_id)
    if tutor_id:
        query = query.filter(AttendanceSession.enrollment.has(tutor_id=tutor_id))
    if month:
        query = query.filter(
            db.extract("month", AttendanceSession.session_date) == month
        )
    if status:
        query = query.filter_by(status=status)

    sessions = query.order_by(AttendanceSession.session_date.desc()).paginate(
        page=page, per_page=per_page
    )

    # Get enrollments and tutors for filter dropdowns
    enrollments = Enrollment.query.filter_by(status="active").all()
    tutors = Tutor.query.filter_by(is_active=True).all()

    return render_template(
        "attendance/list.html",
        sessions=sessions,
        enrollments=enrollments,
        tutors=tutors,
        selected_enrollment_id=enrollment_id,
        selected_tutor_id=tutor_id,
        selected_month=month,
        selected_status=status,
    )


@attendance_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_attendance():
    """Add new attendance session"""
    form = AttendanceSessionForm()

    if form.validate_on_submit():
        try:
            session = AttendanceSession(
                enrollment_id=form.enrollment_id.data,
                session_date=form.session_date.data,
                status="attended",
                student_present=form.student_present.data,
                tutor_present=form.tutor_present.data,
                subject_id=form.subject_id.data,
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
        title="Tambah Presensi",
    )


@attendance_bp.route("/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
def edit_attendance(session_id):
    """Edit attendance session"""
    session = AttendanceSession.query.get_or_404(session_id)
    form = AttendanceSessionForm()

    if form.validate_on_submit():
        try:
            session.enrollment_id = form.enrollment_id.data
            session.session_date = form.session_date.data
            session.student_present = form.student_present.data
            session.tutor_present = form.tutor_present.data
            session.subject_id = form.subject_id.data
            session.tutor_fee_amount = form.tutor_fee_amount.data
            session.notes = form.notes.data
            session.updated_at = datetime.utcnow()

            db.session.commit()

            flash("Presensi berhasil diperbarui", "success")
            return redirect(url_for("attendance.list_attendance"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    elif request.method == "GET":
        form.enrollment_id.data = session.enrollment_id
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
        title="Edit Presensi",
    )


@attendance_bp.route("/<int:session_id>/delete", methods=["POST"])
@login_required
def delete_attendance(session_id):
    """Delete attendance session"""
    session = AttendanceSession.query.get_or_404(session_id)

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
