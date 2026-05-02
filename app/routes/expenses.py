"""
Expense routes for Dashboard Keuangan LBB Super Smart
Routes for managing operational expenses
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import ExpenseForm
from app.models import Expense
from app.utils import decode_public_id

expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")


def _get_expense_by_ref_or_404(expense_ref):
    """Resolve opaque expense ref to model instance."""
    try:
        expense_id = decode_public_id(expense_ref, "expense")
    except ValueError:
        abort(404)
    return Expense.query.get_or_404(expense_id)


@expenses_bp.route("/")
@expenses_bp.route("/list")
@login_required
def list_expenses():
    """List all expenses"""
    page = request.args.get("page", 1, type=int)
    expenses = Expense.query.order_by(Expense.expense_date.desc()).paginate(
        page=page, per_page=20
    )
    return render_template("expenses/list.html", expenses=expenses)


@expenses_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    """Add new expense"""
    form = ExpenseForm()
    if form.validate_on_submit():
        try:
            expense = Expense(
                expense_date=form.expense_date.data,
                category=form.category.data,
                description=form.description.data,
                amount=form.amount.data,
                payment_method=form.payment_method.data,
                reference_number=form.reference_number.data,
                notes=form.notes.data,
                created_by=current_user.id if current_user.is_authenticated else None,
            )
            db.session.add(expense)
            db.session.commit()
            flash(f"Pengeluaran berhasil ditambahkan", "success")
            return redirect(url_for("expenses.list_expenses"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    return render_template("expenses/form.html", form=form, title="Tambah Pengeluaran")


@expenses_bp.route("/<string:expense_ref>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_ref):
    """Edit expense"""
    expense = _get_expense_by_ref_or_404(expense_ref)
    form = ExpenseForm()

    if form.validate_on_submit():
        try:
            expense.expense_date = form.expense_date.data
            expense.category = form.category.data
            expense.description = form.description.data
            expense.amount = form.amount.data
            expense.payment_method = form.payment_method.data
            expense.reference_number = form.reference_number.data
            expense.notes = form.notes.data

            db.session.commit()
            flash(f"Pengeluaran berhasil diubah", "success")
            return redirect(url_for("expenses.list_expenses"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    elif request.method == "GET":
        form.expense_date.data = expense.expense_date
        form.category.data = expense.category
        form.description.data = expense.description
        form.amount.data = expense.amount
        form.payment_method.data = expense.payment_method
        form.reference_number.data = expense.reference_number
        form.notes.data = expense.notes

    return render_template(
        "expenses/form.html", form=form, expense=expense, title="Edit Pengeluaran"
    )


@expenses_bp.route("/<string:expense_ref>/delete", methods=["POST"])
@login_required
def delete_expense(expense_ref):
    """Delete expense"""
    expense = _get_expense_by_ref_or_404(expense_ref)
    try:
        db.session.delete(expense)
        db.session.commit()
        flash(f"Pengeluaran berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("expenses.list_expenses"))


@expenses_bp.route("/summary")
@login_required
def expense_summary():
    """Summary expenses by category"""
    # This will be implemented with dashboard service
    return render_template("expenses/summary_by_category.html")
