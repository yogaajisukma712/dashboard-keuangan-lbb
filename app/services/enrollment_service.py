"""
Enrollment service for Dashboard Keuangan LBB Super Smart
Contains business logic for enrollment operations
"""

from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from app import db
from app.models import AttendanceSession, Enrollment


class EnrollmentService:
    """Service class for enrollment-related operations"""

    @staticmethod
    def create_enrollment(
        student_id,
        subject_id,
        tutor_id,
        curriculum_id,
        level_id,
        student_rate_per_meeting,
        tutor_rate_per_meeting,
        meeting_quota_per_month=4,
        grade=None,
        notes=None,
    ):
        """
        Create new enrollment

        Args:
            student_id: Student ID
            subject_id: Subject ID
            tutor_id: Tutor ID
            curriculum_id: Curriculum ID
            level_id: Level ID
            student_rate_per_meeting: Rate to charge student per meeting
            tutor_rate_per_meeting: Rate to pay tutor per meeting
            meeting_quota_per_month: Target meetings per month
            grade: Student grade/class
            notes: Additional notes

        Returns:
            Enrollment object if successful, None if failed
        """
        try:
            enrollment = Enrollment(
                student_id=student_id,
                subject_id=subject_id,
                tutor_id=tutor_id,
                curriculum_id=curriculum_id,
                level_id=level_id,
                grade=grade,
                meeting_quota_per_month=meeting_quota_per_month,
                student_rate_per_meeting=student_rate_per_meeting,
                tutor_rate_per_meeting=tutor_rate_per_meeting,
                status="active",
                notes=notes,
            )
            db.session.add(enrollment)
            db.session.commit()
            return enrollment
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_enrollment(enrollment_id, **kwargs):
        """
        Update enrollment

        Args:
            enrollment_id: Enrollment ID to update
            **kwargs: Fields to update

        Returns:
            Updated enrollment object
        """
        try:
            enrollment = Enrollment.query.get(enrollment_id)
            if not enrollment:
                raise ValueError(f"Enrollment {enrollment_id} not found")

            for key, value in kwargs.items():
                if hasattr(enrollment, key):
                    setattr(enrollment, key, value)

            enrollment.updated_at = datetime.utcnow()
            db.session.commit()
            return enrollment
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_enrollment_progress(enrollment_id, month=None, year=None):
        """
        Get enrollment progress for current or specified month

        Args:
            enrollment_id: Enrollment ID
            month: Month (1-12), defaults to current month
            year: Year, defaults to current year

        Returns:
            Dict with attendance count, remaining meetings, etc
        """
        if month is None:
            today = datetime.utcnow()
            month = today.month
            year = today.year
        elif year is None:
            year = datetime.utcnow().year

        enrollment = Enrollment.query.get(enrollment_id)
        if not enrollment:
            return None

        # Count attended sessions this month
        attended_count = AttendanceSession.query.filter(
            AttendanceSession.enrollment_id == enrollment_id,
            AttendanceSession.status == "attended",
            db.extract("month", AttendanceSession.session_date) == month,
            db.extract("year", AttendanceSession.session_date) == year,
        ).count()

        remaining = max(0, enrollment.meeting_quota_per_month - attended_count)

        return {
            "enrollment_id": enrollment_id,
            "quota": enrollment.meeting_quota_per_month,
            "attended": attended_count,
            "remaining": remaining,
            "month": month,
            "year": year,
        }

    @staticmethod
    def calculate_remaining_meetings(enrollment_id, month=None):
        """
        Calculate remaining meetings for this month

        Args:
            enrollment_id: Enrollment ID
            month: Month number (1-12)

        Returns:
            Number of remaining meetings
        """
        progress = EnrollmentService.get_enrollment_progress(enrollment_id, month)
        return progress["remaining"] if progress else 0

    @staticmethod
    def deactivate_enrollment(enrollment_id):
        """
        Deactivate enrollment (mark as completed/inactive)

        Args:
            enrollment_id: Enrollment ID to deactivate

        Returns:
            Updated enrollment
        """
        return EnrollmentService.update_enrollment(
            enrollment_id, status="inactive", end_date=datetime.utcnow()
        )

    @staticmethod
    def get_active_enrollments(student_id=None, tutor_id=None):
        """
        Get active enrollments

        Args:
            student_id: Filter by student (optional)
            tutor_id: Filter by tutor (optional)

        Returns:
            List of active enrollments
        """
        query = Enrollment.query.filter_by(status="active")

        if student_id:
            query = query.filter_by(student_id=student_id)
        if tutor_id:
            query = query.filter_by(tutor_id=tutor_id)

        return query.all()

    @staticmethod
    def get_enrollment_total_payable(enrollment_id, month=None, year=None):
        """
        Calculate total tutor payable for this enrollment in given month

        Args:
            enrollment_id: Enrollment ID
            month: Month number
            year: Year number

        Returns:
            Total payable amount
        """
        if month is None:
            today = datetime.utcnow()
            month = today.month
            year = today.year
        elif year is None:
            year = datetime.utcnow().year

        total = (
            db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.enrollment_id == enrollment_id,
                AttendanceSession.status == "attended",
                db.extract("month", AttendanceSession.session_date) == month,
                db.extract("year", AttendanceSession.session_date) == year,
            )
            .scalar()
            or 0
        )

        return float(total)
