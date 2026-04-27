"""
Master routes blueprint for Dashboard Keuangan LBB Super Smart
Handles CRUD operations for master data: Students, Tutors, Subjects, Curriculums, Levels, Pricing
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_

from app import db
from app.forms import (
    CurriculumForm,
    PricingRuleForm,
    StudentForm,
    SubjectForm,
    TutorForm,
)
from app.models import Curriculum, Level, PricingRule, Student, Subject, Tutor, User
from app.utils import admin_required

master_bp = Blueprint("master", __name__, url_prefix="/master")


# ==================== STUDENT ROUTES ====================


@master_bp.route("/students", methods=["GET"])
@login_required
def students_list():
    """List all students"""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)

    query = Student.query

    if search:
        query = query.filter(
            or_(
                Student.name.ilike(f"%{search}%"),
                Student.student_code.ilike(f"%{search}%"),
                Student.email.ilike(f"%{search}%"),
            )
        )

    students = query.paginate(page=page, per_page=20)

    return render_template(
        "master/students_list.html", students=students, search=search
    )


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


@master_bp.route("/students/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_student(id):
    """Edit student"""
    student = Student.query.get_or_404(id)
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


@master_bp.route("/students/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_student(id):
    """Delete student"""
    student = Student.query.get_or_404(id)
    name = student.name

    db.session.delete(student)
    db.session.commit()

    flash(f"Siswa {name} berhasil dihapus", "success")
    return redirect(url_for("master.students_list"))


@master_bp.route("/students/<int:id>")
@login_required
def student_detail(id):
    """View student detail"""
    student = Student.query.get_or_404(id)
    enrollments = student.enrollments.all()
    payments = student.payments.all()

    return render_template(
        "master/student_detail.html",
        student=student,
        enrollments=enrollments,
        payments=payments,
    )


# ==================== TUTOR ROUTES ====================


@master_bp.route("/tutors", methods=["GET"])
@login_required
def tutors_list():
    """List all tutors"""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)

    query = Tutor.query

    if search:
        query = query.filter(
            or_(
                Tutor.name.ilike(f"%{search}%"),
                Tutor.tutor_code.ilike(f"%{search}%"),
                Tutor.email.ilike(f"%{search}%"),
            )
        )

    tutors = query.paginate(page=page, per_page=20)

    return render_template("master/tutors_list.html", tutors=tutors, search=search)


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


@master_bp.route("/tutors/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_tutor(id):
    """Edit tutor"""
    tutor = Tutor.query.get_or_404(id)
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


@master_bp.route("/tutors/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_tutor(id):
    """Delete tutor"""
    tutor = Tutor.query.get_or_404(id)
    name = tutor.name

    db.session.delete(tutor)
    db.session.commit()

    flash(f"Tutor {name} berhasil dihapus", "success")
    return redirect(url_for("master.tutors_list"))


@master_bp.route("/tutors/<int:id>")
@login_required
def tutor_detail(id):
    """View tutor detail"""
    tutor = Tutor.query.get_or_404(id)
    enrollments = tutor.enrollments.all()

    return render_template(
        "master/tutor_detail.html", tutor=tutor, enrollments=enrollments
    )


# ==================== SUBJECT ROUTES ====================


@master_bp.route("/subjects", methods=["GET"])
@login_required
def subjects_list():
    """List all subjects"""
    page = request.args.get("page", 1, type=int)
    subjects = Subject.query.paginate(page=page, per_page=20)

    return render_template("master/subjects_list.html", subjects=subjects)


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


@master_bp.route("/subjects/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_subject(id):
    """Edit subject"""
    subject = Subject.query.get_or_404(id)
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


@master_bp.route("/subjects/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_subject(id):
    """Delete subject"""
    subject = Subject.query.get_or_404(id)
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
    curriculums = Curriculum.query.paginate(page=page, per_page=20)

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


@master_bp.route("/curriculums/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_curriculum(id):
    """Edit curriculum"""
    curriculum = Curriculum.query.get_or_404(id)
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


@master_bp.route("/curriculums/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_curriculum(id):
    """Delete curriculum"""
    curriculum = Curriculum.query.get_or_404(id)
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
    pricing_rules = PricingRule.query.paginate(page=page, per_page=20)

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

    return render_template("master/pricing_form.html", form=form, action="add")


@master_bp.route("/pricing/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_pricing(id):
    """Edit pricing rule"""
    pricing = PricingRule.query.get_or_404(id)
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

    return render_template(
        "master/pricing_form.html", form=form, pricing=pricing, action="edit"
    )


@master_bp.route("/pricing/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_pricing(id):
    """Delete pricing rule"""
    pricing = PricingRule.query.get_or_404(id)

    db.session.delete(pricing)
    db.session.commit()

    flash("Aturan tarif berhasil dihapus", "success")
    return redirect(url_for("master.pricing_list"))
