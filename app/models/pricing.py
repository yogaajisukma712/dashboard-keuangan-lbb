"""
Pricing models for Dashboard Keuangan LBB Super Smart
Contains PricingRule model for managing tariff rules
"""

from datetime import datetime

from app import db


class PricingRule(db.Model):
    """Pricing Rule model for managing student and tutor rates"""

    __tablename__ = "pricing_rules"

    id = db.Column(db.Integer, primary_key=True)
    curriculum_id = db.Column(
        db.Integer, db.ForeignKey("curriculums.id"), nullable=True
    )
    level_id = db.Column(db.Integer, db.ForeignKey("levels.id"), nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True)
    grade = db.Column(db.String(20))  # Optional: specific grade

    # Rates
    student_rate_per_meeting = db.Column(
        db.Numeric(12, 2), nullable=False
    )  # Tarif jual ke siswa
    tutor_rate_per_meeting = db.Column(db.Numeric(12, 2), nullable=False)  # Tarif tutor
    default_meeting_quota = db.Column(
        db.Integer, default=4
    )  # Default kuota pertemuan per bulan

    # Status
    is_active = db.Column(db.Boolean, default=True)
    active_from = db.Column(db.DateTime, default=datetime.utcnow)
    active_to = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    curriculum = db.relationship("Curriculum", backref="pricing_rules")
    level = db.relationship("Level", backref="pricing_rules")
    subject = db.relationship("Subject", backref="pricing_rules")

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("pricing_rule", self.id)

    def __repr__(self):
        return f"<PricingRule {self.id}>"

    def get_margin(self):
        """Calculate margin per meeting"""
        return float(self.student_rate_per_meeting - self.tutor_rate_per_meeting)

    def get_margin_percentage(self):
        """Calculate margin percentage"""
        if self.student_rate_per_meeting == 0:
            return 0
        return (self.get_margin() / float(self.student_rate_per_meeting)) * 100

    @classmethod
    def get_active_pricing(cls, curriculum_id=None, level_id=None, subject_id=None):
        """Get active pricing rule based on criteria"""
        query = cls.query.filter_by(is_active=True)

        if curriculum_id:
            query = query.filter_by(curriculum_id=curriculum_id)
        if level_id:
            query = query.filter_by(level_id=level_id)
        if subject_id:
            query = query.filter_by(subject_id=subject_id)

        return query.first()
