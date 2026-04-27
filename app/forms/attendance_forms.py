"""
Attendance Forms for Dashboard Keuangan LBB Super Smart
Contains WTForms for attendance/presensi operations
"""

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, NumberRange, Optional


class AttendanceSessionForm(FlaskForm):
    """Form for recording attendance session"""

    enrollment_id = SelectField("Enrollment", coerce=int, validators=[DataRequired()])
    session_date = DateField("Tanggal Sesi", validators=[DataRequired()])
    student_present = BooleanField("Siswa Hadir")
    tutor_present = BooleanField("Tutor Hadir")
    subject_id = SelectField("Mata Pelajaran", coerce=int, validators=[Optional()])
    tutor_fee_amount = DecimalField(
        "Nominal Tutor", places=2, validators=[DataRequired(), NumberRange(min=0)]
    )
    notes = TextAreaField("Catatan")
    submit = SubmitField("Simpan Presensi")


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
