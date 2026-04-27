"""
Payment models for Dashboard Keuangan LBB Super Smart
Contains StudentPayment and StudentPaymentLine models
"""

from datetime import datetime

from app import db


class StudentPayment(db.Model):
    """Student Payment header model"""

    __tablename__ = "student_payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    receipt_number = db.Column(db.String(50), unique=True, nullable=False)
    payment_method = db.Column(
        db.String(50), nullable=False
    )  # cash, bank_transfer, e_wallet
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    verified_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    payment_lines = db.relationship(
        "StudentPaymentLine",
        backref="payment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<StudentPayment {self.receipt_number}>"

    def get_total_nominal(self):
        """Get total nominal from all payment lines"""
        return sum(line.nominal_amount or 0 for line in self.payment_lines)

    def get_total_tutor_payable(self):
        """Get total tutor payable from all payment lines"""
        return sum(line.tutor_payable_amount or 0 for line in self.payment_lines)

    def get_total_margin(self):
        """Get total margin from all payment lines"""
        return sum(line.margin_amount or 0 for line in self.payment_lines)


class StudentPaymentLine(db.Model):
    """Student Payment line detail model"""

    __tablename__ = "student_payment_lines"

    id = db.Column(db.Integer, primary_key=True)
    student_payment_id = db.Column(
        db.Integer, db.ForeignKey("student_payments.id"), nullable=False, index=True
    )
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey("enrollments.id"), nullable=False, index=True
    )
    service_month = db.Column(db.Date, nullable=False)  # Month when service is provided
    meeting_count = db.Column(db.Integer, nullable=False)  # Number of meetings paid
    student_rate_per_meeting = db.Column(db.Numeric(10, 2), nullable=False)
    tutor_rate_per_meeting = db.Column(db.Numeric(10, 2), nullable=False)
    nominal_amount = db.Column(
        db.Numeric(12, 2), nullable=False
    )  # Total payment amount
    tutor_payable_amount = db.Column(
        db.Numeric(12, 2), nullable=False
    )  # Amount allocated to tutor
    margin_amount = db.Column(
        db.Numeric(12, 2), nullable=False
    )  # Margin for institution
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    enrollment = db.relationship("Enrollment", backref="payment_lines")

    def __repr__(self):
        return f"<StudentPaymentLine payment_id={self.student_payment_id} enrollment_id={self.enrollment_id}>"

    @staticmethod
    def calculate_amounts(meeting_count, student_rate, tutor_rate):
        """
        Calculate payment amounts
        Returns dict with nominal_amount, tutor_payable_amount, margin_amount
        """
        nominal_amount = meeting_count * student_rate
        tutor_payable_amount = meeting_count * tutor_rate
        margin_amount = nominal_amount - tutor_payable_amount

        return {
            "nominal_amount": nominal_amount,
            "tutor_payable_amount": tutor_payable_amount,
            "margin_amount": margin_amount,
        }
