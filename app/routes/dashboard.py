"""
Dashboard routes for Dashboard Keuangan LBB Super Smart
Contains routes for main dashboard and KPI display
"""

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.services.dashboard_service import DashboardService

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

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


def _parse_month_year(default_today=True):
    """Parse month and year from request args, falling back to current date."""
    today = datetime.utcnow()
    try:
        month = int(request.args.get("month", today.month if default_today else None))
    except (TypeError, ValueError):
        month = today.month
    try:
        year = int(request.args.get("year", today.year if default_today else None))
    except (TypeError, ValueError):
        year = today.year

    # Validate ranges
    month = max(1, min(12, month))
    year = max(2020, min(2099, year))
    return month, year


@dashboard_bp.route("/", methods=["GET"])
@dashboard_bp.route("/owner", methods=["GET"])
@login_required
def owner_dashboard():
    """Main dashboard for owner — supports ?month=M&year=Y query params."""
    try:
        service = DashboardService()
        month, year = _parse_month_year()

        # All KPI data
        student_income = service.get_total_income_this_month(month, year)
        other_income = service.get_other_income_this_month(month, year)
        expenses = service.get_total_expenses_this_month(month, year)
        tutor_payable = service.get_tutor_payable_from_collection(month, year)
        margin = service.get_margin_this_month(month, year)
        salary_accrual = service.get_tutor_salary_accrual(month, year)
        grand_tutor_payable = service.get_grand_tutor_payable(month, year)
        estimated_profit = service.get_estimated_profit(month, year)
        monthly_cash_flow = service.get_monthly_cash_flow(month, year)
        cash_balance = service.get_cash_balance(month, year)
        grand_profit = service.get_grand_profit(month, year)
        estimated_remaining = service.get_estimated_remaining_balance(month, year)
        opening_balance = service.get_opening_balance(month, year)

        kpi_data = {
            "opening_balance": opening_balance,
            "total_income_this_month": student_income,
            "other_income_this_month": other_income,
            "total_pemasukan_bulanan": student_income + other_income,
            "total_expenses_this_month": expenses,
            "tutor_payable_from_collection": tutor_payable,
            "margin_this_month": margin,
            "tutor_salary_accrual": salary_accrual,
            "grand_tutor_payable": grand_tutor_payable,
            "estimated_profit": estimated_profit,
            "monthly_cash_flow": monthly_cash_flow,
            "cash_balance": cash_balance,
            "grand_profit": grand_profit,
            "estimated_remaining_balance": estimated_remaining,
        }

        # Trend data
        trend_data = service.get_monthly_trend(12)

        # Top students and subjects for this month
        top_students = service.get_top_students(month, year, 5)
        top_subjects = service.get_top_subjects(month, year, 5)

        # Build period navigation
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1

        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1

        today = datetime.utcnow()

        return render_template(
            "dashboard/owner_dashboard.html",
            kpi=kpi_data,
            trends=trend_data,
            top_students=top_students,
            top_subjects=top_subjects,
            current_month=month,
            current_year=year,
            current_month_name=MONTH_NAMES.get(month, str(month)),
            prev_month=prev_month,
            prev_year=prev_year,
            next_month=next_month,
            next_year=next_year,
            is_current_period=(month == today.month and year == today.year),
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return render_template("dashboard/owner_dashboard.html", error=str(e)), 500


@dashboard_bp.route("/payroll", methods=["GET"])
@login_required
def payroll_dashboard():
    """Payroll dashboard — supports ?month=M&year=Y."""
    try:
        service = DashboardService()
        month, year = _parse_month_year()

        payroll_summary = service.get_payroll_summary(month, year)
        tutor_details = service.get_tutor_salary_details(month, year)
        unpaid_tutors = service.get_unpaid_tutors(month, year)

        return render_template(
            "dashboard/payroll_dashboard.html",
            payroll_summary=payroll_summary,
            tutor_details=tutor_details,
            unpaid_tutors=unpaid_tutors,
            current_month=month,
            current_year=year,
            current_month_name=MONTH_NAMES.get(month, str(month)),
        )

    except Exception as e:
        return render_template("dashboard/payroll_dashboard.html", error=str(e)), 500


@dashboard_bp.route("/income", methods=["GET"])
@login_required
def income_dashboard():
    """Income dashboard — supports ?month=M&year=Y."""
    try:
        service = DashboardService()
        month, year = _parse_month_year()

        income_by_student = service.get_income_by_student(month, year)
        income_by_subject = service.get_income_by_subject(month, year)
        income_by_curriculum = service.get_income_by_curriculum(month, year)
        income_by_level = service.get_income_by_level(month, year)
        monthly_summary = service.get_monthly_income_summary(month, year)

        return render_template(
            "dashboard/income_dashboard.html",
            income_by_student=income_by_student,
            income_by_subject=income_by_subject,
            income_by_curriculum=income_by_curriculum,
            income_by_level=income_by_level,
            monthly_summary=monthly_summary,
            current_month=month,
            current_year=year,
            current_month_name=MONTH_NAMES.get(month, str(month)),
        )

    except Exception as e:
        return render_template("dashboard/income_dashboard.html", error=str(e)), 500


@dashboard_bp.route("/reconciliation", methods=["GET"])
@login_required
def reconciliation_dashboard():
    """Reconciliation dashboard — supports ?month=M&year=Y."""
    try:
        service = DashboardService()
        month, year = _parse_month_year()

        reconciliation = service.get_reconciliation_data(month, year)
        gap_analysis = service.get_reconciliation_gap_analysis(month, year)
        tutor_reconciliation = service.get_tutor_reconciliation_details(month, year)

        return render_template(
            "dashboard/reconciliation_dashboard.html",
            reconciliation=reconciliation,
            gap_analysis=gap_analysis,
            tutor_reconciliation=tutor_reconciliation,
            current_month=month,
            current_year=year,
            current_month_name=MONTH_NAMES.get(month, str(month)),
        )

    except Exception as e:
        return render_template(
            "dashboard/reconciliation_dashboard.html", error=str(e)
        ), 500


@dashboard_bp.route("/api/kpi/<int:month>/<int:year>", methods=["GET"])
@login_required
def api_get_kpi(month, year):
    """API endpoint to get KPI data for specific month/year"""
    try:
        service = DashboardService()
        student_income = service.get_total_income_this_month(month, year)
        other_income = service.get_other_income_this_month(month, year)
        expenses = service.get_total_expenses_this_month(month, year)

        kpi_data = {
            "opening_balance": float(service.get_opening_balance(month, year) or 0),
            "total_income": float(student_income),
            "other_income": float(other_income),
            "total_pemasukan_bulanan": float(student_income + other_income),
            "total_expenses": float(expenses),
            "tutor_payable": float(
                service.get_tutor_payable_from_collection(month, year) or 0
            ),
            "margin": float(service.get_margin_this_month(month, year) or 0),
            "tutor_salary": float(service.get_tutor_salary_accrual(month, year) or 0),
            "grand_tutor_payable": float(
                service.get_grand_tutor_payable(month, year) or 0
            ),
            "estimated_profit": float(service.get_estimated_profit(month, year) or 0),
            "monthly_cash_flow": float(service.get_monthly_cash_flow(month, year) or 0),
            "cash_balance": float(service.get_cash_balance(month, year) or 0),
            "grand_profit": float(service.get_grand_profit(month, year) or 0),
            "estimated_remaining_balance": float(
                service.get_estimated_remaining_balance(month, year) or 0
            ),
        }
        return jsonify(kpi_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/trend/<int:months>", methods=["GET"])
@login_required
def api_get_trend(months):
    """API endpoint to get trend data for last N months"""
    try:
        service = DashboardService()
        trend_data = service.get_monthly_trend(months)
        return jsonify(trend_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/payroll/<int:month>/<int:year>", methods=["GET"])
@login_required
def api_get_payroll_summary(month, year):
    """API endpoint to get payroll summary for specific month/year"""
    try:
        service = DashboardService()
        payroll_summary = service.get_payroll_summary(month, year)

        result = {
            "total_payable": float(payroll_summary.get("total_payable", 0)),
            "total_paid": float(payroll_summary.get("total_paid", 0)),
            "total_unpaid": float(payroll_summary.get("total_unpaid", 0)),
            "tutor_count": payroll_summary.get("tutor_count", 0),
        }
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
