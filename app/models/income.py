"""
Income models for Dashboard Keuangan LBB Super Smart
Contains OtherIncome model for non-student income
"""

from datetime import datetime

from app import db


class OtherIncome(db.Model):
    """Other income model - Pemasukan lain-lain"""

    __tablename__ = "other_incomes"

    id = db.Column(db.Integer, primary_key=True)
    income_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=False)  # iklan, titipan, koreksi, dll
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    created_by_user = db.relationship("User", backref="other_incomes")

    def __repr__(self):
        return f"<OtherIncome {self.category} - {self.amount}>"

    def get_month(self):
        """Get month from income_date"""
        return self.income_date.month

    def get_year(self):
        """Get year from income_date"""
        return self.income_date.year
