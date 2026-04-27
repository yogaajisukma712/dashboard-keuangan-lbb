"""
Payment Service for Dashboard Keuangan LBB Super Smart
Handles business logic for student payments and margin calculations
"""

from datetime import datetime
from decimal import Decimal

from app import db
from app.models import Enrollment, StudentPayment, StudentPaymentLine


class PaymentService:
    """Service class for payment-related operations"""

    @staticmethod
    def create_payment(
        student_id,
        payment_date,
        receipt_number,
        payment_method,
        total_amount,
        payment_lines_data,
        notes=None,
    ):
        """
        Create a new student payment with multiple payment lines

        Args:
            student_id: ID of student
            payment_date: Date of payment
            receipt_number: Receipt/invoice number
            payment_method: Payment method (cash, transfer, etc)
            total_amount: Total payment amount
            payment_lines_data: List of dicts with enrollment_id, meeting_count
            notes: Optional notes

        Returns:
            StudentPayment object
        """
        try:
            # Create payment header
            payment = StudentPayment(
                student_id=student_id,
                payment_date=payment_date,
                receipt_number=receipt_number,
                payment_method=payment_method,
                total_amount=total_amount,
                notes=notes,
            )

            db.session.add(payment)
            db.session.flush()

            # Create payment lines
            for line_data in payment_lines_data:
                enrollment = Enrollment.query.get(line_data["enrollment_id"])
                if not enrollment:
                    raise ValueError(
                        f"Enrollment {line_data['enrollment_id']} not found"
                    )

                meeting_count = int(line_data["meeting_count"])

                # Calculate amounts
                amounts = StudentPaymentLine.calculate_amounts(
                    meeting_count,
                    float(enrollment.student_rate_per_meeting),
                    float(enrollment.tutor_rate_per_meeting),
                )

                line = StudentPaymentLine(
                    student_payment_id=payment.id,
                    enrollment_id=enrollment.id,
                    service_month=payment_date.date(),
                    meeting_count=meeting_count,
                    student_rate_per_meeting=enrollment.student_rate_per_meeting,
                    tutor_rate_per_meeting=enrollment.tutor_rate_per_meeting,
                    nominal_amount=amounts["nominal_amount"],
                    tutor_payable_amount=amounts["tutor_payable_amount"],
                    margin_amount=amounts["margin_amount"],
                )

                db.session.add(line)

            db.session.commit()
            return payment

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_student_payment_history(student_id, limit=10):
        """Get payment history for a student"""
        return (
            StudentPayment.query.filter_by(student_id=student_id)
            .order_by(StudentPayment.payment_date.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_total_student_income(month, year):
        """Get total income from student payments for specific month/year"""
        from sqlalchemy import extract

        total = (
            db.session.query(db.func.sum(StudentPaymentLine.nominal_amount))
            .join(
                StudentPayment,
                StudentPaymentLine.student_payment_id == StudentPayment.id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .scalar()
            or 0
        )

        return float(total)

    @staticmethod
    def get_total_tutor_payable_from_collection(month, year):
        """Get total tutor payable allocated from student payments"""
        from sqlalchemy import extract

        total = (
            db.session.query(db.func.sum(StudentPaymentLine.tutor_payable_amount))
            .join(
                StudentPayment,
                StudentPaymentLine.student_payment_id == StudentPayment.id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .scalar()
            or 0
        )

        return float(total)

    @staticmethod
    def get_total_margin(month, year):
        """Get total margin from student payments"""
        from sqlalchemy import extract

        total = (
            db.session.query(db.func.sum(StudentPaymentLine.margin_amount))
            .join(
                StudentPayment,
                StudentPaymentLine.student_payment_id == StudentPayment.id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .scalar()
            or 0
        )

        return float(total)

    @staticmethod
    def get_monthly_summary(year, month):
        """Get payment summary for specific month"""
        from sqlalchemy import extract

        payments = StudentPayment.query.filter(
            extract("month", StudentPayment.payment_date) == month,
            extract("year", StudentPayment.payment_date) == year,
        ).all()

        total_amount = sum(float(p.total_amount) for p in payments)
        total_tutor_payable = sum(
            float(line.tutor_payable_amount)
            for p in payments
            for line in p.payment_lines
        )
        total_margin = sum(
            float(line.margin_amount) for p in payments for line in p.payment_lines
        )

        return {
            "payment_count": len(payments),
            "total_amount": total_amount,
            "total_tutor_payable": total_tutor_payable,
            "total_margin": total_margin,
            "payments": payments,
        }

    @staticmethod
    def get_income_by_subject(month, year):
        """Get income breakdown by subject"""
        from sqlalchemy import extract

        result = (
            db.session.query(
                db.func.coalesce(Enrollment.subject_id, 0).label("subject_id"),
                db.func.sum(StudentPaymentLine.nominal_amount).label("total_income"),
                db.func.count(StudentPaymentLine.id).label("count"),
            )
            .join(StudentPaymentLine, StudentPaymentLine.enrollment_id == Enrollment.id)
            .join(
                StudentPayment,
                StudentPaymentLine.student_payment_id == StudentPayment.id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(Enrollment.subject_id)
            .all()
        )

        return result

    @staticmethod
    def get_income_by_student(month, year):
        """Get income breakdown by student"""
        from sqlalchemy import extract

        result = (
            db.session.query(
                StudentPayment.student_id,
                db.func.sum(StudentPaymentLine.nominal_amount).label("total_income"),
                db.func.count(StudentPaymentLine.id).label("payment_count"),
            )
            .join(
                StudentPaymentLine,
                StudentPaymentLine.student_payment_id == StudentPayment.id,
            )
            .filter(
                extract("month", StudentPayment.payment_date) == month,
                extract("year", StudentPayment.payment_date) == year,
            )
            .group_by(StudentPayment.student_id)
            .all()
        )

        return result
