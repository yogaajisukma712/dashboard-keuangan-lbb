"""
Payroll models for Dashboard Keuangan LBB Super Smart
Contains TutorPayout and TutorPayoutLine models
"""

from datetime import datetime

from app import db


class TutorPayout(db.Model):
    """
    Tutor Payout model - Header pembayaran gaji tutor
    Satu baris = satu transaksi pembayaran ke tutor
    """

    __tablename__ = "tutor_payouts"

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(
        db.Integer, db.ForeignKey("tutors.id"), nullable=False, index=True
    )
    payout_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    bank_name = db.Column(db.String(50))
    account_number = db.Column(db.String(50))
    payment_method = db.Column(
        db.String(50), default="transfer"
    )  # transfer, cash, check
    reference_number = db.Column(db.String(100))  # No. bukti transfer
    notes = db.Column(db.Text)
    status = db.Column(
        db.String(20), default="completed"
    )  # pending, completed, cancelled
    proof_image = db.Column(db.String(500))  # path relatif ke UPLOAD_FOLDER
    proof_notes = db.Column(db.Text)  # catatan bukti transfer
    whatsapp_last_contact_id = db.Column(db.String(255))
    whatsapp_last_message = db.Column(db.Text)
    whatsapp_last_sent_at = db.Column(db.DateTime)
    whatsapp_last_status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    payout_lines = db.relationship(
        "TutorPayoutLine",
        backref="payout",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TutorPayout {self.id} - {self.amount}>"

    @property
    def public_id(self):
        """Opaque public id for URLs."""
        from app.utils import encode_public_id

        return encode_public_id("tutor_payout", self.id)

    def get_service_months(self):
        """Get all service months in this payout"""
        return [line.service_month for line in self.payout_lines]


class TutorPayoutLine(db.Model):
    """
    Tutor Payout Line model - Detail pembayaran per bulan layanan
    Satu payout bisa mencakup multiple bulan layanan
    """

    __tablename__ = "tutor_payout_lines"

    id = db.Column(db.Integer, primary_key=True)
    tutor_payout_id = db.Column(
        db.Integer, db.ForeignKey("tutor_payouts.id"), nullable=False, index=True
    )
    service_month = db.Column(db.Date, nullable=False)  # Tahun-Bulan layanan
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TutorPayoutLine {self.service_month} - {self.amount}>"

    def get_service_period(self):
        """Get human-readable service period"""
        if self.service_month:
            return self.service_month.strftime("%B %Y")
        return "N/A"
