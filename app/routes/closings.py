"""
Closings routes for Dashboard Keuangan LBB Super Smart
Handles monthly closing operations
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import MonthlyClosing

closings_bp = Blueprint("closings", __name__, url_prefix="/closings")


@closings_bp.route("/monthly-closing")
@login_required
def monthly_closing():
    """Monthly closing page"""
    closings = MonthlyClosing.query.order_by(
        MonthlyClosing.year.desc(), MonthlyClosing.month.desc()
    ).all()
    return render_template("closings/monthly_closing.html", closings=closings)


@closings_bp.route("/closing/create", methods=["GET", "POST"])
@login_required
def create_closing():
    """Create new monthly closing"""
    if request.method == "POST":
        try:
            # TODO: Implement closing logic
            flash("Closing berhasil dibuat", "success")
            return redirect(url_for("closings.monthly_closing"))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    return render_template("closings/closing_form.html")


@closings_bp.route("/closing/<int:month>/detail")
@login_required
def closing_detail(month):
    """View closing detail"""
    closing = MonthlyClosing.query.filter_by(month=month).first_or_404()
    return render_template("closings/closing_detail.html", closing=closing)
