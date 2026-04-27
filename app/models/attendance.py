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
        "Enrollment", backref="attendance_sessions", lazy="joined"
    )
    tutor = db.relationship("Tutor", backref="attendance_sessions")
    subject = db.relationship("Subject", backref="attendance_sessions")

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

    @property
    def tutor_id(self):
        """Get tutor_id from enrollment"""
        if self.enrollment:
            return self.enrollment.tutor_id
        return None

    @property
    def student_id(self):
        """Get student_id from enrollment"""
        if self.enrollment:
            return self.enrollment.student_id
        return None
