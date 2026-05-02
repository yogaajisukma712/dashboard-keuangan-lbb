"""
Attendance Forms for Dashboard Keuangan LBB Super Smart
Contains WTForms for attendance/presensi operations
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, NumberRange, Optional

from app.models import Enrollment, Subject
from app.models import Tutor


class AttendanceSessionForm(FlaskForm):
    """Form for recording attendance session"""

    enrollment_id = SelectField("Enrollment", coerce=int, validators=[DataRequired()])
    tutor_id = SelectField("Tutor Pengajar", coerce=int, validators=[DataRequired()])
    session_date = DateField("Tanggal Sesi", validators=[DataRequired()])
    student_present = BooleanField("Siswa Hadir")
    tutor_present = BooleanField("Tutor Hadir")
    subject_id = SelectField("Mata Pelajaran", coerce=int, validators=[Optional()])
    tutor_fee_amount = DecimalField(
        "Nominal Tutor", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    notes = TextAreaField("Catatan")
    submit = SubmitField("Simpan Presensi")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        enrollments = Enrollment.query.filter_by(status="active").all()
        self.enrollment_id.choices = [
            (
                enrollment.id,
                f"{enrollment.student.name} - {enrollment.subject.name} - {enrollment.tutor.name}",
            )
            for enrollment in enrollments
        ]
        tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
        self.tutor_id.choices = [
            (tutor.id, tutor.name)
            for tutor in tutors
        ]

        self.subject_id.choices = [(0, "-- Ikuti subject dari enrollment --")] + [
            (subject.id, subject.name)
            for subject in Subject.query.filter_by(is_active=True).all()
        ]


class BulkAttendanceForm(FlaskForm):
    """Form for bulk adding attendance"""

    enrollment_ids = StringField(
        "ID Enrollments (comma separated)", validators=[DataRequired()]
    )
    session_date = DateField("Tanggal Sesi", validators=[DataRequired()])
    tutor_fee_amount = DecimalField(
        "Nominal Tutor", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    submit = SubmitField("Simpan Bulk Presensi")
