"""
Enrollment models for Dashboard Keuangan LBB Super Smart
Contains Enrollment and EnrollmentSchedule models
"""

from datetime import datetime

from app import db


class Enrollment(db.Model):
    """Enrollment model - represents a student taking a subject with a tutor"""

    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.id"), nullable=False)
    curriculum_id = db.Column(
        db.Integer, db.ForeignKey("curriculums.id"), nullable=False
    )
    level_id = db.Column(db.Integer, db.ForeignKey("levels.id"), nullable=False)
    grade = db.Column(db.String(20))  # Grade/kelas
    meeting_quota_per_month = db.Column(db.Integer, default=4)
    student_rate_per_meeting = db.Column(
        db.Numeric(15, 2), nullable=False
    )  # Tarif siswa
    tutor_rate_per_meeting = db.Column(db.Numeric(15, 2), nullable=False)  # Tarif tutor
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="active")  # active, inactive, completed
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    schedules = db.relationship(
        "EnrollmentSchedule",
        backref="enrollment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    attendance_sessions = db.relationship(
        "AttendanceSession",
        backref="enrollment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    payment_lines = db.relationship(
        "StudentPaymentLine",
        backref="enrollment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Enrollment {self.student.name} - {self.subject.name}>"

    def get_attendance_count(self, month=None):
        """Get number of attended sessions"""
        from datetime import datetime as dt

        from dateutil.relativedelta import relativedelta

        if month is None:
            month = dt.utcnow().month

        query = self.attendance_sessions.filter_by(status="attended")

        # Filter by month if needed
        start_date = dt(dt.utcnow().year, month, 1)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)

        query = query.filter(
            AttendanceSession.session_date.between(start_date, end_date)
        )

        return query.count()

    def get_remaining_meetings(self, month=None):
        """Get remaining meetings for this month"""
        attended = self.get_attendance_count(month)
        return max(0, self.meeting_quota_per_month - attended)

    def get_total_payable(self, month=None):
        """Get total payable to tutor from attendance"""
        from datetime import datetime as dt

        from dateutil.relativedelta import relativedelta

        if month is None:
            month = dt.utcnow().month

        query = self.attendance_sessions.filter_by(status="attended")

        start_date = dt(dt.utcnow().year, month, 1)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)

        query = query.filter(
            AttendanceSession.session_date.between(start_date, end_date)
        )

        total = (
            db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
            .filter_by(enrollment_id=self.id, status="attended")
            .scalar()
            or 0
        )

        return float(total)


class EnrollmentSchedule(db.Model):
    """EnrollmentSchedule model - represents recurring lesson schedule"""

    __tablename__ = "enrollment_schedules"

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(
        db.Integer, db.ForeignKey("enrollments.id"), nullable=False
    )
    day_of_week = db.Column(
        db.Integer, nullable=False
    )  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    day_name = db.Column(db.String(20))  # Monday, Tuesday, etc
    start_time = db.Column(db.Time, nullable=False)  # HH:MM:SS
    end_time = db.Column(db.Time)  # HH:MM:SS
    location = db.Column(db.String(255))  # Lokasi les (optional)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<EnrollmentSchedule {self.day_name} {self.start_time}>"

    @staticmethod
    def get_day_name(day_num):
        """Convert day number to day name"""
        days = [
            "Senin",
            "Selasa",
            "Rabu",
            "Kamis",
            "Jumat",
            "Sabtu",
            "Minggu",
        ]
        return days[day_num] if 0 <= day_num <= 6 else "Unknown"


# Import at the end to avoid circular imports
from app.models.attendance import AttendanceSession
from app.models.payment import StudentPaymentLine
