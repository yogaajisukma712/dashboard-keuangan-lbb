"""
Master routes blueprint for Dashboard Keuangan LBB Super Smart
Handles CRUD operations for master data: Students, Tutors, Subjects, Curriculums, Levels, Pricing
"""

from datetime import date
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.forms import (
    CurriculumForm,
    PricingRuleForm,
    StudentForm,
    SubjectForm,
    SubjectTutorAssignmentForm,
    TutorForm,
)
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    EnrollmentSchedule,
    Level,
    PricingRule,
    RecruitmentCandidate,
    Student,
    StudentPayment,
    Subject,
    SubjectTutorAssignment,
    Tutor,
    TutorPayout,
    User,
    WhatsAppTutorValidation,
)
from app.services import BulkImportService, DATASET_DEFINITIONS
from app.utils import admin_required, decode_public_id, get_per_page

master_bp = Blueprint("master", __name__, url_prefix="/master")

SAMPLE_DATA_DIR = Path(__file__).resolve().parents[2] / "Data Input Februari 2025"


def _get_student_by_ref_or_404(student_ref):
    """Resolve opaque student ref to model instance."""
    try:
        student_id = decode_public_id(student_ref, "student")
    except ValueError:
        abort(404)
    return Student.query.get_or_404(student_id)


def _get_tutor_by_ref_or_404(tutor_ref):
    """Resolve opaque tutor ref to model instance."""
    try:
        tutor_id = decode_public_id(tutor_ref, "tutor")
    except ValueError:
        abort(404)
    return Tutor.query.get_or_404(tutor_id)


def _get_subject_by_ref_or_404(subject_ref):
    """Resolve opaque subject ref to model instance."""
    try:
        subject_id = decode_public_id(subject_ref, "subject")
    except ValueError:
        abort(404)
    return Subject.query.get_or_404(subject_id)


def _get_curriculum_by_ref_or_404(curriculum_ref):
    """Resolve opaque curriculum ref to model instance."""
    try:
        curriculum_id = decode_public_id(curriculum_ref, "curriculum")
    except ValueError:
        abort(404)
    return Curriculum.query.get_or_404(curriculum_id)


def _get_level_by_ref_or_404(level_ref):
    """Resolve opaque level ref to model instance."""
    try:
        level_id = decode_public_id(level_ref, "level")
    except ValueError:
        abort(404)
    return Level.query.get_or_404(level_id)


def _get_pricing_by_ref_or_404(pricing_ref):
    """Resolve opaque pricing rule ref to model instance."""
    try:
        pricing_id = decode_public_id(pricing_ref, "pricing_rule")
    except ValueError:
        abort(404)
    return PricingRule.query.get_or_404(pricing_id)


def _build_tutor_teaching_schedule(tutor_id: int):
    weekday_names = {
        0: "Senin",
        1: "Selasa",
        2: "Rabu",
        3: "Kamis",
        4: "Jumat",
        5: "Sabtu",
        6: "Minggu",
    }
    sessions = (
        AttendanceSession.query.join(AttendanceSession.enrollment)
        .filter(
            AttendanceSession.tutor_id == tutor_id,
            Enrollment.status == "active",
            Enrollment.is_active.is_(True),
        )
        .order_by(AttendanceSession.session_date.desc(), AttendanceSession.id.desc())
        .all()
    )

    grouped = {}
    for session in sessions:
        enrollment = session.enrollment
        if enrollment is None or enrollment.student is None or enrollment.subject is None:
            continue
        weekday = session.session_date.weekday()
        day_bucket = grouped.setdefault(
            weekday,
            {"weekday": weekday, "day_name": weekday_names.get(weekday, "Lainnya"), "items": {}},
        )
        key = (enrollment.id, enrollment.subject.name, enrollment.student.name)
        item = day_bucket["items"].setdefault(
            key,
            {
                "subject_name": enrollment.subject.name,
                "student_name": enrollment.student.name,
                "grade": enrollment.grade or "-",
                "enrollment_ref": enrollment.public_id,
                "session_count": 0,
                "latest_session_date": session.session_date,
                "latest_status": session.status,
            },
        )
        item["session_count"] += 1
        if session.session_date > item["latest_session_date"]:
            item["latest_session_date"] = session.session_date
            item["latest_status"] = session.status

    teaching_schedule = []
    for weekday in sorted(grouped):
        bucket = grouped[weekday]
        items = sorted(
            bucket["items"].values(),
            key=lambda item: (item["subject_name"].lower(), item["student_name"].lower()),
        )
        teaching_schedule.append(
            {"weekday": bucket["weekday"], "day_name": bucket["day_name"], "items": items}
        )
    return teaching_schedule


def _short_person_name(name: str | None) -> str:
    parts = (name or "-").split()
    return " ".join(parts[:2]) if parts else "-"


def _build_tutor_weekly_schedule_grid(tutor_id: int | None):
    weekday_names = [
        "Senin",
        "Selasa",
        "Rabu",
        "Kamis",
        "Jumat",
        "Sabtu",
        "Minggu",
    ]
    hour_slots = list(range(8, 22))
    cells = {
        (hour, weekday): {"hour": hour, "weekday": weekday, "items": []}
        for hour in hour_slots
        for weekday in range(7)
    }
    if not tutor_id:
        return {
            "weekday_names": weekday_names,
            "hour_slots": hour_slots,
            "rows": [
                {"hour": hour, "cells": [cells[(hour, weekday)] for weekday in range(7)]}
                for hour in hour_slots
            ],
            "lesson_count": 0,
            "latest_session_date": None,
        }

    latest_session_date = (
        db.session.query(db.func.max(AttendanceSession.session_date))
        .filter(AttendanceSession.tutor_id == tutor_id)
        .scalar()
    )
    latest_by_enrollment = dict(
        db.session.query(
            AttendanceSession.enrollment_id,
            db.func.max(AttendanceSession.session_date),
        )
        .filter(AttendanceSession.tutor_id == tutor_id)
        .group_by(AttendanceSession.enrollment_id)
        .all()
    )
    availability_by_slot = {}
    candidate = (
        RecruitmentCandidate.query.filter_by(tutor_id=tutor_id)
        .order_by(RecruitmentCandidate.signed_at.desc(), RecruitmentCandidate.id.desc())
        .first()
    )
    if candidate:
        for slot in candidate.availability_slots:
            try:
                weekday = int(slot.get("weekday"))
                hour = int(slot.get("hour"))
            except (AttributeError, TypeError, ValueError):
                continue
            state = slot.get("state")
            if weekday in range(7) and hour in hour_slots and state in {
                "available",
                "unavailable",
            }:
                availability_by_slot[(hour, weekday)] = state

    schedules = (
        EnrollmentSchedule.query.join(Enrollment)
        .filter(
            Enrollment.tutor_id == tutor_id,
            Enrollment.status == "active",
            Enrollment.is_active.is_(True),
            EnrollmentSchedule.is_active.is_(True),
        )
        .order_by(
            EnrollmentSchedule.day_of_week.asc(),
            EnrollmentSchedule.start_time.asc(),
            Enrollment.id.asc(),
        )
        .all()
    )

    items = []
    for schedule in schedules:
        enrollment = schedule.enrollment
        if not enrollment or not enrollment.student or not enrollment.subject:
            continue
        hour = schedule.start_time.hour if schedule.start_time else None
        if hour not in hour_slots:
            continue
        last_seen = latest_by_enrollment.get(enrollment.id)
        items.append(
            {
                "weekday": schedule.day_of_week,
                "hour": hour,
                "student_name": enrollment.student.name,
                "student_short_name": _short_person_name(enrollment.student.name),
                "subject_name": enrollment.subject.name,
                "enrollment_ref": enrollment.public_id,
                "latest_session_date": last_seen,
                "is_latest": bool(last_seen and last_seen == latest_session_date),
                "source": "enrollment",
            }
        )

    if not items:
        attendance_rows = (
            AttendanceSession.query.join(AttendanceSession.enrollment)
            .filter(AttendanceSession.tutor_id == tutor_id)
            .order_by(
                AttendanceSession.session_date.desc(),
                AttendanceSession.id.desc(),
            )
            .all()
        )
        used_slots = {weekday: 17 for weekday in range(7)}
        seen_enrollments = set()
        for session in attendance_rows:
            enrollment = session.enrollment
            if not enrollment or not enrollment.student or not enrollment.subject:
                continue
            if enrollment.id in seen_enrollments:
                continue
            seen_enrollments.add(enrollment.id)
            weekday = session.session_date.weekday()
            hour = used_slots.get(weekday, 17)
            if hour not in hour_slots:
                continue
            used_slots[weekday] = hour + 1
            items.append(
                {
                    "weekday": weekday,
                    "hour": hour,
                    "student_name": enrollment.student.name,
                    "student_short_name": _short_person_name(enrollment.student.name),
                    "subject_name": enrollment.subject.name,
                    "enrollment_ref": enrollment.public_id,
                    "latest_session_date": session.session_date,
                    "is_latest": bool(session.session_date == latest_session_date),
                    "source": "attendance",
                }
            )

    for item in items:
        cells[(item["hour"], item["weekday"])]["items"].append(item)

    for cell in cells.values():
        cell["has_latest"] = any(item["is_latest"] for item in cell["items"])
        cell["availability"] = (
            "filled"
            if cell["items"]
            else availability_by_slot.get(
                (cell["hour"], cell["weekday"]),
                "unavailable" if cell["hour"] < 16 else "available",
            )
        )
        cell["items"].sort(
            key=lambda item: (
                item["student_short_name"].lower(),
                item["subject_name"].lower(),
            )
        )

    return {
        "weekday_names": weekday_names,
        "hour_slots": hour_slots,
        "rows": [
            {"hour": hour, "cells": [cells[(hour, weekday)] for weekday in range(7)]}
            for hour in hour_slots
        ],
        "lesson_count": len(items),
        "latest_session_date": latest_session_date,
    }


def _build_tutor_subject_summary(tutor_id: int):
    summary = {}

    enrollments = (
        Enrollment.query.join(Subject, Enrollment.subject_id == Subject.id)
        .filter(Enrollment.tutor_id == tutor_id)
        .all()
    )
    for enrollment in enrollments:
        subject = enrollment.subject
        if subject is None:
            continue
        item = summary.setdefault(
            subject.id,
            {
                "subject_id": subject.id,
                "subject_name": subject.name,
                "subject_ref": subject.public_id,
                "active_enrollment_count": 0,
                "attendance_count": 0,
                "latest_attendance_date": None,
            },
        )
        if enrollment.status == "active" and enrollment.is_active:
            item["active_enrollment_count"] += 1

    attendance_sessions = (
        AttendanceSession.query.join(AttendanceSession.enrollment)
        .filter(AttendanceSession.tutor_id == tutor_id)
        .all()
    )
    for session in attendance_sessions:
        subject = session.subject or (session.enrollment.subject if session.enrollment else None)
        if subject is None:
            continue
        item = summary.setdefault(
            subject.id,
            {
                "subject_id": subject.id,
                "subject_name": subject.name,
                "subject_ref": subject.public_id,
                "active_enrollment_count": 0,
                "attendance_count": 0,
                "latest_attendance_date": None,
            },
        )
        item["attendance_count"] += 1
        latest_attendance_date = item["latest_attendance_date"]
        if latest_attendance_date is None or session.session_date > latest_attendance_date:
            item["latest_attendance_date"] = session.session_date

    return sorted(
        summary.values(),
        key=lambda item: (
            -int(item["attendance_count"]),
            -int(item["active_enrollment_count"]),
            item["subject_name"].lower(),
        ),
    )


def _build_subject_tutor_summary(subject_id: int):
    summary = {}

    enrollments = (
        Enrollment.query.join(Tutor, Enrollment.tutor_id == Tutor.id)
        .filter(Enrollment.subject_id == subject_id)
        .all()
    )
    active_enrollment_counts = {}
    for enrollment in enrollments:
        tutor = enrollment.tutor
        if tutor is None:
            continue
        active_enrollment_counts.setdefault(tutor.id, 0)
        if enrollment.status == "active" and enrollment.is_active:
            active_enrollment_counts[tutor.id] += 1

    attendance_sessions = (
        AttendanceSession.query.join(AttendanceSession.enrollment)
        .filter(
            Enrollment.subject_id == subject_id,
        )
        .all()
    )
    for session in attendance_sessions:
        enrollment = session.enrollment
        session_subject_id = session.subject_id
        enrollment_subject_id = enrollment.subject_id if enrollment else None
        if session_subject_id and session_subject_id != subject_id:
            continue
        if enrollment_subject_id != subject_id:
            continue
        tutor = session.tutor or (session.enrollment.tutor if session.enrollment else None)
        if tutor is None:
            continue
        item = summary.setdefault(
            tutor.id,
            {
                "tutor_id": tutor.id,
                "tutor_name": tutor.name,
                "tutor_ref": tutor.public_id,
                "tutor_code": tutor.tutor_code,
                "active_enrollment_count": active_enrollment_counts.get(tutor.id, 0),
                "attendance_count": 0,
                "latest_attendance_date": None,
                "manual_override": False,
                "manual_source_label": "",
            },
        )
        item["active_enrollment_count"] = active_enrollment_counts.get(tutor.id, 0)
        item["attendance_count"] += 1
        latest_attendance_date = item["latest_attendance_date"]
        if latest_attendance_date is None or session.session_date > latest_attendance_date:
            item["latest_attendance_date"] = session.session_date

    manual_assignments = (
        SubjectTutorAssignment.query.join(Tutor, SubjectTutorAssignment.tutor_id == Tutor.id)
        .filter(SubjectTutorAssignment.subject_id == subject_id)
        .all()
    )
    for assignment in manual_assignments:
        tutor = assignment.tutor
        if tutor is None:
            continue
        if assignment.status == "excluded":
            summary.pop(tutor.id, None)
            continue
        item = summary.setdefault(
            tutor.id,
            {
                "tutor_id": tutor.id,
                "tutor_name": tutor.name,
                "tutor_ref": tutor.public_id,
                "tutor_code": tutor.tutor_code,
                "active_enrollment_count": active_enrollment_counts.get(tutor.id, 0),
                "attendance_count": 0,
                "latest_attendance_date": None,
                "manual_override": True,
                "manual_source_label": (
                    "Scan Presensi/Enrollment"
                    if (assignment.notes or "").startswith("Auto-scanned")
                    else "Manual"
                ),
            },
        )
        item["manual_override"] = True
        item["manual_source_label"] = (
            "Scan Presensi/Enrollment"
            if (assignment.notes or "").startswith("Auto-scanned")
            else "Manual"
        )
        item["active_enrollment_count"] = active_enrollment_counts.get(tutor.id, 0)

    return sorted(
        summary.values(),
        key=lambda item: (
            -int(item["attendance_count"]),
            -int(item["active_enrollment_count"]),
            item["tutor_name"].lower(),
        ),
    )


def _scan_subject_tutors_from_attendance_and_enrollment(subject_id: int):
    """Persist current subject tutors discovered from attendance and enrollments."""
    tutor_ids = set()

    active_enrollments = Enrollment.query.filter(
        Enrollment.subject_id == subject_id,
        Enrollment.status == "active",
        Enrollment.is_active.is_(True),
        Enrollment.tutor_id.isnot(None),
    ).all()
    for enrollment in active_enrollments:
        tutor_ids.add(enrollment.tutor_id)

    attendance_sessions = (
        AttendanceSession.query.join(AttendanceSession.enrollment)
        .filter(Enrollment.subject_id == subject_id)
        .all()
    )
    for session in attendance_sessions:
        enrollment = session.enrollment
        session_subject_id = session.subject_id
        enrollment_subject_id = enrollment.subject_id if enrollment else None
        if session_subject_id and session_subject_id != subject_id:
            continue
        if enrollment_subject_id != subject_id:
            continue
        tutor_id = session.tutor_id or (enrollment.tutor_id if enrollment else None)
        if tutor_id:
            tutor_ids.add(tutor_id)

    created = 0
    updated = 0
    for tutor_id in tutor_ids:
        assignment = SubjectTutorAssignment.query.filter_by(
            subject_id=subject_id,
            tutor_id=tutor_id,
        ).first()
        if assignment:
            assignment.status = "included"
            assignment.notes = "Auto-scanned from attendance/enrollment."
            updated += 1
        else:
            db.session.add(
                SubjectTutorAssignment(
                    subject_id=subject_id,
                    tutor_id=tutor_id,
                    status="included",
                    notes="Auto-scanned from attendance/enrollment.",
                )
            )
            created += 1

    return {"created": created, "updated": updated, "found": len(tutor_ids)}


def _get_bulk_template_map():
    return {
        key: {
            **meta,
            "download_url": url_for("master.download_bulk_template", dataset_key=key),
        }
        for key, meta in DATASET_DEFINITIONS.items()
    }


# ==================== STUDENT ROUTES ====================


@master_bp.route("/students", methods=["GET"])
@login_required
def students_list():
    """List all students"""
    from app.routes.quota_invoice import _first_of_month, _get_student_quota_alert_map

    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    search = request.args.get("search", "", type=str)
    active_state = request.args.get("active_state", "active", type=str).strip().lower()
    sort_by = request.args.get("sort", "name_asc", type=str).strip().lower()

    last_attendance_subquery = (
        db.session.query(
            AttendanceSession.student_id.label("student_id"),
            db.func.max(AttendanceSession.session_date).label("last_attendance_date"),
        )
        .group_by(AttendanceSession.student_id)
        .subquery()
    )
    last_payment_subquery = (
        db.session.query(
            StudentPayment.student_id.label("student_id"),
            db.func.max(StudentPayment.payment_date).label("last_payment_date"),
        )
        .group_by(StudentPayment.student_id)
        .subquery()
    )

    query = (
        Student.query.outerjoin(
            last_attendance_subquery,
            Student.id == last_attendance_subquery.c.student_id,
        )
        .outerjoin(last_payment_subquery, Student.id == last_payment_subquery.c.student_id)
    )

    if search:
        query = query.filter(
            or_(
                Student.name.ilike(f"%{search}%"),
                Student.student_code.ilike(f"%{search}%"),
                Student.email.ilike(f"%{search}%"),
            )
        )

    if active_state == "inactive":
        query = query.filter(Student.is_active.is_(False))
    elif active_state == "all":
        pass
    else:
        active_state = "active"
        query = query.filter(Student.is_active.is_(True))

    sort_options = {
        "name_asc",
        "name_desc",
        "last_attendance_desc",
        "last_attendance_asc",
        "last_payment_desc",
        "last_payment_asc",
    }
    if sort_by not in sort_options:
        sort_by = "name_asc"

    if sort_by == "name_desc":
        query = query.order_by(Student.name.desc(), Student.id.desc())
    elif sort_by == "last_attendance_desc":
        query = query.order_by(
            last_attendance_subquery.c.last_attendance_date.is_(None),
            last_attendance_subquery.c.last_attendance_date.desc(),
            Student.name.asc(),
        )
    elif sort_by == "last_attendance_asc":
        query = query.order_by(
            last_attendance_subquery.c.last_attendance_date.is_(None),
            last_attendance_subquery.c.last_attendance_date.asc(),
            Student.name.asc(),
        )
    elif sort_by == "last_payment_desc":
        query = query.order_by(
            last_payment_subquery.c.last_payment_date.is_(None),
            last_payment_subquery.c.last_payment_date.desc(),
            Student.name.asc(),
        )
    elif sort_by == "last_payment_asc":
        query = query.order_by(
            last_payment_subquery.c.last_payment_date.is_(None),
            last_payment_subquery.c.last_payment_date.asc(),
            Student.name.asc(),
        )
    else:
        query = query.order_by(Student.name.asc(), Student.id.asc())

    students = query.paginate(page=page, per_page=per_page)
    student_ids = [student.id for student in students.items]
    last_attendance_map = dict(
        db.session.query(
            AttendanceSession.student_id,
            db.func.max(AttendanceSession.session_date),
        )
        .filter(AttendanceSession.student_id.in_(student_ids))
        .group_by(AttendanceSession.student_id)
        .all()
    )
    last_payment_map = dict(
        db.session.query(StudentPayment.student_id, db.func.max(StudentPayment.payment_date))
        .filter(StudentPayment.student_id.in_(student_ids))
        .group_by(StudentPayment.student_id)
        .all()
    )
    today = date.today()
    service_month = _first_of_month(today.year, today.month)
    active_student_ids = [
        student.id for student in students.items if bool(student.is_active)
    ]
    quota_alert_map = _get_student_quota_alert_map(active_student_ids, service_month)

    return render_template(
        "master/students_list.html",
        students=students,
        search=search,
        active_state=active_state,
        sort_by=sort_by,
        last_attendance_map=last_attendance_map,
        last_payment_map=last_payment_map,
        quota_alert_map=quota_alert_map,
        quota_alert_month=service_month,
    )


@master_bp.route("/bulk-upload", methods=["GET", "POST"])
@login_required
@admin_required
def bulk_upload():
    """Bulk upload CSV importer page."""
    import_result = None
    selected_dataset = request.form.get("dataset_key", "students")
    selected_service_month = request.form.get("service_month", "")

    if request.method == "POST":
        dataset_key = (request.form.get("dataset_key") or "").strip()
        service_month = (request.form.get("service_month") or "").strip()
        upload = request.files.get("csv_file")
        selected_dataset = dataset_key or selected_dataset
        selected_service_month = service_month

        try:
            importer = BulkImportService(db.session)
            import_result = importer.import_dataset(
                dataset_key=dataset_key,
                file_storage=upload,
                current_user_id=getattr(current_user, "id", None),
                service_month=service_month or None,
            )
            db.session.commit()
            flash(
                f"Import {import_result['dataset_label']} selesai. "
                f"Created: {import_result['created']}, "
                f"Updated: {import_result['updated']}, "
                f"Skipped: {import_result['skipped']}.",
                "success",
            )
        except Exception as exc:
            db.session.rollback()
            flash(f"Gagal import CSV: {exc}", "danger")

    return render_template(
        "master/bulk_upload.html",
        dataset_options=_get_bulk_template_map(),
        selected_dataset=selected_dataset,
        selected_service_month=selected_service_month,
        import_result=import_result,
    )


@master_bp.route("/bulk-upload/template/<string:dataset_key>", methods=["GET"])
@login_required
@admin_required
def download_bulk_template(dataset_key):
    """Download sample CSV template from project folder."""
    meta = DATASET_DEFINITIONS.get(dataset_key)
    if not meta:
        abort(404)

    file_path = SAMPLE_DATA_DIR / meta["sample_file"]
    if not file_path.exists():
        abort(404)

    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@master_bp.route("/students/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_student():
    """Add new student"""
    form = StudentForm()

    if form.validate_on_submit():
        student = Student(
            student_code=form.student_code.data,
            name=form.name.data,
            curriculum_id=form.curriculum_id.data,
            level_id=form.level_id.data,
            grade=form.grade.data,
            phone=form.phone.data,
            email=form.email.data,
            parent_name=form.parent_name.data,
            parent_phone=form.parent_phone.data,
            address=form.address.data,
        )

        db.session.add(student)
        db.session.commit()

        flash(f"Siswa {student.name} berhasil ditambahkan", "success")
        return redirect(url_for("master.students_list"))

    return render_template("master/student_form.html", form=form, action="add")


@master_bp.route("/students/<string:student_ref>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_student(student_ref):
    """Edit student"""
    student = _get_student_by_ref_or_404(student_ref)
    form = StudentForm()

    if form.validate_on_submit():
        student.student_code = form.student_code.data
        student.name = form.name.data
        student.curriculum_id = form.curriculum_id.data
        student.level_id = form.level_id.data
        student.grade = form.grade.data
        student.phone = form.phone.data
        student.email = form.email.data
        student.parent_name = form.parent_name.data
        student.parent_phone = form.parent_phone.data
        student.address = form.address.data

        db.session.commit()

        flash(f"Siswa {student.name} berhasil diperbarui", "success")
        return redirect(url_for("master.students_list"))

    elif request.method == "GET":
        form.student_code.data = student.student_code
        form.name.data = student.name
        form.curriculum_id.data = student.curriculum_id
        form.level_id.data = student.level_id
        form.grade.data = student.grade
        form.phone.data = student.phone
        form.email.data = student.email
        form.parent_name.data = student.parent_name
        form.parent_phone.data = student.parent_phone
        form.address.data = student.address

    return render_template(
        "master/student_form.html", form=form, student=student, action="edit"
    )


@master_bp.route("/students/<string:student_ref>/delete", methods=["POST"])
@login_required
@admin_required
def delete_student(student_ref):
    """Delete student"""
    student = _get_student_by_ref_or_404(student_ref)
    name = student.name

    db.session.delete(student)
    db.session.commit()

    flash(f"Siswa {name} berhasil dihapus", "success")
    return redirect(url_for("master.students_list"))


@master_bp.route("/students/<string:student_ref>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_student_active(student_ref):
    """Toggle active status for a student."""
    student = _get_student_by_ref_or_404(student_ref)
    next_url = request.form.get("next") or url_for(
        "master.student_detail", student_ref=student.public_id
    )

    student.is_active = not bool(student.is_active)
    if student.is_active:
        student.status = "active"
        flash(f"Siswa {student.name} diaktifkan kembali", "success")
    else:
        student.status = "inactive"
        flash(f"Siswa {student.name} dinonaktifkan", "warning")

    db.session.commit()
    return redirect(next_url)


@master_bp.route("/students/bulk-status", methods=["POST"])
@login_required
@admin_required
def bulk_update_student_status():
    """Bulk activate or deactivate selected students."""
    student_refs = request.form.getlist("student_refs")
    bulk_action = (request.form.get("bulk_action") or "").strip()
    next_url = request.form.get("next") or url_for("master.students_list")

    if bulk_action not in {"activate", "deactivate"}:
        flash("Aksi bulk siswa tidak valid.", "danger")
        return redirect(next_url)
    if not student_refs:
        flash("Pilih minimal satu siswa terlebih dahulu.", "warning")
        return redirect(next_url)

    student_ids = []
    for student_ref in student_refs:
        try:
            student_ids.append(decode_public_id(student_ref, "student"))
        except ValueError:
            continue

    if not student_ids:
        flash("Tidak ada siswa valid yang dipilih.", "danger")
        return redirect(next_url)

    target_active = bulk_action == "activate"
    target_status = "active" if target_active else "inactive"
    updated_count = (
        Student.query.filter(Student.id.in_(student_ids))
        .update(
            {
                Student.is_active: target_active,
                Student.status: target_status,
            },
            synchronize_session=False,
        )
    )
    db.session.commit()

    action_label = "diaktifkan" if target_active else "dinonaktifkan"
    flash(f"{updated_count} siswa berhasil {action_label}.", "success")
    return redirect(next_url)


@master_bp.route("/students/<string:student_ref>")
@login_required
def student_detail(student_ref):
    """View student detail"""
    from app.routes.quota_invoice import (
        BILLING_TYPE_LABELS,
        build_postpaid_month_options,
        _build_quota_summary,
        _first_of_month,
        _get_student_invoice_history,
        _get_student_quota_alert_map,
        _get_student_quota_details,
        _month_label,
    )

    student = _get_student_by_ref_or_404(student_ref)
    enrollments = student.enrollments.all()
    payments = student.payments.all()
    today = date.today()
    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)
    service_month = _first_of_month(year, month)
    quota_details = _get_student_quota_details(student.id, service_month)
    quota_summary = _build_quota_summary(quota_details)
    quota_by_enrollment = {
        item["enrollment"].id: item for item in quota_details if item.get("enrollment")
    }
    quota_alert_summary = _get_student_quota_alert_map([student.id], service_month).get(
        student.id
    )
    student_invoices = _get_student_invoice_history(student.id)

    return render_template(
        "master/student_detail.html",
        student=student,
        enrollments=enrollments,
        payments=payments,
        quota_details=quota_details,
        quota_summary=quota_summary,
        quota_by_enrollment=quota_by_enrollment,
        quota_alert_summary=quota_alert_summary,
        service_month=service_month,
        service_month_label=_month_label(service_month),
        postpaid_month_options=build_postpaid_month_options(service_month),
        student_invoices=student_invoices,
        BILLING_TYPE_LABELS=BILLING_TYPE_LABELS,
    )


# ==================== TUTOR ROUTES ====================


@master_bp.route("/tutors", methods=["GET"])
@login_required
def tutors_list():
    """List all tutors"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    search = request.args.get("search", "", type=str)
    active_state = request.args.get("active_state", "active", type=str).strip().lower()

    query = Tutor.query

    if search:
        query = query.filter(
            or_(
                Tutor.name.ilike(f"%{search}%"),
                Tutor.tutor_code.ilike(f"%{search}%"),
                Tutor.email.ilike(f"%{search}%"),
            )
        )

    if active_state == "active":
        query = query.filter(Tutor.is_active.is_(True))
    elif active_state == "inactive":
        query = query.filter(Tutor.is_active.is_(False))
    elif active_state != "all":
        active_state = "active"
        query = query.filter(Tutor.is_active.is_(True))

    tutors = query.paginate(page=page, per_page=per_page)

    return render_template(
        "master/tutors_list.html",
        tutors=tutors,
        search=search,
        active_state=active_state,
    )


@master_bp.route("/tutors/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_tutor():
    """Add new tutor"""
    form = TutorForm()

    if form.validate_on_submit():
        tutor = Tutor(
            tutor_code=form.tutor_code.data,
            name=form.name.data,
            phone=form.phone.data,
            email=form.email.data,
            address=form.address.data,
            identity_type=form.identity_type.data,
            identity_number=form.identity_number.data,
            bank_name=form.bank_name.data,
            bank_account_number=form.bank_account_number.data,
            account_holder_name=form.account_holder_name.data,
        )

        db.session.add(tutor)
        db.session.commit()

        flash(f"Tutor {tutor.name} berhasil ditambahkan", "success")
        return redirect(url_for("master.tutors_list"))

    return render_template("master/tutor_form.html", form=form, action="add")


@master_bp.route("/tutors/<string:tutor_ref>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_tutor(tutor_ref):
    """Edit tutor"""
    tutor = _get_tutor_by_ref_or_404(tutor_ref)
    form = TutorForm()

    if form.validate_on_submit():
        tutor.tutor_code = form.tutor_code.data
        tutor.name = form.name.data
        tutor.phone = form.phone.data
        tutor.email = form.email.data
        tutor.address = form.address.data
        tutor.identity_type = form.identity_type.data
        tutor.identity_number = form.identity_number.data
        tutor.bank_name = form.bank_name.data
        tutor.bank_account_number = form.bank_account_number.data
        tutor.account_holder_name = form.account_holder_name.data

        db.session.commit()

        flash(f"Tutor {tutor.name} berhasil diperbarui", "success")
        return redirect(url_for("master.tutors_list"))

    elif request.method == "GET":
        form.tutor_code.data = tutor.tutor_code
        form.name.data = tutor.name
        form.phone.data = tutor.phone
        form.email.data = tutor.email
        form.address.data = tutor.address
        form.identity_type.data = tutor.identity_type
        form.identity_number.data = tutor.identity_number
        form.bank_name.data = tutor.bank_name
        form.bank_account_number.data = tutor.bank_account_number
        form.account_holder_name.data = tutor.account_holder_name

    return render_template(
        "master/tutor_form.html", form=form, tutor=tutor, action="edit"
    )


@master_bp.route("/tutors/<string:tutor_ref>/delete", methods=["POST"])
@login_required
@admin_required
def delete_tutor(tutor_ref):
    """Delete tutor"""
    tutor = _get_tutor_by_ref_or_404(tutor_ref)
    name = tutor.name

    db.session.delete(tutor)
    db.session.commit()

    flash(f"Tutor {name} berhasil dihapus", "success")
    return redirect(url_for("master.tutors_list"))


@master_bp.route("/tutors/<string:tutor_ref>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_tutor_active(tutor_ref):
    """Toggle active status for a tutor."""
    tutor = _get_tutor_by_ref_or_404(tutor_ref)
    next_url = request.form.get("next") or url_for("master.tutors_list")

    tutor.is_active = not bool(tutor.is_active)
    if tutor.is_active:
        tutor.status = "active"
        flash(f"Tutor {tutor.name} diaktifkan kembali", "success")
    else:
        tutor.status = "inactive"
        flash(f"Tutor {tutor.name} dinonaktifkan", "warning")

    db.session.commit()
    return redirect(next_url)


@master_bp.route("/tutors/bulk-status", methods=["POST"])
@login_required
@admin_required
def bulk_update_tutor_status():
    """Bulk activate or deactivate selected tutors."""
    tutor_refs = request.form.getlist("tutor_refs")
    bulk_action = (request.form.get("bulk_action") or "").strip()
    next_url = request.form.get("next") or url_for("master.tutors_list")

    if bulk_action not in {"activate", "deactivate"}:
        flash("Aksi bulk tutor tidak valid.", "danger")
        return redirect(next_url)
    if not tutor_refs:
        flash("Pilih minimal satu tutor terlebih dahulu.", "warning")
        return redirect(next_url)

    tutor_ids = []
    for tutor_ref in tutor_refs:
        try:
            tutor_ids.append(decode_public_id(tutor_ref, "tutor"))
        except ValueError:
            continue

    if not tutor_ids:
        flash("Tidak ada tutor valid yang dipilih.", "danger")
        return redirect(next_url)

    target_active = bulk_action == "activate"
    target_status = "active" if target_active else "inactive"
    updated_count = (
        Tutor.query.filter(Tutor.id.in_(tutor_ids))
        .update(
            {
                Tutor.is_active: target_active,
                Tutor.status: target_status,
            },
            synchronize_session=False,
        )
    )
    db.session.commit()

    action_label = "diaktifkan" if target_active else "dinonaktifkan"
    flash(f"{updated_count} tutor berhasil {action_label}.", "success")
    return redirect(next_url)


@master_bp.route("/tutors/schedule", methods=["GET"])
@login_required
def tutor_schedule_view():
    """Show one tutor weekly schedule as an hour-by-day grid."""
    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
    tutor_ref = (request.args.get("tutor_ref") or "").strip()
    selected_tutor = None
    if tutor_ref:
        selected_tutor = _get_tutor_by_ref_or_404(tutor_ref)
    elif tutors:
        selected_tutor = tutors[0]

    schedule_grid = _build_tutor_weekly_schedule_grid(
        selected_tutor.id if selected_tutor else None
    )
    return render_template(
        "master/tutor_schedule.html",
        tutors=tutors,
        selected_tutor=selected_tutor,
        selected_tutor_ref=selected_tutor.public_id if selected_tutor else "",
        schedule_grid=schedule_grid,
    )


@master_bp.route("/tutors/<string:tutor_ref>")
@login_required
def tutor_detail(tutor_ref):
    """View tutor detail"""
    tutor = _get_tutor_by_ref_or_404(tutor_ref)
    enrollments = tutor.enrollments.all()
    recent_payouts = tutor.payouts.order_by(TutorPayout.id.desc()).limit(3).all()
    last_payout = recent_payouts[0] if recent_payouts else None
    teaching_schedule = _build_tutor_teaching_schedule(tutor.id)
    schedule_grid = _build_tutor_weekly_schedule_grid(tutor.id)
    taught_subjects = _build_tutor_subject_summary(tutor.id)
    whatsapp_tutor_validation = WhatsAppTutorValidation.query.filter_by(
        tutor_id=tutor.id
    ).first()
    validated_group_memberships = []
    excluded_group_names = []
    if whatsapp_tutor_validation is not None:
        validated_group_memberships = list(
            whatsapp_tutor_validation.group_memberships_json or []
        )
        excluded_group_names = list(
            whatsapp_tutor_validation.excluded_group_names_json or []
        )

    return render_template(
        "master/tutor_detail.html",
        tutor=tutor,
        enrollments=enrollments,
        recent_payouts=recent_payouts,
        last_payout=last_payout,
        teaching_schedule=teaching_schedule,
        schedule_grid=schedule_grid,
        taught_subjects=taught_subjects,
        whatsapp_tutor_validation=whatsapp_tutor_validation,
        validated_group_memberships=validated_group_memberships,
        excluded_group_names=excluded_group_names,
    )


# ==================== SUBJECT ROUTES ====================


@master_bp.route("/subjects", methods=["GET"])
@login_required
def subjects_list():
    """List all subjects"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    subjects = Subject.query.paginate(page=page, per_page=per_page)

    return render_template("master/subjects_list.html", subjects=subjects)


@master_bp.route("/subjects/<string:subject_ref>", methods=["GET"])
@login_required
def subject_detail(subject_ref):
    """View subject detail"""
    subject = _get_subject_by_ref_or_404(subject_ref)
    tutor_assignment_form = SubjectTutorAssignmentForm()
    enrollments = (
        subject.enrollments.join(Student, Enrollment.student_id == Student.id)
        .join(Tutor, Enrollment.tutor_id == Tutor.id)
        .order_by(Enrollment.updated_at.desc(), Enrollment.id.desc())
        .all()
    )
    tutor_summary = _build_subject_tutor_summary(subject.id)

    return render_template(
        "master/subject_detail.html",
        subject=subject,
        enrollments=enrollments,
        tutor_summary=tutor_summary,
        tutor_assignment_form=tutor_assignment_form,
    )


@master_bp.route("/subjects/<string:subject_ref>/tutors/scan", methods=["POST"])
@login_required
@admin_required
def scan_subject_tutors(subject_ref):
    """Refresh subject tutor assignments from attendance and active enrollments."""
    subject = _get_subject_by_ref_or_404(subject_ref)
    result = _scan_subject_tutors_from_attendance_and_enrollment(subject.id)
    db.session.commit()
    flash(
        (
            f"Scan tutor mapel {subject.name} selesai: "
            f"{result['found']} tutor ditemukan, "
            f"{result['created']} baru, {result['updated']} diperbarui."
        ),
        "success",
    )
    return redirect(url_for("master.subject_detail", subject_ref=subject.public_id))


@master_bp.route("/subjects/<string:subject_ref>/tutors/add", methods=["POST"])
@login_required
@admin_required
def add_subject_tutor(subject_ref):
    """Add or re-include tutor on subject detail page."""
    subject = _get_subject_by_ref_or_404(subject_ref)
    form = SubjectTutorAssignmentForm()
    if not form.validate_on_submit():
        flash("Tutor mapel tidak valid.", "danger")
        return redirect(url_for("master.subject_detail", subject_ref=subject.public_id))

    tutor = Tutor.query.get_or_404(form.tutor_id.data)
    assignment = SubjectTutorAssignment.query.filter_by(
        subject_id=subject.id,
        tutor_id=tutor.id,
    ).first()
    if assignment:
        assignment.status = "included"
    else:
        assignment = SubjectTutorAssignment(
            subject_id=subject.id,
            tutor_id=tutor.id,
            status="included",
        )
        db.session.add(assignment)
    db.session.commit()
    flash(f"Tutor {tutor.name} ditambahkan ke mapel {subject.name}.", "success")
    return redirect(url_for("master.subject_detail", subject_ref=subject.public_id))


@master_bp.route("/subjects/<string:subject_ref>/tutors/<string:tutor_ref>/remove", methods=["POST"])
@login_required
@admin_required
def remove_subject_tutor(subject_ref, tutor_ref):
    """Exclude tutor from subject detail page without deleting historical attendance."""
    subject = _get_subject_by_ref_or_404(subject_ref)
    tutor = _get_tutor_by_ref_or_404(tutor_ref)
    assignment = SubjectTutorAssignment.query.filter_by(
        subject_id=subject.id,
        tutor_id=tutor.id,
    ).first()
    if assignment:
        assignment.status = "excluded"
    else:
        assignment = SubjectTutorAssignment(
            subject_id=subject.id,
            tutor_id=tutor.id,
            status="excluded",
            notes="Excluded from subject detail page.",
        )
        db.session.add(assignment)
    db.session.commit()
    flash(f"Tutor {tutor.name} dihapus dari daftar mapel {subject.name}.", "success")
    return redirect(url_for("master.subject_detail", subject_ref=subject.public_id))


@master_bp.route("/subjects/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_subject():
    """Add new subject"""
    form = SubjectForm()

    if form.validate_on_submit():
        subject = Subject(name=form.name.data, description=form.description.data)

        db.session.add(subject)
        db.session.commit()

        flash(f"Mata pelajaran {subject.name} berhasil ditambahkan", "success")
        return redirect(url_for("master.subjects_list"))

    return render_template("master/subject_form.html", form=form, action="add")


@master_bp.route("/subjects/<string:subject_ref>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_subject(subject_ref):
    """Edit subject"""
    subject = _get_subject_by_ref_or_404(subject_ref)
    form = SubjectForm()

    if form.validate_on_submit():
        subject.name = form.name.data
        subject.description = form.description.data

        db.session.commit()

        flash(f"Mata pelajaran {subject.name} berhasil diperbarui", "success")
        return redirect(url_for("master.subjects_list"))

    elif request.method == "GET":
        form.name.data = subject.name
        form.description.data = subject.description

    return render_template(
        "master/subject_form.html", form=form, subject=subject, action="edit"
    )


@master_bp.route("/subjects/<string:subject_ref>/delete", methods=["POST"])
@login_required
@admin_required
def delete_subject(subject_ref):
    """Delete subject"""
    subject = _get_subject_by_ref_or_404(subject_ref)
    name = subject.name

    db.session.delete(subject)
    db.session.commit()

    flash(f"Mata pelajaran {name} berhasil dihapus", "success")
    return redirect(url_for("master.subjects_list"))


# ==================== CURRICULUM ROUTES ====================


@master_bp.route("/curriculums", methods=["GET"])
@login_required
def curriculums_list():
    """List all curriculums"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    curriculums = Curriculum.query.paginate(page=page, per_page=per_page)

    return render_template("master/curriculums_list.html", curriculums=curriculums)


@master_bp.route("/curriculums/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_curriculum():
    """Add new curriculum"""
    form = CurriculumForm()

    if form.validate_on_submit():
        curriculum = Curriculum(name=form.name.data, description=form.description.data)

        db.session.add(curriculum)
        db.session.commit()

        flash(f"Kurikulum {curriculum.name} berhasil ditambahkan", "success")
        return redirect(url_for("master.curriculums_list"))

    return render_template("master/curriculum_form.html", form=form, action="add")


@master_bp.route("/curriculums/<string:curriculum_ref>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_curriculum(curriculum_ref):
    """Edit curriculum"""
    curriculum = _get_curriculum_by_ref_or_404(curriculum_ref)
    form = CurriculumForm()

    if form.validate_on_submit():
        curriculum.name = form.name.data
        curriculum.description = form.description.data

        db.session.commit()

        flash(f"Kurikulum {curriculum.name} berhasil diperbarui", "success")
        return redirect(url_for("master.curriculums_list"))

    elif request.method == "GET":
        form.name.data = curriculum.name
        form.description.data = curriculum.description

    return render_template(
        "master/curriculum_form.html", form=form, curriculum=curriculum, action="edit"
    )


@master_bp.route("/curriculums/<string:curriculum_ref>/delete", methods=["POST"])
@login_required
@admin_required
def delete_curriculum(curriculum_ref):
    """Delete curriculum"""
    curriculum = _get_curriculum_by_ref_or_404(curriculum_ref)
    name = curriculum.name

    db.session.delete(curriculum)
    db.session.commit()

    flash(f"Kurikulum {name} berhasil dihapus", "success")
    return redirect(url_for("master.curriculums_list"))


# ==================== PRICING ROUTES ====================


@master_bp.route("/pricing", methods=["GET"])
@login_required
def pricing_list():
    """List all pricing rules"""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    pricing_rules = PricingRule.query.paginate(page=page, per_page=per_page)

    return render_template("master/pricing_list.html", pricing_rules=pricing_rules)


@master_bp.route("/pricing/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_pricing():
    """Add new pricing rule"""
    form = PricingRuleForm()

    if form.validate_on_submit():
        pricing = PricingRule(
            curriculum_id=form.curriculum_id.data,
            level_id=form.level_id.data,
            subject_id=form.subject_id.data,
            grade=form.grade.data,
            student_rate_per_meeting=form.student_rate_per_meeting.data,
            tutor_rate_per_meeting=form.tutor_rate_per_meeting.data,
            default_meeting_quota=form.default_meeting_quota.data,
        )

        db.session.add(pricing)
        db.session.commit()

        flash("Aturan tarif berhasil ditambahkan", "success")
        return redirect(url_for("master.pricing_list"))

    curriculum_public_ids = {
        str(curriculum.id): curriculum.public_id for curriculum in Curriculum.query.all()
    }
    level_public_ids = {str(level.id): level.public_id for level in Level.query.all()}
    return render_template(
        "master/pricing_form.html",
        form=form,
        action="add",
        curriculum_public_ids=curriculum_public_ids,
        level_public_ids=level_public_ids,
    )


@master_bp.route("/pricing/<string:pricing_ref>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_pricing(pricing_ref):
    """Edit pricing rule"""
    pricing = _get_pricing_by_ref_or_404(pricing_ref)
    form = PricingRuleForm()

    if form.validate_on_submit():
        pricing.curriculum_id = form.curriculum_id.data
        pricing.level_id = form.level_id.data
        pricing.subject_id = form.subject_id.data
        pricing.grade = form.grade.data
        pricing.student_rate_per_meeting = form.student_rate_per_meeting.data
        pricing.tutor_rate_per_meeting = form.tutor_rate_per_meeting.data
        pricing.default_meeting_quota = form.default_meeting_quota.data

        db.session.commit()

        flash("Aturan tarif berhasil diperbarui", "success")
        return redirect(url_for("master.pricing_list"))

    elif request.method == "GET":
        form.curriculum_id.data = pricing.curriculum_id
        form.level_id.data = pricing.level_id
        form.subject_id.data = pricing.subject_id
        form.grade.data = pricing.grade
        form.student_rate_per_meeting.data = pricing.student_rate_per_meeting
        form.tutor_rate_per_meeting.data = pricing.tutor_rate_per_meeting
        form.default_meeting_quota.data = pricing.default_meeting_quota

    curriculum_public_ids = {
        str(curriculum.id): curriculum.public_id for curriculum in Curriculum.query.all()
    }
    level_public_ids = {str(level.id): level.public_id for level in Level.query.all()}
    return render_template(
        "master/pricing_form.html",
        form=form,
        pricing=pricing,
        action="edit",
        curriculum_public_ids=curriculum_public_ids,
        level_public_ids=level_public_ids,
    )


@master_bp.route("/pricing/<string:pricing_ref>/delete", methods=["POST"])
@login_required
@admin_required
def delete_pricing(pricing_ref):
    """Delete pricing rule"""
    pricing = _get_pricing_by_ref_or_404(pricing_ref)

    db.session.delete(pricing)
    db.session.commit()

    flash("Aturan tarif berhasil dihapus", "success")
    return redirect(url_for("master.pricing_list"))


@master_bp.route("/pricing/api/<string:curriculum_ref>/<string:level_ref>", methods=["GET"])
@login_required
def api_get_pricing(curriculum_ref, level_ref):
    """API: Ambil tarif berdasarkan kurikulum dan jenjang untuk autofill enrollment form"""
    curriculum = _get_curriculum_by_ref_or_404(curriculum_ref)
    level = _get_level_by_ref_or_404(level_ref)
    pr = PricingRule.query.filter_by(
        curriculum_id=curriculum.id,
        level_id=level.id,
        is_active=True,
    ).first()
    if pr:
        return jsonify(
            {
                "found": True,
                "student_rate": float(pr.student_rate_per_meeting),
                "student_rate_per_meeting": float(pr.student_rate_per_meeting),
                "tutor_rate": float(pr.tutor_rate_per_meeting),
                "tutor_rate_per_meeting": float(pr.tutor_rate_per_meeting),
                "default_quota": pr.default_meeting_quota,
                "default_meeting_quota": pr.default_meeting_quota,
            }
        )
    return jsonify({"found": False})
