"""Recruitment CRM models."""

import json
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class RecruitmentCandidate(db.Model):
    """Tutor applicant captured from the recruitment form."""

    __tablename__ = "recruitment_candidates"

    id = db.Column(db.Integer, primary_key=True)
    google_email = db.Column(db.String(160), nullable=False, index=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    address = db.Column(db.Text)
    subject_interest = db.Column(db.String(160))
    teaching_preferences_json = db.Column(db.Text)
    last_education_level = db.Column(db.String(40))
    university_name = db.Column(db.String(160))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    cv_file_path = db.Column(db.String(500))
    photo_file_path = db.Column(db.String(500))
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    meet_link = db.Column(db.String(500))
    interview_notes = db.Column(db.Text)
    contract_text = db.Column(db.Text)
    offering_text = db.Column(db.Text)
    signature_data_url = db.Column(db.Text)
    invited_at = db.Column(db.DateTime)
    interview_agreed_at = db.Column(db.DateTime)
    contract_sent_at = db.Column(db.DateTime)
    signed_at = db.Column(db.DateTime)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.id"), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    tutor = db.relationship("Tutor", backref="recruitment_candidates")

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("recruitment_candidate", self.id)

    @property
    def is_signed(self):
        return bool(self.signed_at and self.signature_data_url)

    def set_password(self, password):
        """Hash and set the candidate dashboard password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check the candidate dashboard password."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def teaching_preferences(self):
        if not self.teaching_preferences_json:
            return []
        try:
            values = json.loads(self.teaching_preferences_json)
        except (TypeError, ValueError):
            return []
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    @teaching_preferences.setter
    def teaching_preferences(self, values):
        cleaned = []
        seen = set()
        for value in values or []:
            label = str(value).strip()
            key = label.lower()
            if label and key not in seen:
                cleaned.append(label)
                seen.add(key)
        self.teaching_preferences_json = json.dumps(cleaned, ensure_ascii=False)
        self.subject_interest = ", ".join(cleaned)[:160] if cleaned else None

    def __repr__(self):
        return f"<RecruitmentCandidate {self.google_email} {self.status}>"
