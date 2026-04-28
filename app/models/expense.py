"""
Expense model for Dashboard Keuangan LBB Super Smart
Contains Expense model for recording operational expenses
"""

from datetime import datetime

from app import db


class Expense(db.Model):
    """Expense model for operational costs"""

    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    expense_date = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    category = db.Column(
        db.String(50), nullable=False
    )  # iklan, kuota, tarik tunai, alat, dll
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Nominal pengeluaran
    payment_method = db.Column(db.String(50))  # tunai, transfer, kartu kredit, dll
    reference_number = db.Column(db.String(100))  # No struk, no referensi, dll
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    creator = db.relationship("User", backref="expenses_created")

    def __repr__(self):
        return f"<Expense {self.category} - {self.amount}>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "expense_date": self.expense_date.isoformat(),
            "category": self.category,
            "description": self.description,
            "amount": float(self.amount),
            "payment_method": self.payment_method,
            "reference_number": self.reference_number,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
