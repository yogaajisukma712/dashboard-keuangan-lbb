"""
Closing model for Dashboard Keuangan LBB Super Smart
Contains MonthlyClosing model for monthly financial snapshots
"""

from datetime import datetime

from app import db


class MonthlyClosing(db.Model):
    """Monthly closing/snapshot model"""

    __tablename__ = "monthly_closings"

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)

    # Opening balances
    opening_cash_balance = db.Column(db.Numeric(15, 2), default=0)
    opening_tutor_payable = db.Column(db.Numeric(15, 2), default=0)

    # Closing balances
    closing_cash_balance = db.Column(db.Numeric(15, 2), default=0)
    closing_tutor_payable = db.Column(db.Numeric(15, 2), default=0)
    closing_profit = db.Column(db.Numeric(15, 2), default=0)

    # Summary data
    total_income = db.Column(db.Numeric(15, 2), default=0)
    total_expense = db.Column(db.Numeric(15, 2), default=0)
    total_tutor_salary = db.Column(db.Numeric(15, 2), default=0)
    total_margin = db.Column(db.Numeric(15, 2), default=0)

    # Status
    is_closed = db.Column(db.Boolean, default=False)
    closed_by = db.Column(db.String(120))  # Username yang menutup
    closed_at = db.Column(db.DateTime)

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<MonthlyClosing {self.year}-{self.month:02d}>"

    def get_period_label(self):
        """Get month label"""
        months = {
            1: "Januari",
            2: "Februari",
            3: "Maret",
            4: "April",
            5: "Mei",
            6: "Juni",
            7: "Juli",
            8: "Agustus",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Desember",
        }
        return f"{months.get(self.month, 'Unknown')} {self.year}"
