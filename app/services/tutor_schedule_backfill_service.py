"""One-time tutor schedule backfill from January-April attendance."""

from collections import Counter, defaultdict
from datetime import date, datetime, time

from app import db
from app.models import AttendanceSession, Enrollment, EnrollmentSchedule, WhatsAppEvaluation


class TutorScheduleBackfillService:
    """Persist missing tutor schedules from January-April 2026 attendance."""

    DEFAULT_START = date(2026, 1, 1)
    DEFAULT_END = date(2026, 4, 30)
    DEFAULT_START_HOUR = 17
    MAX_HOUR = 21

    @staticmethod
    def _weekday_number(session_date):
        return (session_date.toordinal() - 1) % 7

    @classmethod
    def _latest_review_status_by_session(cls, session_ids):
        if not session_ids:
            return {}
        rows = (
            WhatsAppEvaluation.query.filter(
                WhatsAppEvaluation.attendance_session_id.in_(session_ids)
            )
            .order_by(WhatsAppEvaluation.updated_at.desc(), WhatsAppEvaluation.id.desc())
            .all()
        )
        latest_status = {}
        for row in rows:
            latest_status.setdefault(
                row.attendance_session_id, row.manual_review_status or "pending"
            )
        return latest_status

    @classmethod
    def _is_eligible_session(cls, session, latest_review_status):
        review_status = latest_review_status.get(session.id)
        if review_status is not None:
            return review_status == "valid"
        return session.status == "attended"

    @classmethod
    def _select_enrollment_id(cls, student_sessions):
        enrollment_counts = Counter(session.enrollment_id for session in student_sessions)
        latest_by_enrollment = {
            enrollment_id: max(
                session.session_date
                for session in student_sessions
                if session.enrollment_id == enrollment_id
            )
            for enrollment_id in enrollment_counts
        }
        return max(
            enrollment_counts,
            key=lambda item: (enrollment_counts[item], latest_by_enrollment[item], -item),
        )

    @classmethod
    def _desired_weekdays(cls, student_sessions):
        weeks = defaultdict(set)
        for session in student_sessions:
            if not session.session_date:
                continue
            iso_year, iso_week, _weekday = session.session_date.isocalendar()
            weeks[(iso_year, iso_week)].add(session.session_date)

        weekly_dates = [sorted(dates) for dates in weeks.values() if dates]
        if not weekly_dates:
            return []

        weekly_count_counts = Counter(len(dates) for dates in weekly_dates)
        target_count = max(
            weekly_count_counts,
            key=lambda count: (weekly_count_counts[count], count),
        )

        desired_weekdays = []
        for position in range(target_count):
            position_weekdays = Counter()
            latest_by_weekday = {}
            for dates in weekly_dates:
                if position >= len(dates):
                    continue
                session_date = dates[position]
                weekday = cls._weekday_number(session_date)
                position_weekdays[weekday] += 1
                latest_by_weekday[weekday] = max(
                    latest_by_weekday.get(weekday, session_date),
                    session_date,
                )
            if not position_weekdays:
                continue
            desired_weekdays.append(
                max(
                    position_weekdays,
                    key=lambda weekday: (
                        position_weekdays[weekday],
                        latest_by_weekday[weekday],
                        -weekday,
                    ),
                )
            )
        return desired_weekdays

    @classmethod
    def backfill_from_attendance(cls, start_date=None, end_date=None, commit=True):
        start_date = start_date or cls.DEFAULT_START
        end_date = end_date or cls.DEFAULT_END
        sessions = (
            AttendanceSession.query.join(AttendanceSession.enrollment)
            .filter(
                AttendanceSession.session_date.between(start_date, end_date),
                AttendanceSession.tutor_id.isnot(None),
                AttendanceSession.enrollment_id.isnot(None),
                AttendanceSession.tutor_id == Enrollment.tutor_id,
                Enrollment.status == "active",
                Enrollment.is_active.is_(True),
            )
            .order_by(AttendanceSession.tutor_id.asc(), AttendanceSession.session_date.asc())
            .all()
        )
        latest_review_status = cls._latest_review_status_by_session(
            [session.id for session in sessions]
        )
        buckets = defaultdict(list)
        for session in sessions:
            if not cls._is_eligible_session(session, latest_review_status):
                continue
            enrollment = session.enrollment
            if not enrollment or not enrollment.student:
                continue
            student_key = (enrollment.student.name or "").strip().lower()
            if not student_key:
                student_key = f"student:{enrollment.student_id}"
            buckets[(enrollment.tutor_id, student_key)].append(session)

        eligible_tutor_ids = {tutor_id for tutor_id, _student_key in buckets}
        desired_by_enrollment = {}
        for student_sessions in buckets.values():
            enrollment_id = cls._select_enrollment_id(student_sessions)
            desired_weekdays = cls._desired_weekdays(student_sessions)
            if desired_weekdays:
                desired_by_enrollment[enrollment_id] = desired_weekdays
        active_schedules = (
            EnrollmentSchedule.query.join(Enrollment)
            .filter(EnrollmentSchedule.is_active.is_(True))
            .all()
        )
        occupied_slots = defaultdict(set)
        kept_schedule_counts = Counter()
        deactivated_stale = 0
        now = datetime.utcnow()
        for schedule in active_schedules:
            enrollment = schedule.enrollment
            if not enrollment:
                continue
            last_attended = (
                db.session.query(db.func.max(AttendanceSession.session_date))
                .filter(
                    AttendanceSession.enrollment_id == enrollment.id,
                    AttendanceSession.tutor_id == enrollment.tutor_id,
                    AttendanceSession.status == "attended",
                )
                .scalar()
            )
            if last_attended and last_attended < start_date:
                schedule.is_active = False
                schedule.updated_at = now
                deactivated_stale += 1
                continue
            if enrollment.tutor_id in eligible_tutor_ids:
                desired_counts = Counter(desired_by_enrollment.get(enrollment.id, []))
                keep_key = (enrollment.id, schedule.day_of_week)
                should_keep = (
                    schedule.start_time is not None
                    and desired_counts[schedule.day_of_week] > kept_schedule_counts[keep_key]
                )
                if not should_keep:
                    schedule.is_active = False
                    schedule.updated_at = now
                    deactivated_stale += 1
                    continue
                kept_schedule_counts[keep_key] += 1
            elif schedule.start_time is None:
                continue
            occupied_slots[enrollment.tutor_id].add(
                (schedule.day_of_week, schedule.start_time.hour)
            )

        created = 0
        skipped_existing = 0
        skipped_invalid = 0
        for (tutor_id, _student_key), student_sessions in buckets.items():
            enrollment_id = cls._select_enrollment_id(student_sessions)
            desired_counts = Counter(desired_by_enrollment.get(enrollment_id, []))
            if not desired_counts:
                skipped_invalid += 1
                continue
            missing_created = 0
            for weekday, desired_count in desired_counts.items():
                missing_count = desired_count - kept_schedule_counts[
                    (enrollment_id, weekday)
                ]
                for _index in range(missing_count):
                    hour = cls.DEFAULT_START_HOUR
                    while (weekday, hour) in occupied_slots[tutor_id] and hour < cls.MAX_HOUR:
                        hour += 1
                    if (weekday, hour) in occupied_slots[tutor_id]:
                        skipped_invalid += 1
                        continue

                    db.session.add(
                        EnrollmentSchedule(
                            enrollment_id=enrollment_id,
                            day_of_week=weekday,
                            day_name=EnrollmentSchedule.get_day_name(weekday),
                            start_time=time(hour, 0),
                            end_time=time(hour + 1, 0),
                            is_active=True,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    occupied_slots[tutor_id].add((weekday, hour))
                    kept_schedule_counts[(enrollment_id, weekday)] += 1
                    created += 1
                    missing_created += 1
            if not missing_created:
                skipped_existing += 1

        if commit:
            db.session.commit()
        return {
            "created": created,
            "deactivated_stale": deactivated_stale,
            "skipped_existing": skipped_existing,
            "skipped_invalid": skipped_invalid,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        }
