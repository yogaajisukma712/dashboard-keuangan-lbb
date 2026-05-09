"""Models for the self-service tutor portal."""

from datetime import datetime

from app import db


class TutorPortalRequest(db.Model):
    """Admin-reviewed request submitted by a tutor."""

    __tablename__ = "tutor_portal_requests"

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.id"), nullable=False, index=True)
    request_type = db.Column(db.String(40), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    payload_json = db.Column(db.JSON, default=dict)
    notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    tutor = db.relationship("Tutor", backref="portal_requests")
    reviewer = db.relationship("User", backref="reviewed_tutor_portal_requests")

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("tutor_portal_request", self.id)

    def __repr__(self):
        return f"<TutorPortalRequest {self.request_type} {self.status}>"
