"""
Payroll routes for Dashboard Keuangan LBB Super Smart
Handles tutor payment and payroll management
"""

from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.forms import TutorPayoutForm
from app.models import AttendanceSession, Tutor, TutorPayout, TutorPayoutLine
from app.utils import admin_required

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")


@payroll_bp.route("/tutor-summary", methods=["GET"])
@login_required
def tutor_summary():
    """
    Display summary of tutor payables
    Shows total payable per tutor and payment status
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    tutors = Tutor.query.filter_by(is_active=True).all()

    # Calculate payable for each tutor
    tutor_data = []
    for tutor in tutors:
        # Get attendance sessions for this month/year
        attendance_total = (
            db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.tutor_id == tutor.id,
                db.extract("month", AttendanceSession.session_date) == month,
                db.extract("year", AttendanceSession.session_date) == year,
                AttendanceSession.status == "attended",
            )
            .scalar()
            or 0
        )

        # Get paid amount
        paid_total = (
            db.session.query(db.func.sum(TutorPayoutLine.amount))
            .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
            .filter(
                TutorPayout.tutor_id == tutor.id,
                db.extract("month", TutorPayoutLine.service_month) == month,
                db.extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )

        balance = float(attendance_total) - float(paid_total)

        tutor_data.append(
            {
                "tutor": tutor,
                "payable": float(attendance_total),
                "paid": float(paid_total),
                "balance": balance,
            }
        )

    return render_template(
        "payroll/tutor_summary.html", tutor_data=tutor_data, month=month, year=year
    )


@payroll_bp.route("/payout/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_payout():
    """
    Add new tutor payout
    """
    form = TutorPayoutForm()

    if form.validate_on_submit():
        try:
            payout = TutorPayout(
                tutor_id=form.tutor_id.data,
                payout_date=form.payout_date.data,
                amount=form.amount.data,
                bank_name=form.bank_name.data,
                account_number=form.account_number.data,
                payment_method=form.payment_method.data,
                reference_number=form.reference_number.data,
                notes=form.notes.data,
                status="completed",
            )

            db.session.add(payout)
            db.session.flush()

            # Add payout lines if service_month provided
            service_month = form.service_month.data
            if service_month:
                payout_line = TutorPayoutLine(
                    tutor_payout_id=payout.id,
                    service_month=service_month,
                    amount=form.amount.data,
                )
                db.session.add(payout_line)

            db.session.commit()
            flash(f"Pembayaran gaji ke {payout.tutor.name} berhasil dicatat", "success")
            return redirect(url_for("payroll.tutor_summary"))
        except Exception as e:
            db.session.rollback()
            flash(f"Terjadi kesalahan: {str(e)}", "danger")

    form.tutor_id.choices = [
        (t.id, t.name) for t in Tutor.query.filter_by(is_active=True).all()
    ]

    return render_template("payroll/payout_form.html", form=form)


@payroll_bp.route("/payout/<int:payout_id>", methods=["GET"])
@login_required
def payout_detail(payout_id):
    """
    Display payout detail
    """
    payout = TutorPayout.query.get_or_404(payout_id)

    return render_template("payroll/payout_detail.html", payout=payout)


@payroll_bp.route("/payout/<int:payout_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_payout(payout_id):
    """
    Delete payout (only if not yet processed)
    """
    payout = TutorPayout.query.get_or_404(payout_id)

    try:
        db.session.delete(payout)
        db.session.commit()
        flash("Pembayaran berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Terjadi kesalahan: {str(e)}", "danger")

    return redirect(url_for("payroll.tutor_summary"))


@payroll_bp.route("/transfer-list", methods=["GET"])
@login_required
def transfer_list():
    """
    Display list of pending transfers
    Can be exported to Excel for bulk transfer
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    # Get all tutors with pending balance
    tutors = Tutor.query.filter_by(is_active=True).all()

    transfer_data = []
    total_amount = 0

    for tutor in tutors:
        # Calculate payable
        payable = (
            db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.tutor_id == tutor.id,
                db.extract("month", AttendanceSession.session_date) == month,
                db.extract("year", AttendanceSession.session_date) == year,
                AttendanceSession.status == "attended",
            )
            .scalar()
            or 0
        )

        # Calculate paid
        paid = (
            db.session.query(db.func.sum(TutorPayoutLine.amount))
            .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
            .filter(
                TutorPayout.tutor_id == tutor.id,
                db.extract("month", TutorPayoutLine.service_month) == month,
                db.extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )

        balance = float(payable) - float(paid)

        if balance > 0 and tutor.bank_account_number:
            transfer_data.append(
                {
                    "no": len(transfer_data) + 1,
                    "tutor_name": tutor.name,
                    "bank_name": tutor.bank_name or "-",
                    "account_number": tutor.bank_account_number,
                    "account_holder": tutor.account_holder_name,
                    "amount": balance,
                }
            )
            total_amount += balance

    return render_template(
        "payroll/transfer_list.html",
        transfer_data=transfer_data,
        total_amount=total_amount,
        month=month,
        year=year,
    )


@payroll_bp.route("/api/tutor/<int:tutor_id>/balance", methods=["GET"])
@login_required
def api_tutor_balance(tutor_id):
    """
    API endpoint to get tutor balance
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    tutor = Tutor.query.get_or_404(tutor_id)

    payable = (
        db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
        .filter(
            AttendanceSession.tutor_id == tutor_id,
            db.extract("month", AttendanceSession.session_date) == month,
            db.extract("year", AttendanceSession.session_date) == year,
            AttendanceSession.status == "attended",
        )
        .scalar()
        or 0
    )

    paid = (
        db.session.query(db.func.sum(TutorPayoutLine.amount))
        .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
        .filter(
            TutorPayout.tutor_id == tutor_id,
            db.extract("month", TutorPayoutLine.service_month) == month,
            db.extract("year", TutorPayoutLine.service_month) == year,
        )
        .scalar()
        or 0
    )

    return jsonify(
        {
            "tutor_id": tutor_id,
            "tutor_name": tutor.name,
            "payable": float(payable),
            "paid": float(paid),
            "balance": float(payable) - float(paid),
        }
    )
