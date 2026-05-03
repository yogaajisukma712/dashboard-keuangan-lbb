"""
Payment routes for Dashboard Keuangan LBB Super Smart
Handles student payments, payment lists, and payment history
"""

from flask import abort
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.forms import StudentPaymentForm, StudentPaymentLineForm
from app.models import Enrollment, Student, StudentPayment, StudentPaymentLine
from app.services import PaymentService
from app.utils import (
    build_qr_code_data_uri,
    decode_public_id,
    get_per_page,
    get_branding_logo_mark_data_uri,
)

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

payment_service = PaymentService()


def _get_student_by_ref_or_404(student_ref):
    """Resolve opaque student ref to model instance."""
    try:
        student_id = decode_public_id(student_ref, "student")
    except ValueError:
        abort(404)
    return Student.query.get_or_404(student_id)


def _get_payment_by_ref_or_404(payment_ref):
    """Resolve opaque payment ref to model instance."""
    try:
        payment_id = decode_public_id(payment_ref, "student_payment")
    except ValueError:
        abort(404)
    return StudentPayment.query.get_or_404(payment_id)


@payments_bp.route("/", methods=["GET"])
@login_required
def list_payments():
    """List all student payments"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()

    # Get filter parameters
    student_ref = (request.args.get("student_ref") or "").strip()
    student_id = None
    if student_ref:
        try:
            student_id = decode_public_id(student_ref, "student")
        except ValueError:
            student_id = None
    elif request.args.get("student_id", type=int):
        legacy_student = Student.query.get(request.args.get("student_id", type=int))
        if legacy_student:
            return redirect(
                url_for(
                    "payments.list_payments",
                    page=page,
                    student_ref=legacy_student.public_id,
                    date_from=request.args.get("date_from", ""),
                    date_to=request.args.get("date_to", ""),
                )
            )
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
        current_student_ref=student_ref,
    )


@payments_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_payment():
    """Add new student payment"""
    if request.method == "POST":
        try:
            student_ref = (request.form.get("student_ref") or "").strip()
            student_id = None
            if student_ref:
                student_id = decode_public_id(student_ref, "student")
            elif request.form.get("student_id", type=int):
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


@payments_bp.route("/<string:payment_ref>", methods=["GET"])
@login_required
def detail_payment(payment_ref):
    """View payment detail"""
    payment = _get_payment_by_ref_or_404(payment_ref)

    return render_template("payments/detail.html", payment=payment)


@payments_bp.route("/<string:payment_ref>/edit", methods=["GET", "POST"])
@login_required
def edit_payment(payment_ref):
    """Edit payment"""
    payment = _get_payment_by_ref_or_404(payment_ref)

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
            return redirect(
                url_for("payments.detail_payment", payment_ref=payment.public_id)
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    return render_template(
        "payments/form.html",
        payment=payment,
        students=Student.query.filter_by(is_active=True).all(),
        enrollments=payment.student.enrollments.all(),
    )


@payments_bp.route("/<string:payment_ref>/delete", methods=["POST"])
@login_required
def delete_payment(payment_ref):
    """Delete payment"""
    payment = _get_payment_by_ref_or_404(payment_ref)

    try:
        # Delete payment lines first
        StudentPaymentLine.query.filter_by(student_payment_id=payment.id).delete()
        db.session.delete(payment)
        db.session.commit()
        flash("Pembayaran berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("payments.list_payments"))


@payments_bp.route("/student/<string:student_ref>/history", methods=["GET"])
@login_required
def student_payment_history(student_ref):
    """View payment history for a specific student"""
    student = _get_student_by_ref_or_404(student_ref)
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()

    paginated = (
        StudentPayment.query.filter_by(student_id=student.id)
        .order_by(StudentPayment.payment_date.desc())
        .paginate(page=page, per_page=per_page)
    )

    return render_template(
        "payments/student_payment_history.html",
        student=student,
        payments=paginated.items,
        paginated=paginated,
    )


@payments_bp.route("/api/enrollments/<string:student_ref>", methods=["GET"])
@login_required
def get_student_enrollments(student_ref):
    """API endpoint to get student enrollments (for AJAX)"""
    student = _get_student_by_ref_or_404(student_ref)
    enrollments = Enrollment.query.filter_by(
        student_id=student.id, status="active"
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


@payments_bp.route("/<string:payment_ref>/invoice", methods=["GET"])
@login_required
def payment_invoice(payment_ref):
    """Tampilkan & unduh invoice sebagai PNG untuk sebuah pembayaran siswa."""
    from collections import OrderedDict
    from datetime import date as dt_date

    from flask import current_app

    payment = _get_payment_by_ref_or_404(payment_ref)

    # Urutkan payment lines: service_month dulu, lalu enrollment_id
    raw_lines = payment.payment_lines.all()
    lines = sorted(
        raw_lines,
        key=lambda l: (l.service_month or dt_date.min, l.enrollment_id or 0),
    )

    # Kelompokkan per service_month (OrderedDict menjaga urutan)
    lines_by_month = OrderedDict()
    for line in lines:
        lines_by_month.setdefault(line.service_month, []).append(line)

    # Program = nama-nama mapel unik, digabung " & "
    seen, subjects = set(), []
    for line in lines:
        if line.enrollment and line.enrollment.subject:
            n = line.enrollment.subject.name
            if n not in seen:
                seen.add(n)
                subjects.append(n)
    program = " & ".join(subjects) if subjects else "—"

    # Kelas = grade + level dari enrollment pertama
    grade_level = "—"
    for line in lines:
        if line.enrollment:
            g = line.enrollment.grade or ""
            lv = line.enrollment.level.name if line.enrollment.level else ""
            grade_level = f"{g} {lv}".strip() or "—"
            break

    reg_fee = current_app.config.get("DEFAULT_REGISTRATION_FEE", 0)
    bank_str = current_app.config.get("INSTITUTION_BANK_ACCOUNTS", "")
    bank_accounts = [b.strip() for b in bank_str.split("|") if b.strip()]

    MONTHS_ID = [
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

    return render_template(
        "payments/invoice.html",
        payment=payment,
        lines_by_month=lines_by_month,
        program=program,
        grade_level=grade_level,
        reg_fee=reg_fee,
        bank_accounts=bank_accounts,
        MONTHS_ID=MONTHS_ID,
        institution_name=current_app.config.get("INSTITUTION_NAME", "LBB Super Smart"),
        institution_phone=current_app.config.get("INSTITUTION_PHONE", ""),
        institution_city=current_app.config.get("INSTITUTION_CITY", "Surabaya"),
        ceo_name=current_app.config.get("INSTITUTION_CEO_NAME", ""),
        ceo_title=current_app.config.get("INSTITUTION_CEO_TITLE", "CEO"),
        branding_logo_mark_data_uri=get_branding_logo_mark_data_uri(),
        signature_qr_data_uri=build_qr_code_data_uri(
            "|".join(
                [
                    "PAYMENT-INVOICE",
                    payment.receipt_number or f"PAY-{payment.id}",
                    payment.student.name if payment.student else "-",
                    payment.payment_date.isoformat() if payment.payment_date else "-",
                    f"{float(payment.total_amount or 0):.0f}",
                ]
            ),
            box_size=4,
        ),
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
