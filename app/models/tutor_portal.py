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


class TutorMeetLink(db.Model):
    """Reusable SS Meet link generated from the tutor portal."""

    __tablename__ = "tutor_meet_links"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey("enrollments.id"), nullable=False, index=True
    )
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True, index=True)
    token = db.Column(db.String(96), nullable=False, unique=True, index=True)
    room = db.Column(db.String(255), nullable=False)
    join_url = db.Column(db.Text, nullable=False)
    jitsi_url = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    max_joins = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(40), default="tutor_portal")
    valid_from = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    enrollment = db.relationship("Enrollment", backref="tutor_meet_links")
    tutor = db.relationship("Tutor", backref="meet_links")

    @property
    def is_active(self):
        return self.status == "active" and (
            (self.valid_from is None or self.valid_from <= datetime.utcnow())
            and (self.expires_at is None or self.expires_at > datetime.utcnow())
        )
