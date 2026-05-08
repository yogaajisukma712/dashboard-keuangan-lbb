"""
Attendance model for Dashboard Keuangan LBB Super Smart
Contains AttendanceSession model for tracking les sessions
"""

from datetime import datetime

from app import db


class AttendanceSession(db.Model):
    """Attendance/Presensi model - tracks each lesson session"""

    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey("enrollments.id"), nullable=False, index=True
    )
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    tutor_id = db.Column(
        db.Integer, db.ForeignKey("tutors.id"), nullable=False, index=True
    )
    session_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(
        db.String(20),
        default="scheduled",
        nullable=False,
    )  # scheduled, attended, cancelled, rescheduled
    student_present = db.Column(db.Boolean, default=False)
    tutor_present = db.Column(db.Boolean, default=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True)
    tutor_fee_amount = db.Column(db.Numeric(15, 2), default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    enrollment = db.relationship(
        "Enrollment", back_populates="attendance_sessions", lazy="joined"
    )
    student = db.relationship("Student", backref="attendance_sessions")
    tutor = db.relationship("Tutor", back_populates="attendance_sessions")
    subject = db.relationship("Subject", back_populates="attendance_sessions")

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("attendance_session", self.id)

    def __repr__(self):
        return f"<AttendanceSession {self.id} - {self.session_date}>"

    def mark_attended(self):
        """Mark session as attended"""
        self.status = "attended"
        self.student_present = True
        self.tutor_present = True
        self.updated_at = datetime.utcnow()

    def mark_cancelled(self):
        """Mark session as cancelled"""
        self.status = "cancelled"
        self.updated_at = datetime.utcnow()

    def get_month(self):
        """Get month from session date"""
        return self.session_date.month

    def get_year(self):
        """Get year from session date"""
        return self.session_date.year


class AttendancePeriodLock(db.Model):
    """Monthly lock that prevents WhatsApp rescans from mutating attendance."""

    __tablename__ = "attendance_period_locks"
    __table_args__ = (
        db.UniqueConstraint("month", "year", name="uq_attendance_period_locks_month_year"),
    )

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    notes = db.Column(db.Text)
    locked_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    locked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship("User", backref="attendance_period_locks")

    @property
    def label(self):
        return f"{self.month:02d}/{self.year}"
