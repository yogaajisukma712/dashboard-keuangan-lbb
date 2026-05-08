"""
Closings routes for Dashboard Keuangan LBB Super Smart
Handles monthly closing operations
"""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import MonthlyClosing
from app.services.dashboard_service import DashboardService

closings_bp = Blueprint("closings", __name__, url_prefix="/closings")

MONTH_NAMES = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


def _compute_closing_data(month: int, year: int) -> dict:
    """Calculate all KPI values needed for a monthly closing snapshot.

    Returns a dict with every field required by MonthlyClosing plus some
    display-only extras (grand_saldo, grand_hutang) for the preview panel.
    The caller is responsible for saving.
    """
    svc = DashboardService()

    student_income = svc.get_total_income_this_month(month, year)
    other_income = svc.get_other_income_this_month(month, year)
    expenses = svc.get_total_expenses_this_month(month, year)
    tutor_salary = svc.get_tutor_salary_accrual(month, year)
    margin = svc.get_margin_this_month(month, year)
    opening_cash = svc.get_opening_balance(month, year)
    grand_hutang = svc.get_grand_tutor_payable(month, year)
    grand_saldo = svc.get_cash_balance(month, year)
    grand_profit = svc.get_grand_profit(month, year)
    estimasi_sisa = svc.get_estimated_remaining_balance(month, year)

    # closing_tutor_payable = hutang gaji tersisa setelah payout paid/confirmed.
    closing_tp = grand_hutang

    # opening_tutor_payable  = hutang tutor dari bulan sebelumnya
    prev_m, prev_y = DashboardService._prev_month(month, year)
    prev_closing = MonthlyClosing.query.filter_by(month=prev_m, year=prev_y).first()
    if prev_closing:
        opening_tp = float(prev_closing.closing_tutor_payable or 0)
    else:
        earliest = DashboardService._get_earliest_dashboard_period()
        opening_tp = DashboardService._get_opening_tutor_payable_internal(
            month, year, earliest
        )

    return {
        # For display / preview
        "month": month,
        "year": year,
        "month_name": MONTH_NAMES.get(month, str(month)),
        "student_income": student_income,
        "other_income": other_income,
        "expenses": expenses,
        "tutor_salary": tutor_salary,
        "grand_saldo": grand_saldo,
        "grand_hutang": grand_hutang,
        "grand_profit": grand_profit,
        # Fields that map 1-to-1 to MonthlyClosing columns
        "opening_cash_balance": opening_cash,
        "opening_tutor_payable": opening_tp,
        "closing_cash_balance": estimasi_sisa,  # = Estimasi Sisa Saldo
        "closing_tutor_payable": closing_tp,
        "closing_profit": grand_profit,
        "total_income": student_income + other_income,
        "total_expense": expenses,
        "total_tutor_salary": tutor_salary,
        "total_margin": margin + other_income,
    }


def _apply_closing_data(closing: MonthlyClosing, data: dict, notes: str) -> None:
    """Write computed data dict into a MonthlyClosing ORM object (no commit)."""
    closing.opening_cash_balance = Decimal(str(round(data["opening_cash_balance"], 2)))
    closing.opening_tutor_payable = Decimal(
        str(round(data["opening_tutor_payable"], 2))
    )
    closing.closing_cash_balance = Decimal(str(round(data["closing_cash_balance"], 2)))
    closing.closing_tutor_payable = Decimal(
        str(round(data["closing_tutor_payable"], 2))
    )
    closing.closing_profit = Decimal(str(round(data["closing_profit"], 2)))
    closing.total_income = Decimal(str(round(data["total_income"], 2)))
    closing.total_expense = Decimal(str(round(data["total_expense"], 2)))
    closing.total_tutor_salary = Decimal(str(round(data["total_tutor_salary"], 2)))
    closing.total_margin = Decimal(str(round(data["total_margin"], 2)))
    closing.notes = notes or None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@closings_bp.route("/monthly-closing")
@login_required
def monthly_closing():
    """Daftar semua monthly closing."""
    closings = MonthlyClosing.query.order_by(
        MonthlyClosing.year.desc(), MonthlyClosing.month.desc()
    ).all()
    return render_template("closings/monthly_closing.html", closings=closings)


@closings_bp.route("/closing/create", methods=["GET", "POST"])
@login_required
def create_closing():
    """Form pembuatan closing baru.

    GET  → tampilkan form pilih bulan/tahun.
    POST (action=preview)  → hitung KPI, tampilkan preview tanpa simpan.
    POST (action=save)     → simpan sebagai Draft, redirect ke detail.
    POST (action=confirm)  → simpan & kunci sekaligus, redirect ke detail.
    """
    if request.method == "GET":
        return render_template(
            "closings/closing_form.html",
            preview=None,
            form_data={},
            month_names=MONTH_NAMES,
        )

    # ── Parse form ────────────────────────────────────────────────────────────
    try:
        month = int(request.form.get("month", 0))
        year = int(request.form.get("year", 0))
    except (ValueError, TypeError):
        flash("Bulan dan tahun harus berupa angka.", "danger")
        return render_template(
            "closings/closing_form.html",
            preview=None,
            form_data=request.form,
            month_names=MONTH_NAMES,
        )

    notes = (request.form.get("notes") or "").strip()
    action = request.form.get("action", "save")  # preview | save | confirm

    # ── Validate ──────────────────────────────────────────────────────────────
    errors = []
    if not (1 <= month <= 12):
        errors.append("Bulan tidak valid (1–12).")
    if not (2020 <= year <= 2099):
        errors.append("Tahun tidak valid (2020–2099).")

    if errors:
        for e in errors:
            flash(e, "danger")
        return render_template(
            "closings/closing_form.html",
            preview=None,
            form_data=request.form,
            month_names=MONTH_NAMES,
        )

    # ── Guard: sudah dikunci? ─────────────────────────────────────────────────
    existing = MonthlyClosing.query.filter_by(month=month, year=year).first()
    if existing and existing.is_closed:
        flash(
            f"Periode {MONTH_NAMES[month]} {year} sudah di-closing dan dikunci. "
            "Tidak bisa diubah.",
            "warning",
        )
        return redirect(url_for("closings.closing_detail", month=month, year=year))

    # ── Compute KPIs ──────────────────────────────────────────────────────────
    try:
        data = _compute_closing_data(month, year)
    except Exception as exc:
        flash(f"Gagal menghitung data: {exc}", "danger")
        return render_template(
            "closings/closing_form.html",
            preview=None,
            form_data=request.form,
            month_names=MONTH_NAMES,
        )

    data["notes"] = notes

    # ── Preview only → tampilkan tanpa simpan ─────────────────────────────────
    if action == "preview":
        return render_template(
            "closings/closing_form.html",
            preview=data,
            form_data=request.form,
            month_names=MONTH_NAMES,
        )

    # ── Save / Confirm → simpan ke database ───────────────────────────────────
    if existing:
        closing = existing
    else:
        closing = MonthlyClosing(month=month, year=year)
        db.session.add(closing)

    _apply_closing_data(closing, data, notes)

    if action == "confirm":
        closing.is_closed = True
        closing.closed_by = (
            current_user.username if current_user.is_authenticated else "system"
        )
        closing.closed_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal menyimpan closing: {exc}", "danger")
        return render_template(
            "closings/closing_form.html",
            preview=data,
            form_data=request.form,
            month_names=MONTH_NAMES,
        )

    if action == "confirm":
        flash(
            f"Closing {MONTH_NAMES[month]} {year} berhasil disimpan dan dikunci! 🔒",
            "success",
        )
    else:
        flash(
            f"Draft closing {MONTH_NAMES[month]} {year} berhasil disimpan. "
            "Klik 'Konfirmasi & Kunci' di halaman detail jika sudah yakin.",
            "success",
        )

    return redirect(url_for("closings.closing_detail", month=month, year=year))


@closings_bp.route("/closing/<int:month>/<int:year>/detail")
@login_required
def closing_detail(month, year):
    """Halaman detail sebuah closing."""
    closing = MonthlyClosing.query.filter_by(month=month, year=year).first_or_404()
    return render_template("closings/closing_detail.html", closing=closing)


@closings_bp.route("/closing/<int:month>/<int:year>/confirm", methods=["POST"])
@login_required
def confirm_closing(month, year):
    """Kunci draft closing yang sudah ada."""
    closing = MonthlyClosing.query.filter_by(month=month, year=year).first_or_404()
    if closing.is_closed:
        flash("Closing ini sudah dikunci.", "warning")
    else:
        closing.is_closed = True
        closing.closed_by = (
            current_user.username if current_user.is_authenticated else "system"
        )
        closing.closed_at = datetime.utcnow()
        db.session.commit()
        flash(
            f"Closing {closing.get_period_label()} berhasil dikunci! 🔒",
            "success",
        )
    return redirect(url_for("closings.closing_detail", month=month, year=year))


@closings_bp.route("/closing/<int:month>/<int:year>/delete", methods=["POST"])
@login_required
def delete_closing(month, year):
    """Hapus draft closing (hanya jika belum dikunci)."""
    closing = MonthlyClosing.query.filter_by(month=month, year=year).first_or_404()
    if closing.is_closed:
        flash("Closing yang sudah dikunci tidak bisa dihapus.", "danger")
        return redirect(url_for("closings.closing_detail", month=month, year=year))
    label = closing.get_period_label()
    db.session.delete(closing)
    db.session.commit()
    flash(f"Draft closing {label} berhasil dihapus.", "success")
    return redirect(url_for("closings.monthly_closing"))
