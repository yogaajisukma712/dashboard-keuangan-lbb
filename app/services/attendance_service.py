"""
Attendance Service for Dashboard Keuangan LBB Super Smart
Handles business logic for attendance/presensi operations
"""

from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from app import db
from app.models import AttendanceSession, Enrollment


class AttendanceService:
    """Service class for attendance operations"""

    @staticmethod
    def record_attendance(enrollment_id, session_date, tutor_fee_amount, notes=None):
        """
        Record a new attendance session

        Args:
            enrollment_id: ID of the enrollment
            session_date: Date of the session
            tutor_fee_amount: Fee amount for tutor
            notes: Optional notes

        Returns:
            AttendanceSession object or None if error
        """
        try:
            enrollment = Enrollment.query.get(enrollment_id)
            if not enrollment:
                return None

            session = AttendanceSession(
                enrollment_id=enrollment_id,
                student_id=enrollment.student_id,
                tutor_id=enrollment.tutor_id,
                session_date=session_date,
                status="attended",
                student_present=True,
                tutor_present=True,
                subject_id=enrollment.subject_id,
                tutor_fee_amount=tutor_fee_amount,
                notes=notes,
            )

            db.session.add(session)
            db.session.commit()
            return session
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_monthly_summary(month, year):
        """
        Get attendance summary for a specific month

        Args:
            month: Month number (1-12)
            year: Year

        Returns:
            Dict with summary data
        """
        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)

        sessions = AttendanceSession.query.filter(
            AttendanceSession.session_date.between(start_date, end_date),
            AttendanceSession.status == "attended",
        ).all()

        total_sessions = len(sessions)
        total_fee = sum(float(s.tutor_fee_amount or 0) for s in sessions)

        # Group by tutor
        tutor_summary = {}
        for session in sessions:
            tutor_id = session.tutor_id
            if tutor_id not in tutor_summary:
                tutor_summary[tutor_id] = {
                    "count": 0,
                    "total_fee": 0,
                    "tutor": session.enrollment.tutor,
                }
            tutor_summary[tutor_id]["count"] += 1
            tutor_summary[tutor_id]["total_fee"] += float(session.tutor_fee_amount or 0)

        return {
            "month": month,
            "year": year,
            "total_sessions": total_sessions,
            "total_fee": total_fee,
            "tutor_summary": tutor_summary,
        }

    @staticmethod
    def get_attendance_by_tutor(tutor_id, month=None, year=None):
        """Get attendance records for specific tutor"""
        if month is None:
            today = datetime.utcnow()
            month = today.month
            year = today.year

        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)

        sessions = AttendanceSession.query.filter(
            AttendanceSession.tutor_id == tutor_id,
            AttendanceSession.session_date.between(start_date, end_date),
            AttendanceSession.status == "attended",
        ).all()

        return sessions

    @staticmethod
    def get_tutor_total_salary(tutor_id, month=None, year=None):
        """Calculate total salary for tutor based on attendance"""
        sessions = AttendanceService.get_attendance_by_tutor(tutor_id, month, year)
        return sum(float(s.tutor_fee_amount or 0) for s in sessions)

    @staticmethod
    def create_bulk_attendance(enrollment_ids, session_date, tutor_fee_amount):
        """
        Create multiple attendance records at once

        Args:
            enrollment_ids: List of enrollment IDs
            session_date: Date of sessions
            tutor_fee_amount: Fee amount for all sessions

        Returns:
            Count of created sessions
        """
        try:
            if isinstance(enrollment_ids, str):
                enrollment_ids = [
                    int(item.strip())
                    for item in enrollment_ids.split(",")
                    if item.strip()
                ]

            count = 0
            for enrollment_id in enrollment_ids:
                if enrollment_id:
                    AttendanceService.record_attendance(
                        int(enrollment_id), session_date, tutor_fee_amount
                    )
                    count += 1
            return count
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_attendance(session_id, **kwargs):
        """Update attendance session"""
        try:
            session = AttendanceSession.query.get(session_id)
            if not session:
                return None

            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            session.updated_at = datetime.utcnow()
            db.session.commit()
            return session
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def cancel_attendance(session_id):
        """Cancel an attendance session"""
        return AttendanceService.update_attendance(session_id, status="cancelled")

    @staticmethod
    def get_enrollment_progress(enrollment_id, month=None, year=None):
        """
        Get progress of enrollment (attended vs remaining meetings)

        Args:
            enrollment_id: ID of enrollment
            month: Month (optional, defaults to current)
            year: Year (optional, defaults to current)

        Returns:
            Dict with progress data
        """
        if month is None:
            today = datetime.utcnow()
            month = today.month
            year = today.year

        enrollment = Enrollment.query.get(enrollment_id)
        if not enrollment:
            return None

        attended = enrollment.get_attendance_count(month)
        remaining = enrollment.get_remaining_meetings(month)

        return {
            "enrollment_id": enrollment_id,
            "student": enrollment.student.name,
            "subject": enrollment.subject.name,
            "quota": enrollment.meeting_quota_per_month,
            "attended": attended,
            "remaining": remaining,
            "progress_percentage": (attended / enrollment.meeting_quota_per_month * 100)
            if enrollment.meeting_quota_per_month > 0
            else 0,
        }
