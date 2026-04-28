"""
Dashboard Service for Dashboard Keuangan LBB Super Smart
Handles all KPI calculations and dashboard data aggregation
"""

from datetime import datetime

from sqlalchemy import extract, func

from app import db
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    Expense,
    Level,
    MonthlyClosing,
    OtherIncome,
    Student,
    StudentPayment,
    StudentPaymentLine,
    Subject,
    Tutor,
    TutorPayoutLine,
)


class DashboardService:
    """Service for dashboard calculations and reporting"""

    @staticmethod
    def get_opening_balance(month, year):
        """Get opening cash balance for the month (= previous month closing balance)"""
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1

        prev_closing = MonthlyClosing.query.filter_by(
            month=prev_month, year=prev_year
        ).first()

        if prev_closing:
            return float(prev_closing.closing_cash_balance or 0)

        return 0.0

    @staticmethod
    def get_total_income_this_month(month, year):
        """Get total income from student payments this month"""
        total = (
            db.session.query(func.sum(StudentPaymentLine.nominal_amount))
            .join(StudentPayment)
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_other_income_this_month(month, year):
        """Get other income (non-student) this month"""
        total = (
            db.session.query(func.sum(OtherIncome.amount))
            .filter(
                extract("month", OtherIncome.income_date) == month,
                extract("year", OtherIncome.income_date) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_total_expenses_this_month(month, year):
        """Get total expenses this month"""
        total = (
            db.session.query(func.sum(Expense.amount))
            .filter(
                extract("month", Expense.expense_date) == month,
                extract("year", Expense.expense_date) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_tutor_payable_from_collection(month, year):
        """Get total tutor payable from student payments this month"""
        total = (
            db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
            .join(StudentPayment)
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_margin_this_month(month, year):
        """Get total margin this month"""
        total = (
            db.session.query(func.sum(StudentPaymentLine.margin_amount))
            .join(StudentPayment)
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_tutor_salary_accrual(month, year):
        """Get total tutor salary accrual from attendance this month"""
        total = (
            db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                extract("month", AttendanceSession.session_date) == month,
                extract("year", AttendanceSession.session_date) == year,
                AttendanceSession.status == "attended",
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_grand_tutor_payable(month, year):
        """
        Grand total tutor payable (cumulative up to this month).
        Formula:
          prev_month.closing_tutor_payable  (from MonthlyClosing)
          + current_month tutor_payable_from_collection  (from StudentPaymentLine)

        Per acuan Feb 2025:
          Jan closing_tutor_payable = 3,380,000
          Feb tutor_payable_from_collection = 9,610,000
          Grand Hutang Gaji = 12,990,000
          Grand Profit = Grand Total Saldo (22,900,745) - Grand Hutang Gaji (12,990,000) = 9,910,745

        Payouts are NOT deducted here.
        """
        # Previous month's accumulated tutor payable (from MonthlyClosing)
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1

        prev_closing = MonthlyClosing.query.filter_by(
            month=prev_month, year=prev_year
        ).first()
        prev_payable = (
            float(prev_closing.closing_tutor_payable or 0) if prev_closing else 0
        )

        # Current month's new tutor payable from student payments
        current_payable = DashboardService.get_tutor_payable_from_collection(
            month, year
        )

        return prev_payable + current_payable

    @staticmethod
    def get_estimated_profit(month, year):
        """Get estimated profit this month = margin + other_income - expenses"""
        margin = DashboardService.get_margin_this_month(month, year)
        other_income = DashboardService.get_other_income_this_month(month, year)
        expenses = DashboardService.get_total_expenses_this_month(month, year)
        return margin + other_income - expenses

    @staticmethod
    def get_monthly_cash_flow(month, year):
        """Monthly net cash = income + other_income - expenses (no opening balance).
        Corresponds to 'Saldo Bulan Ini' in the acuan."""
        income = DashboardService.get_total_income_this_month(month, year)
        other = DashboardService.get_other_income_this_month(month, year)
        expenses = DashboardService.get_total_expenses_this_month(month, year)
        return income + other - expenses

    @staticmethod
    def get_cash_balance(month, year):
        """Get grand total saldo = opening + income + other_income - expenses.
        Corresponds to 'Grand Total Saldo' in the acuan."""
        opening = DashboardService.get_opening_balance(month, year)
        income = DashboardService.get_total_income_this_month(month, year)
        other_income = DashboardService.get_other_income_this_month(month, year)
        expenses = DashboardService.get_total_expenses_this_month(month, year)
        return opening + income + other_income - expenses

    @staticmethod
    def get_grand_profit(month, year):
        """Get grand profit = Grand Total Saldo - Grand Hutang Gaji (cumulative tutor payable)"""
        cash_balance = DashboardService.get_cash_balance(month, year)
        tutor_payable = DashboardService.get_grand_tutor_payable(month, year)
        return cash_balance - tutor_payable

    @staticmethod
    def get_estimated_remaining_balance(month, year):
        """Estimasi sisa saldo = Grand Total Saldo - Estimasi Gaji Tutor (accrual)"""
        cash_balance = DashboardService.get_cash_balance(month, year)
        salary_accrual = DashboardService.get_tutor_salary_accrual(month, year)
        return cash_balance - salary_accrual

    @staticmethod
    def _prev_month(month, year):
        """Helper: return (month, year) for N months ago (n=1 = previous)."""
        m = month - 1
        y = year
        if m < 1:
            m = 12
            y -= 1
        return m, y

    @staticmethod
    def get_monthly_trend(num_months):
        """Get trend data for last N months using proper month arithmetic."""
        today = datetime.utcnow()
        trend_data = []

        for i in range(num_months - 1, -1, -1):
            # Compute correct month/year going i months back from today
            month = today.month - i
            year = today.year
            while month <= 0:
                month += 12
                year -= 1

            month_label = datetime(year, month, 1).strftime("%B %Y")
            trend_data.append(
                {
                    "month": month_label,
                    "income": DashboardService.get_total_income_this_month(month, year),
                    "expenses": DashboardService.get_total_expenses_this_month(
                        month, year
                    ),
                    "profit": DashboardService.get_estimated_profit(month, year),
                    "margin": DashboardService.get_margin_this_month(month, year),
                    "tutor_payable": DashboardService.get_tutor_salary_accrual(
                        month, year
                    ),
                }
            )

        return trend_data

    @staticmethod
    def get_top_students(month, year, limit=5):
        """Get top students by income for the given month/year"""
        results = (
            db.session.query(
                Student.id,
                Student.name,
                func.sum(StudentPaymentLine.nominal_amount).label("total_income"),
            )
            .join(StudentPayment, Student.id == StudentPayment.student_id)
            .join(
                StudentPaymentLine,
                StudentPayment.id == StudentPaymentLine.student_payment_id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Student.id, Student.name)
            .order_by(func.sum(StudentPaymentLine.nominal_amount).desc())
            .limit(limit)
            .all()
        )
        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_top_subjects(month, year, limit=5):
        """Get top subjects by income for the given month/year"""
        results = (
            db.session.query(
                Subject.id,
                Subject.name,
                func.sum(StudentPaymentLine.nominal_amount).label("total_income"),
            )
            .join(Enrollment, Subject.id == Enrollment.subject_id)
            .join(StudentPaymentLine, Enrollment.id == StudentPaymentLine.enrollment_id)
            .join(
                StudentPayment,
                StudentPayment.id == StudentPaymentLine.student_payment_id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Subject.id, Subject.name)
            .order_by(func.sum(StudentPaymentLine.nominal_amount).desc())
            .limit(limit)
            .all()
        )
        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_payroll_summary(month, year):
        """Get payroll summary for a specific month"""
        payable = DashboardService.get_tutor_salary_accrual(month, year)

        paid = (
            db.session.query(func.sum(TutorPayoutLine.amount))
            .filter(
                extract("month", TutorPayoutLine.service_month) == month,
                extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )

        tutors = Tutor.query.filter_by(is_active=True).count()

        return {
            "total_payable": float(payable),
            "total_paid": float(paid),
            "total_unpaid": float(payable) - float(paid),
            "tutor_count": tutors,
        }

    @staticmethod
    def get_tutor_salary_details(month, year):
        """Get detailed salary information per tutor"""
        tutors = Tutor.query.filter_by(is_active=True).all()

        details = []
        for tutor in tutors:
            payable = (
                db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
                .filter(
                    AttendanceSession.tutor_id == tutor.id,
                    extract("month", AttendanceSession.session_date) == month,
                    extract("year", AttendanceSession.session_date) == year,
                    AttendanceSession.status == "attended",
                )
                .scalar()
                or 0
            )

            details.append(
                {
                    "tutor_id": tutor.id,
                    "tutor_name": tutor.name,
                    "payable": float(payable),
                }
            )

        return details

    @staticmethod
    def get_unpaid_tutors(month, year):
        """Get tutors with unpaid balance"""
        unpaid = []
        details = DashboardService.get_tutor_salary_details(month, year)
        for detail in details:
            if detail["payable"] > 0:
                unpaid.append(detail)
        return unpaid

    @staticmethod
    def get_income_by_student(month, year):
        """Get income breakdown by student"""
        results = (
            db.session.query(
                Student.id,
                Student.name,
                func.sum(StudentPaymentLine.nominal_amount),
            )
            .join(StudentPayment, Student.id == StudentPayment.student_id)
            .join(
                StudentPaymentLine,
                StudentPayment.id == StudentPaymentLine.student_payment_id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Student.id, Student.name)
            .all()
        )
        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_income_by_subject(month, year):
        """Get income breakdown by subject"""
        results = (
            db.session.query(
                Subject.id,
                Subject.name,
                func.sum(StudentPaymentLine.nominal_amount),
            )
            .join(Enrollment, Subject.id == Enrollment.subject_id)
            .join(StudentPaymentLine, Enrollment.id == StudentPaymentLine.enrollment_id)
            .join(
                StudentPayment,
                StudentPayment.id == StudentPaymentLine.student_payment_id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Subject.id, Subject.name)
            .all()
        )
        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_income_by_curriculum(month, year):
        """Get income breakdown by curriculum (includes curriculum name)"""
        results = (
            db.session.query(
                Curriculum.id,
                Curriculum.name,
                func.sum(StudentPaymentLine.nominal_amount).label("income"),
            )
            .join(Enrollment, Enrollment.id == StudentPaymentLine.enrollment_id)
            .join(Curriculum, Curriculum.id == Enrollment.curriculum_id)
            .join(
                StudentPayment,
                StudentPayment.id == StudentPaymentLine.student_payment_id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Curriculum.id, Curriculum.name)
            .order_by(func.sum(StudentPaymentLine.nominal_amount).desc())
            .all()
        )
        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_income_by_level(month, year):
        """Get income breakdown by level (includes level name)"""
        results = (
            db.session.query(
                Level.id,
                Level.name,
                func.sum(StudentPaymentLine.nominal_amount).label("income"),
            )
            .join(Enrollment, Enrollment.id == StudentPaymentLine.enrollment_id)
            .join(Level, Level.id == Enrollment.level_id)
            .join(
                StudentPayment,
                StudentPayment.id == StudentPaymentLine.student_payment_id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Level.id, Level.name)
            .order_by(func.sum(StudentPaymentLine.nominal_amount).desc())
            .all()
        )
        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_monthly_income_summary(month, year):
        """Get monthly income summary"""
        student_income = DashboardService.get_total_income_this_month(month, year)
        other_income = DashboardService.get_other_income_this_month(month, year)
        return {
            "student_income": student_income,
            "other_income": other_income,
            "total_income": student_income + other_income,
        }

    @staticmethod
    def get_reconciliation_data(month, year):
        """Get reconciliation data comparing payments vs attendance"""
        paid = (
            db.session.query(func.sum(TutorPayoutLine.amount))
            .filter(
                extract("month", TutorPayoutLine.service_month) == month,
                extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )
        return {
            "payable_from_collection": DashboardService.get_tutor_payable_from_collection(
                month, year
            ),
            "accrual_from_attendance": DashboardService.get_tutor_salary_accrual(
                month, year
            ),
            "total_payout": float(paid),
        }

    @staticmethod
    def get_reconciliation_gap_analysis(month, year):
        """Get gap analysis between payment and attendance"""
        reconciliation = DashboardService.get_reconciliation_data(month, year)
        gap = (
            reconciliation["payable_from_collection"]
            - reconciliation["accrual_from_attendance"]
        )
        denom = reconciliation["accrual_from_attendance"]
        return {
            "gap": float(gap),
            "gap_percentage": (float(gap) / float(denom) * 100) if denom > 0 else 0,
        }

    @staticmethod
    def get_tutor_reconciliation_details(month, year):
        """Get reconciliation details per tutor"""
        tutors = Tutor.query.filter_by(is_active=True).all()
        details = []
        for tutor in tutors:
            payable = (
                db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
                .join(
                    StudentPayment,
                    StudentPayment.id == StudentPaymentLine.student_payment_id,
                )
                .join(Enrollment, Enrollment.id == StudentPaymentLine.enrollment_id)
                .filter(
                    Enrollment.tutor_id == tutor.id,
                    extract("month", StudentPayment.payment_date) == month,
                    extract("year", StudentPayment.payment_date) == year,
                )
                .scalar()
                or 0
            )

            accrual = (
                db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
                .filter(
                    AttendanceSession.tutor_id == tutor.id,
                    extract("month", AttendanceSession.session_date) == month,
                    extract("year", AttendanceSession.session_date) == year,
                    AttendanceSession.status == "attended",
                )
                .scalar()
                or 0
            )

            details.append(
                {
                    "tutor_id": tutor.id,
                    "tutor_name": tutor.name,
                    "payable_from_collection": float(payable),
                    "accrual_from_attendance": float(accrual),
                    "gap": float(payable) - float(accrual),
                }
            )

        return details
