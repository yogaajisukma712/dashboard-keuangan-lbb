"""
Income routes for Dashboard Keuangan LBB Super Smart
Handles routes for managing other incomes (non-student payments)
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import IncomeForm
from app.models import OtherIncome

incomes_bp = Blueprint("incomes", __name__, url_prefix="/incomes")


@incomes_bp.route("/", methods=["GET"])
@login_required
def list_incomes():
    """List all incomes with pagination"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    incomes = OtherIncome.query.order_by(OtherIncome.income_date.desc()).paginate(
        page=page, per_page=per_page
    )

    return render_template("incomes/list.html", incomes=incomes)


@incomes_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_income():
    """Add new income"""
    form = IncomeForm()

    if form.validate_on_submit():
        try:
            income = OtherIncome(
                income_date=form.income_date.data,
                category=form.category.data,
                description=form.description.data,
                amount=form.amount.data,
                notes=form.notes.data,
                created_by=current_user.id if current_user.is_authenticated else None,
            )

            db.session.add(income)
            db.session.commit()

            flash(f"Income {form.category.data} berhasil ditambahkan", "success")
            return redirect(url_for("incomes.list_incomes"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    return render_template("incomes/form.html", form=form, title="Tambah Pemasukan")


@incomes_bp.route("/<int:income_id>/edit", methods=["GET", "POST"])
@login_required
def edit_income(income_id):
    """Edit existing income"""
    income = OtherIncome.query.get_or_404(income_id)
    form = IncomeForm()

    if form.validate_on_submit():
        try:
            income.income_date = form.income_date.data
            income.category = form.category.data
            income.description = form.description.data
            income.amount = form.amount.data
            income.notes = form.notes.data

            db.session.commit()

            flash("Income berhasil diubah", "success")
            return redirect(url_for("incomes.list_incomes"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
    elif request.method == "GET":
        form.income_date.data = income.income_date
        form.category.data = income.category
        form.description.data = income.description
        form.amount.data = income.amount
        form.notes.data = income.notes

    return render_template(
        "incomes/form.html", form=form, title="Edit Pemasukan", income=income
    )


@incomes_bp.route("/<int:income_id>/delete", methods=["POST"])
@login_required
def delete_income(income_id):
    """Delete income"""
    income = OtherIncome.query.get_or_404(income_id)

    try:
        db.session.delete(income)
        db.session.commit()
        flash("Income berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("incomes.list_incomes"))


@incomes_bp.route("/summary", methods=["GET"])
@login_required
def income_summary():
    """Income summary by category"""
    # This will be implemented with aggregate queries
    return render_template("incomes/summary.html")
