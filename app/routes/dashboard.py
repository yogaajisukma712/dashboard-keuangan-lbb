"""
Dashboard routes for Dashboard Keuangan LBB Super Smart
Contains routes for main dashboard and KPI display
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.services.dashboard_service import DashboardService

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/", methods=["GET"])
@dashboard_bp.route("/owner", methods=["GET"])
@login_required
def owner_dashboard():
    """
    Main dashboard for owner
    Shows KPI cards and summary charts
    """
    try:
        service = DashboardService()

        # Get current month and year
        today = datetime.utcnow()
        current_month = today.month
        current_year = today.year

        # Get all KPI data
        kpi_data = {
            "opening_balance": service.get_opening_balance(current_month, current_year),
            "total_income_this_month": service.get_total_income_this_month(
                current_month, current_year
            ),
            "total_expenses_this_month": service.get_total_expenses_this_month(
                current_month, current_year
            ),
            "tutor_payable_from_collection": service.get_tutor_payable_from_collection(
                current_month, current_year
            ),
            "margin_this_month": service.get_margin_this_month(
                current_month, current_year
            ),
            "tutor_salary_accrual": service.get_tutor_salary_accrual(
                current_month, current_year
            ),
            "grand_tutor_payable": service.get_grand_tutor_payable(
                current_month, current_year
            ),
            "estimated_profit": service.get_estimated_profit(
                current_month, current_year
            ),
            "cash_balance": service.get_cash_balance(current_month, current_year),
            "grand_profit": service.get_grand_profit(current_month, current_year),
            "estimated_remaining_balance": service.get_estimated_remaining_balance(
                current_month, current_year
            ),
        }

        # Get trend data for charts (last 12 months)
        trend_data = service.get_monthly_trend(12)

        # Get top students
        top_students = service.get_top_students(5)

        # Get top subjects
        top_subjects = service.get_top_subjects(5)

        return render_template(
            "dashboard/owner_dashboard.html",
            kpi=kpi_data,
            trends=trend_data,
            top_students=top_students,
            top_subjects=top_subjects,
            current_month=current_month,
            current_year=current_year,
        )

    except Exception as e:
        return render_template("dashboard/owner_dashboard.html", error=str(e)), 500


@dashboard_bp.route("/payroll", methods=["GET"])
@login_required
def payroll_dashboard():
    """
    Payroll dashboard
    Shows tutor salary information and summary
    """
    try:
        service = DashboardService()

        today = datetime.utcnow()
        current_month = today.month
        current_year = today.year

        # Get payroll summary
        payroll_summary = service.get_payroll_summary(current_month, current_year)

        # Get tutor details
        tutor_details = service.get_tutor_salary_details(current_month, current_year)

        # Get unpaid tutors
        unpaid_tutors = service.get_unpaid_tutors(current_month, current_year)

        return render_template(
            "dashboard/payroll_dashboard.html",
            payroll_summary=payroll_summary,
            tutor_details=tutor_details,
            unpaid_tutors=unpaid_tutors,
            current_month=current_month,
            current_year=current_year,
        )

    except Exception as e:
        return render_template("dashboard/payroll_dashboard.html", error=str(e)), 500


@dashboard_bp.route("/income", methods=["GET"])
@login_required
def income_dashboard():
    """
    Income dashboard
    Shows detailed income information by student, subject, curriculum
    """
    try:
        service = DashboardService()

        today = datetime.utcnow()
        current_month = today.month
        current_year = today.year

        # Get income by student
        income_by_student = service.get_income_by_student(current_month, current_year)

        # Get income by subject
        income_by_subject = service.get_income_by_subject(current_month, current_year)

        # Get income by curriculum
        income_by_curriculum = service.get_income_by_curriculum(
            current_month, current_year
        )

        # Get income by level
        income_by_level = service.get_income_by_level(current_month, current_year)

        # Get monthly income summary
        monthly_summary = service.get_monthly_income_summary(
            current_month, current_year
        )

        return render_template(
            "dashboard/income_dashboard.html",
            income_by_student=income_by_student,
            income_by_subject=income_by_subject,
            income_by_curriculum=income_by_curriculum,
            income_by_level=income_by_level,
            monthly_summary=monthly_summary,
            current_month=current_month,
            current_year=current_year,
        )

    except Exception as e:
        return render_template("dashboard/income_dashboard.html", error=str(e)), 500


@dashboard_bp.route("/reconciliation", methods=["GET"])
@login_required
def reconciliation_dashboard():
    """
    Reconciliation dashboard
    Shows comparison between:
    - Tutor payable from student collection
    - Tutor salary accrual from attendance
    - Actual tutor payout
    - Reconciliation gap
    """
    try:
        service = DashboardService()

        today = datetime.utcnow()
        current_month = today.month
        current_year = today.year

        # Get reconciliation data
        reconciliation = service.get_reconciliation_data(current_month, current_year)

        # Get gap analysis
        gap_analysis = service.get_reconciliation_gap_analysis(
            current_month, current_year
        )

        # Get detail by tutor
        tutor_reconciliation = service.get_tutor_reconciliation_details(
            current_month, current_year
        )

        return render_template(
            "dashboard/reconciliation_dashboard.html",
            reconciliation=reconciliation,
            gap_analysis=gap_analysis,
            tutor_reconciliation=tutor_reconciliation,
            current_month=current_month,
            current_year=current_year,
        )

    except Exception as e:
        return render_template(
            "dashboard/reconciliation_dashboard.html", error=str(e)
        ), 500


@dashboard_bp.route("/api/kpi/<int:month>/<int:year>", methods=["GET"])
@login_required
def api_get_kpi(month, year):
    """
    API endpoint to get KPI data for specific month/year
    Returns JSON response
    """
    try:
        service = DashboardService()

        kpi_data = {
            "opening_balance": float(service.get_opening_balance(month, year) or 0),
            "total_income": float(
                service.get_total_income_this_month(month, year) or 0
            ),
            "total_expenses": float(
                service.get_total_expenses_this_month(month, year) or 0
            ),
            "tutor_payable": float(
                service.get_tutor_payable_from_collection(month, year) or 0
            ),
            "margin": float(service.get_margin_this_month(month, year) or 0),
            "tutor_salary": float(service.get_tutor_salary_accrual(month, year) or 0),
            "profit": float(service.get_estimated_profit(month, year) or 0),
            "cash_balance": float(service.get_cash_balance(month, year) or 0),
            "grand_profit": float(service.get_grand_profit(month, year) or 0),
        }

        return jsonify(kpi_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/trend/<int:months>", methods=["GET"])
@login_required
def api_get_trend(months):
    """
    API endpoint to get trend data for last N months
    """
    try:
        service = DashboardService()
        trend_data = service.get_monthly_trend(months)

        return jsonify(trend_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/payroll/<int:month>/<int:year>", methods=["GET"])
@login_required
def api_get_payroll_summary(month, year):
    """
    API endpoint to get payroll summary for specific month/year
    """
    try:
        service = DashboardService()
        payroll_summary = service.get_payroll_summary(month, year)

        # Convert to JSON-serializable format
        result = {
            "total_payable": float(payroll_summary.get("total_payable", 0)),
            "total_paid": float(payroll_summary.get("total_paid", 0)),
            "total_unpaid": float(payroll_summary.get("total_unpaid", 0)),
            "tutor_count": payroll_summary.get("tutor_count", 0),
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
