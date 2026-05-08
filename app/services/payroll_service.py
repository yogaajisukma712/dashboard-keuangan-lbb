"""
Payroll Service for Dashboard Keuangan LBB Super Smart
Handles all payroll-related business logic
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, extract

from app import db
from app.models import (
    AttendanceSession,
    StudentPaymentLine,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
)


class PayrollService:
    """Service class for payroll operations"""

    @staticmethod
    def get_tutor_attendance_raw(tutor_id, month, year):
        """
        Get raw attendance total (sum of tutor_fee_amount for attended sessions).
        Sumber: AttendanceSession.tutor_fee_amount
        """
        total = (
            db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.tutor_id == tutor_id,
                extract("month", AttendanceSession.session_date) == month,
                extract("year", AttendanceSession.session_date) == year,
                AttendanceSession.status == "attended",
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_tutor_payable_from_attendance(tutor_id, month, year):
        """
        Get payable from attendance sessions.

        Data presensi adalah cerminan payroll — payable selalu dihitung dari
        total sesi yang tercatat di attendance_sessions.
        """
        return PayrollService.get_tutor_attendance_raw(tutor_id, month, year)

    @staticmethod
    def get_tutor_paid_amount(tutor_id, month, year):
        """
        Get total paid to tutor in specific month
        Sumber: TutorPayoutLine.amount
        """
        total = (
            db.session.query(db.func.sum(TutorPayoutLine.amount))
            .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
            .filter(
                TutorPayout.tutor_id == tutor_id,
                extract("month", TutorPayoutLine.service_month) == month,
                extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_tutor_balance(tutor_id, month, year):
        """
        Get unpaid balance for tutor
        Balance = Payable - Paid
        """
        payable = PayrollService.get_tutor_payable_from_attendance(
            tutor_id, month, year
        )
        paid = PayrollService.get_tutor_paid_amount(tutor_id, month, year)
        return payable - paid

    @staticmethod
    def get_all_tutors_summary(month, year):
        """
        Get summary for all tutors in specific month/year
        Returns list of dicts with tutor info and amounts
        """
        tutors = Tutor.query.filter_by(is_active=True).all()
        summary = []

        for tutor in tutors:
            payable = PayrollService.get_tutor_payable_from_attendance(
                tutor.id, month, year
            )
            paid = PayrollService.get_tutor_paid_amount(tutor.id, month, year)
            balance = payable - paid

            summary.append(
                {
                    "tutor_id": tutor.id,
                    "tutor_code": tutor.tutor_code,
                    "tutor_name": tutor.name,
                    "bank_name": tutor.bank_name,
                    "account_number": tutor.bank_account_number,
                    "account_holder": tutor.account_holder_name,
                    "payable": payable,
                    "paid": paid,
                    "balance": balance,
                }
            )

        return summary

    @staticmethod
    def get_unpaid_tutors(month, year):
        """
        Get list of tutors with unpaid balance
        """
        summary = PayrollService.get_all_tutors_summary(month, year)
        return [t for t in summary if t["balance"] > 0]

    @staticmethod
    def create_payout(tutor_id, amount, service_month, payout_date=None, **kwargs):
        """
        Create tutor payout record
        """
        if payout_date is None:
            payout_date = datetime.utcnow()

        try:
            payout = TutorPayout(
                tutor_id=tutor_id,
                payout_date=payout_date,
                amount=Decimal(str(amount)),
                bank_name=kwargs.get("bank_name"),
                account_number=kwargs.get("account_number"),
                payment_method=kwargs.get("payment_method", "transfer"),
                reference_number=kwargs.get("reference_number"),
                notes=kwargs.get("notes"),
                status="completed",
            )

            db.session.add(payout)
            db.session.flush()

            # Create payout line
            payout_line = TutorPayoutLine(
                tutor_payout_id=payout.id,
                service_month=service_month,
                amount=Decimal(str(amount)),
            )

            db.session.add(payout_line)
            db.session.commit()

            return payout
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create payout: {str(e)}")

    @staticmethod
    def mark_as_paid(tutor_id, month, year, amount, **kwargs):
        """
        Mark tutor payment for specific month
        """
        service_month = datetime(year, month, 1).date()
        return PayrollService.create_payout(tutor_id, amount, service_month, **kwargs)

    @staticmethod
    def get_tutor_salary_details(month, year):
        """
        Get detailed salary information per tutor
        Includes: payable, paid, balance, attendance count
        """
        from app.models import Enrollment

        tutors = Tutor.query.filter_by(is_active=True).all()
        details = []

        for tutor in tutors:
            # Get attendance count
            attendance_count = (
                db.session.query(db.func.count(AttendanceSession.id))
                .filter(
                    AttendanceSession.tutor_id == tutor.id,
                    extract("month", AttendanceSession.session_date) == month,
                    extract("year", AttendanceSession.session_date) == year,
                    AttendanceSession.status == "attended",
                )
                .scalar()
                or 0
            )

            payable = PayrollService.get_tutor_payable_from_attendance(
                tutor.id, month, year
            )
            paid = PayrollService.get_tutor_paid_amount(tutor.id, month, year)
            balance = payable - paid

            # Get active enrollments for this tutor
            enrollments_count = Enrollment.query.filter_by(
                tutor_id=tutor.id, status="active"
            ).count()

            details.append(
                {
                    "tutor": tutor,
                    "attendance_count": attendance_count,
                    "enrollments_count": enrollments_count,
                    "payable": payable,
                    "paid": paid,
                    "balance": balance,
                }
            )

        return details

    @staticmethod
    def get_payroll_summary(month, year):
        """
        Get overall payroll summary for the month
        """
        tutors = Tutor.query.filter_by(is_active=True).all()

        total_payable = 0
        total_paid = 0
        tutor_count = 0

        for tutor in tutors:
            payable = PayrollService.get_tutor_payable_from_attendance(
                tutor.id, month, year
            )
            paid = PayrollService.get_tutor_paid_amount(tutor.id, month, year)

            if payable > 0:
                total_payable += payable
                total_paid += paid
                tutor_count += 1

        return {
            "total_payable": total_payable,
            "total_paid": total_paid,
            "total_unpaid": total_payable - total_paid,
            "tutor_count": tutor_count,
        }
