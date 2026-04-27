"""
Dashboard Service for Dashboard Keuangan LBB Super Smart
Handles all KPI calculations and dashboard data aggregation
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, extract, func

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    Expense,
    MonthlyClosing,
    OtherIncome,
    Student,
    StudentPayment,
    StudentPaymentLine,
    Subject,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
)


class DashboardService:
    """Service for dashboard calculations and reporting"""

    @staticmethod
    def get_opening_balance(month, year):
        """Get opening cash balance for the month"""
        closing = MonthlyClosing.query.filter_by(month=month, year=year).first()
        if closing:
            return float(closing.closing_cash_balance or 0)

        # If no closing exists, check previous month
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
        """Get grand total tutor payable (accumulated from current + previous months - payouts)"""
        # Get all payable from payments
        payable_from_payments = (
            db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
            .join(StudentPayment)
            .filter(
                extract("month", StudentPayment.payment_date) <= month,
                extract("year", StudentPayment.payment_date) <= year,
            )
            .scalar()
            or 0
        )

        # Get all payouts
        total_payouts = (
            db.session.query(func.sum(TutorPayoutLine.amount))
            .filter(
                extract("month", TutorPayoutLine.service_month) <= month,
                extract("year", TutorPayoutLine.service_month) <= year,
            )
            .scalar()
            or 0
        )

        return float(payable_from_payments) - float(total_payouts)

    @staticmethod
    def get_estimated_profit(month, year):
        """Get estimated profit this month"""
        margin = DashboardService.get_margin_this_month(month, year)
        other_income = DashboardService.get_other_income_this_month(month, year)
        expenses = DashboardService.get_total_expenses_this_month(month, year)

        return margin + other_income - expenses

    @staticmethod
    def get_cash_balance(month, year):
        """Get cash balance at end of month"""
        opening = DashboardService.get_opening_balance(month, year)
        income = DashboardService.get_total_income_this_month(month, year)
        other_income = DashboardService.get_other_income_this_month(month, year)
        expenses = DashboardService.get_total_expenses_this_month(month, year)

        return opening + income + other_income - expenses

    @staticmethod
    def get_grand_profit(month, year):
        """Get grand profit (cash balance - grand tutor payable)"""
        cash_balance = DashboardService.get_cash_balance(month, year)
        tutor_payable = DashboardService.get_grand_tutor_payable(month, year)

        return cash_balance - tutor_payable

    @staticmethod
    def get_estimated_remaining_balance(month, year):
        """Get estimated remaining balance (cash balance - monthly tutor salary accrual)"""
        cash_balance = DashboardService.get_cash_balance(month, year)
        salary_accrual = DashboardService.get_tutor_salary_accrual(month, year)

        return cash_balance - salary_accrual

    @staticmethod
    def get_monthly_trend(num_months):
        """Get trend data for last N months"""
        today = datetime.utcnow()
        trend_data = []

        for i in range(num_months - 1, -1, -1):
            date = today - timedelta(days=30 * i)
            month = date.month
            year = date.year

            trend_data.append(
                {
                    "month": date.strftime("%B %Y"),
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
    def get_top_students(limit=5):
        """Get top students by income"""
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
            .group_by(Student.id, Student.name)
            .order_by(func.sum(StudentPaymentLine.nominal_amount).desc())
            .limit(limit)
            .all()
        )

        return [{"id": r[0], "name": r[1], "income": float(r[2] or 0)} for r in results]

    @staticmethod
    def get_top_subjects(limit=5):
        """Get top subjects by income"""
        results = (
            db.session.query(
                Subject.id,
                Subject.name,
                func.sum(StudentPaymentLine.nominal_amount).label("total_income"),
            )
            .join(Enrollment, Subject.id == Enrollment.subject_id)
            .join(StudentPaymentLine, Enrollment.id == StudentPaymentLine.enrollment_id)
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
            .join(StudentPayment)
            .join(StudentPaymentLine)
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
            .join(Enrollment)
            .join(StudentPaymentLine)
            .join(StudentPayment)
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
        """Get income breakdown by curriculum"""
        results = (
            db.session.query(
                func.sum(StudentPaymentLine.nominal_amount),
            )
            .join(Enrollment)
            .join(StudentPaymentLine)
            .join(StudentPayment)
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Enrollment.curriculum_id)
            .all()
        )

        return results

    @staticmethod
    def get_income_by_level(month, year):
        """Get income breakdown by level"""
        results = (
            db.session.query(
                func.sum(StudentPaymentLine.nominal_amount),
            )
            .join(Enrollment)
            .join(StudentPaymentLine)
            .join(StudentPayment)
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Enrollment.level_id)
            .all()
        )

        return results

    @staticmethod
    def get_monthly_income_summary(month, year):
        """Get monthly income summary"""
        return {
            "student_income": DashboardService.get_total_income_this_month(month, year),
            "other_income": DashboardService.get_other_income_this_month(month, year),
            "total_income": DashboardService.get_total_income_this_month(month, year)
            + DashboardService.get_other_income_this_month(month, year),
        }

    @staticmethod
    def get_reconciliation_data(month, year):
        """Get reconciliation data comparing payments vs attendance"""
        return {
            "payable_from_collection": DashboardService.get_tutor_payable_from_collection(
                month, year
            ),
            "accrual_from_attendance": DashboardService.get_tutor_salary_accrual(
                month, year
            ),
            "total_payout": (
                db.session.query(func.sum(TutorPayoutLine.amount))
                .filter(
                    extract("month", TutorPayoutLine.service_month) == month,
                    extract("year", TutorPayoutLine.service_month) == year,
                )
                .scalar()
                or 0
            ),
        }

    @staticmethod
    def get_reconciliation_gap_analysis(month, year):
        """Get gap analysis between payment and attendance"""
        reconciliation = DashboardService.get_reconciliation_data(month, year)
        gap = (
            reconciliation["payable_from_collection"]
            - reconciliation["accrual_from_attendance"]
        )

        return {
            "gap": float(gap),
            "gap_percentage": (
                (gap / reconciliation["accrual_from_attendance"] * 100)
                if reconciliation["accrual_from_attendance"] > 0
                else 0
            ),
        }

    @staticmethod
    def get_tutor_reconciliation_details(month, year):
        """Get reconciliation details per tutor"""
        tutors = Tutor.query.filter_by(is_active=True).all()

        details = []
        for tutor in tutors:
            payable = (
                db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
                .join(StudentPayment)
                .join(Enrollment)
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
