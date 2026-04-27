"""
Reporting Service for Dashboard Keuangan LBB Super Smart
Handles report generation and data aggregation
"""

from datetime import datetime
from decimal import Decimal

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    Expense,
    OtherIncome,
    StudentPayment,
    StudentPaymentLine,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
)


class ReportingService:
    """Service for generating reports and aggregations"""

    def get_monthly_report(self, month, year):
        """Get comprehensive monthly report"""
        try:
            # Get income data
            total_student_income = self._get_total_student_income(month, year)
            total_other_income = self._get_total_other_income(month, year)
            total_income = total_student_income + total_other_income

            # Get expense data
            total_expenses = self._get_total_expenses(month, year)

            # Get tutor data
            total_tutor_payable = self._get_total_tutor_payable(month, year)
            total_tutor_paid = self._get_total_tutor_paid(month, year)

            # Calculate margin and profit
            margin = total_student_income - total_tutor_payable
            profit = margin + total_other_income - total_expenses

            return {
                "month": month,
                "year": year,
                "total_student_income": float(total_student_income),
                "total_other_income": float(total_other_income),
                "total_income": float(total_income),
                "total_expenses": float(total_expenses),
                "total_tutor_payable": float(total_tutor_payable),
                "total_tutor_paid": float(total_tutor_paid),
                "margin": float(margin),
                "profit": float(profit),
            }
        except Exception as e:
            raise Exception(f"Error generating monthly report: {str(e)}")

    def get_tutor_report(self, month, year):
        """Get tutor payroll report"""
        try:
            tutors = Tutor.query.filter_by(is_active=True).all()
            tutor_data = []

            for tutor in tutors:
                payable = self._get_tutor_payable(tutor.id, month, year)
                paid = self._get_tutor_paid(tutor.id, month, year)
                balance = payable - paid

                tutor_data.append(
                    {
                        "tutor_id": tutor.id,
                        "tutor_name": tutor.name,
                        "bank_name": tutor.bank_name,
                        "account_number": tutor.bank_account_number,
                        "payable": float(payable),
                        "paid": float(paid),
                        "balance": float(balance),
                    }
                )

            return {
                "month": month,
                "year": year,
                "tutor_data": tutor_data,
                "total_payable": sum(t["payable"] for t in tutor_data),
                "total_paid": sum(t["paid"] for t in tutor_data),
                "total_balance": sum(t["balance"] for t in tutor_data),
            }
        except Exception as e:
            raise Exception(f"Error generating tutor report: {str(e)}")

    def get_student_report(self, month, year):
        """Get student income report"""
        try:
            # Get all student payments for the month
            payments = (
                StudentPayment.query.filter(
                    db.extract("month", StudentPayment.payment_date) == month,
                    db.extract("year", StudentPayment.payment_date) == year,
                )
                .order_by(StudentPayment.student_id)
                .all()
            )

            student_data = {}
            for payment in payments:
                student_id = payment.student_id
                if student_id not in student_data:
                    student_data[student_id] = {
                        "student_id": student_id,
                        "student_name": payment.student.name,
                        "total_amount": Decimal(0),
                        "total_margin": Decimal(0),
                        "total_tutor_payable": Decimal(0),
                        "payment_count": 0,
                    }

                for line in payment.payment_lines:
                    student_data[student_id]["total_amount"] += (
                        line.nominal_amount or Decimal(0)
                    )
                    student_data[student_id]["total_margin"] += (
                        line.margin_amount or Decimal(0)
                    )
                    student_data[student_id]["total_tutor_payable"] += (
                        line.tutor_payable_amount or Decimal(0)
                    )
                    student_data[student_id]["payment_count"] += 1

            # Convert to list and format
            result = [
                {
                    "student_id": data["student_id"],
                    "student_name": data["student_name"],
                    "total_amount": float(data["total_amount"]),
                    "total_margin": float(data["total_margin"]),
                    "total_tutor_payable": float(data["total_tutor_payable"]),
                    "payment_count": data["payment_count"],
                }
                for data in student_data.values()
            ]

            return {
                "month": month,
                "year": year,
                "student_data": result,
                "total_amount": sum(s["total_amount"] for s in result),
                "total_margin": sum(s["total_margin"] for s in result),
                "student_count": len(result),
            }
        except Exception as e:
            raise Exception(f"Error generating student report: {str(e)}")

    def export_to_excel(self, report_type, month, year):
        """Export report to Excel file"""
        # TODO: Implement Excel export
        pass

    def export_to_pdf(self, report_type, month, year):
        """Export report to PDF file"""
        # TODO: Implement PDF export
        pass

    # ==================== Private Helper Methods ====================

    def _get_total_student_income(self, month, year):
        """Get total income from student payments"""
        total = db.session.query(db.func.sum(StudentPaymentLine.nominal_amount)).join(
            StudentPayment,
            StudentPaymentLine.student_payment_id == StudentPayment.id,
        ).filter(
            db.extract("month", StudentPayment.payment_date) == month,
            db.extract("year", StudentPayment.payment_date) == year,
        ).scalar() or Decimal(0)
        return total

    def _get_total_other_income(self, month, year):
        """Get total other income"""
        total = db.session.query(db.func.sum(OtherIncome.amount)).filter(
            db.extract("month", OtherIncome.income_date) == month,
            db.extract("year", OtherIncome.income_date) == year,
        ).scalar() or Decimal(0)
        return total

    def _get_total_expenses(self, month, year):
        """Get total expenses"""
        total = db.session.query(db.func.sum(Expense.amount)).filter(
            db.extract("month", Expense.expense_date) == month,
            db.extract("year", Expense.expense_date) == year,
        ).scalar() or Decimal(0)
        return total

    def _get_total_tutor_payable(self, month, year):
        """Get total tutor payable from attendance"""
        total = db.session.query(
            db.func.sum(AttendanceSession.tutor_fee_amount)
        ).filter(
            db.extract("month", AttendanceSession.session_date) == month,
            db.extract("year", AttendanceSession.session_date) == year,
            AttendanceSession.status == "attended",
        ).scalar() or Decimal(0)
        return total

    def _get_total_tutor_paid(self, month, year):
        """Get total tutor paid"""
        total = db.session.query(db.func.sum(TutorPayoutLine.amount)).join(
            TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id
        ).filter(
            db.extract("month", TutorPayoutLine.service_month) == month,
            db.extract("year", TutorPayoutLine.service_month) == year,
        ).scalar() or Decimal(0)
        return total

    def _get_tutor_payable(self, tutor_id, month, year):
        """Get payable amount for specific tutor"""
        total = db.session.query(
            db.func.sum(AttendanceSession.tutor_fee_amount)
        ).filter(
            AttendanceSession.tutor_id == tutor_id,
            db.extract("month", AttendanceSession.session_date) == month,
            db.extract("year", AttendanceSession.session_date) == year,
            AttendanceSession.status == "attended",
        ).scalar() or Decimal(0)
        return total

    def _get_tutor_paid(self, tutor_id, month, year):
        """Get paid amount for specific tutor"""
        total = db.session.query(db.func.sum(TutorPayoutLine.amount)).join(
            TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id
        ).filter(
            TutorPayout.tutor_id == tutor_id,
            db.extract("month", TutorPayoutLine.service_month) == month,
            db.extract("year", TutorPayoutLine.service_month) == year,
        ).scalar() or Decimal(0)
        return total
