"""
Payment routes for Dashboard Keuangan LBB Super Smart
Handles student payments, payment lists, and payment history
"""

from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.forms import StudentPaymentForm, StudentPaymentLineForm
from app.models import Enrollment, Student, StudentPayment, StudentPaymentLine
from app.services import PaymentService

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

payment_service = PaymentService()


@payments_bp.route("/", methods=["GET"])
@login_required
def list_payments():
    """List all student payments"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    # Get filter parameters
    student_id = request.args.get("student_id", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    query = StudentPayment.query.order_by(StudentPayment.payment_date.desc())

    # Apply filters
    if student_id:
        query = query.filter_by(student_id=student_id)

    if date_from:
        query = query.filter(
            StudentPayment.payment_date >= datetime.fromisoformat(date_from)
        )

    if date_to:
        query = query.filter(
            StudentPayment.payment_date <= datetime.fromisoformat(date_to)
        )

    paginated = query.paginate(page=page, per_page=per_page)

    return render_template(
        "payments/list.html",
        payments=paginated.items,
        paginated=paginated,
        students=Student.query.filter_by(is_active=True).all(),
    )


@payments_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_payment():
    """Add new student payment"""
    if request.method == "POST":
        try:
            student_id = request.form.get("student_id", type=int)
            payment_date = datetime.fromisoformat(request.form.get("payment_date"))
            receipt_number = request.form.get("receipt_number")
            payment_method = request.form.get("payment_method")
            total_amount = float(request.form.get("total_amount", 0))
            notes = request.form.get("notes")

            # Create payment header
            payment = StudentPayment(
                student_id=student_id,
                payment_date=payment_date,
                receipt_number=receipt_number,
                payment_method=payment_method,
                total_amount=total_amount,
                notes=notes,
            )

            db.session.add(payment)
            db.session.flush()

            # Process payment lines from request
            enrollment_ids = request.form.getlist("enrollment_id[]")
            meeting_counts = request.form.getlist("meeting_count[]")

            for enrollment_id, meeting_count in zip(enrollment_ids, meeting_counts):
                if enrollment_id and meeting_count:
                    enrollment = Enrollment.query.get(enrollment_id)
                    if enrollment:
                        line = StudentPaymentLine(
                            student_payment_id=payment.id,
                            enrollment_id=enrollment_id,
                            service_month=payment_date.date(),
                            meeting_count=int(meeting_count),
                            student_rate_per_meeting=float(
                                enrollment.student_rate_per_meeting
                            ),
                            tutor_rate_per_meeting=float(
                                enrollment.tutor_rate_per_meeting
                            ),
                            nominal_amount=int(meeting_count)
                            * float(enrollment.student_rate_per_meeting),
                            tutor_payable_amount=int(meeting_count)
                            * float(enrollment.tutor_rate_per_meeting),
                            margin_amount=int(meeting_count)
                            * (
                                float(enrollment.student_rate_per_meeting)
                                - float(enrollment.tutor_rate_per_meeting)
                            ),
                        )
                        db.session.add(line)

            db.session.commit()
            flash("Pembayaran siswa berhasil ditambahkan", "success")
            return redirect(url_for("payments.list_payments"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    students = Student.query.filter_by(is_active=True).all()
    enrollments = Enrollment.query.filter_by(status="active").all()

    return render_template(
        "payments/form.html", students=students, enrollments=enrollments
    )


@payments_bp.route("/<int:payment_id>", methods=["GET"])
@login_required
def detail_payment(payment_id):
    """View payment detail"""
    payment = StudentPayment.query.get_or_404(payment_id)

    return render_template("payments/detail.html", payment=payment)


@payments_bp.route("/<int:payment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_payment(payment_id):
    """Edit payment"""
    payment = StudentPayment.query.get_or_404(payment_id)

    if request.method == "POST":
        try:
            payment.payment_date = datetime.fromisoformat(
                request.form.get("payment_date")
            )
            payment.receipt_number = request.form.get("receipt_number")
            payment.payment_method = request.form.get("payment_method")
            payment.total_amount = float(request.form.get("total_amount", 0))
            payment.notes = request.form.get("notes")

            db.session.commit()
            flash("Pembayaran berhasil diupdate", "success")
            return redirect(url_for("payments.detail_payment", payment_id=payment_id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    return render_template(
        "payments/form.html",
        payment=payment,
        students=Student.query.filter_by(is_active=True).all(),
        enrollments=payment.student.enrollments.all(),
    )


@payments_bp.route("/<int:payment_id>/delete", methods=["POST"])
@login_required
def delete_payment(payment_id):
    """Delete payment"""
    payment = StudentPayment.query.get_or_404(payment_id)

    try:
        # Delete payment lines first
        StudentPaymentLine.query.filter_by(student_payment_id=payment_id).delete()
        db.session.delete(payment)
        db.session.commit()
        flash("Pembayaran berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("payments.list_payments"))


@payments_bp.route("/student/<int:student_id>/history", methods=["GET"])
@login_required
def student_payment_history(student_id):
    """View payment history for a specific student"""
    student = Student.query.get_or_404(student_id)
    page = request.args.get("page", 1, type=int)
    per_page = 20

    paginated = (
        StudentPayment.query.filter_by(student_id=student_id)
        .order_by(StudentPayment.payment_date.desc())
        .paginate(page=page, per_page=per_page)
    )

    return render_template(
        "payments/student_payment_history.html",
        student=student,
        payments=paginated.items,
        paginated=paginated,
    )


@payments_bp.route("/api/enrollments/<int:student_id>", methods=["GET"])
@login_required
def get_student_enrollments(student_id):
    """API endpoint to get student enrollments (for AJAX)"""
    enrollments = Enrollment.query.filter_by(
        student_id=student_id, status="active"
    ).all()

    return jsonify(
        [
            {
                "id": e.id,
                "subject_name": e.subject.name,
                "tutor_name": e.tutor.name,
                "student_rate": float(e.student_rate_per_meeting),
                "tutor_rate": float(e.tutor_rate_per_meeting),
            }
            for e in enrollments
        ]
    )


@payments_bp.route("/monthly-summary", methods=["GET"])
@login_required
def monthly_summary():
    """View monthly payment summary"""
    year = request.args.get("year", datetime.utcnow().year, type=int)
    month = request.args.get("month", datetime.utcnow().month, type=int)

    summary = payment_service.get_monthly_summary(year, month)

    return render_template(
        "payments/monthly_summary.html", summary=summary, year=year, month=month
    )
