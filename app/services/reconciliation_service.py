"""
Reconciliation Service for Dashboard Keuangan LBB Super Smart
Handles reconciliation between student payments and tutor attendance
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import extract, func

from app import db
from app.models import (
    AttendanceSession,
    StudentPaymentLine,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
)


class ReconciliationService:
    """Service for reconciliation operations"""

    @staticmethod
    def get_payable_from_collection(month, year):
        """
        Get total tutor payable amount from student collections
        This is the hutang gaji that was allocated when students paid
        """
        total = (
            db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
            .filter(
                extract("month", StudentPaymentLine.created_at) == month,
                extract("year", StudentPaymentLine.created_at) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_accrual_from_attendance(month, year):
        """
        Get total tutor salary accrual from attendance sessions
        This is based on actual sesi les yang terlaksana
        """
        total = (
            db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.status == "attended",
                extract("month", AttendanceSession.session_date) == month,
                extract("year", AttendanceSession.session_date) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_total_payout(month, year):
        """
        Get total tutor payout that has been paid
        """
        total = (
            db.session.query(func.sum(TutorPayoutLine.amount))
            .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
            .filter(
                extract("month", TutorPayoutLine.service_month) == month,
                extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )
        return float(total)

    @staticmethod
    def get_reconciliation_gap_analysis(month, year):
        """
        Get reconciliation gap analysis
        Returns gap between payable from collection and accrual from attendance
        """
        payable_from_collection = ReconciliationService.get_payable_from_collection(
            month, year
        )
        accrual_from_attendance = ReconciliationService.get_accrual_from_attendance(
            month, year
        )
        total_payout = ReconciliationService.get_total_payout(month, year)

        gap = payable_from_collection - accrual_from_attendance

        return {
            "payable_from_collection": payable_from_collection,
            "accrual_from_attendance": accrual_from_attendance,
            "total_payout": total_payout,
            "gap": gap,
            "gap_percentage": (
                (gap / payable_from_collection * 100)
                if payable_from_collection > 0
                else 0
            ),
        }

    @staticmethod
    def get_tutor_reconciliation(tutor_id, month, year):
        """
        Get reconciliation data for specific tutor
        """
        # Payable from student collections for this tutor
        payable_from_collection = (
            db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
            .join(
                AttendanceSession,
                StudentPaymentLine.enrollment_id == AttendanceSession.enrollment_id,
            )
            .filter(
                AttendanceSession.tutor_id == tutor_id,
                extract("month", StudentPaymentLine.created_at) == month,
                extract("year", StudentPaymentLine.created_at) == year,
            )
            .scalar()
            or 0
        )

        # Accrual from attendance for this tutor
        accrual_from_attendance = (
            db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.tutor_id == tutor_id,
                AttendanceSession.status == "attended",
                extract("month", AttendanceSession.session_date) == month,
                extract("year", AttendanceSession.session_date) == year,
            )
            .scalar()
            or 0
        )

        # Payout for this tutor
        payout = (
            db.session.query(func.sum(TutorPayoutLine.amount))
            .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
            .filter(
                TutorPayout.tutor_id == tutor_id,
                extract("month", TutorPayoutLine.service_month) == month,
                extract("year", TutorPayoutLine.service_month) == year,
            )
            .scalar()
            or 0
        )

        gap = float(payable_from_collection) - float(accrual_from_attendance)

        return {
            "tutor_id": tutor_id,
            "payable_from_collection": float(payable_from_collection),
            "accrual_from_attendance": float(accrual_from_attendance),
            "payout": float(payout),
            "gap": gap,
        }

    @staticmethod
    def get_all_tutor_reconciliation(month, year):
        """
        Get reconciliation data for all tutors
        """
        tutors = Tutor.query.filter_by(is_active=True).all()

        tutor_reconciliation = []
        for tutor in tutors:
            rec = ReconciliationService.get_tutor_reconciliation(tutor.id, month, year)
            if (
                rec["payable_from_collection"] > 0
                or rec["accrual_from_attendance"] > 0
                or rec["payout"] > 0
            ):
                rec["tutor_name"] = tutor.name
                tutor_reconciliation.append(rec)

        return tutor_reconciliation
