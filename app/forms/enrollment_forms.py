"""
Enrollment forms for Dashboard Keuangan LBB Super Smart
Forms for creating and editing enrollments
"""

from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField, TextAreaField
from wtforms.fields import SelectField
from wtforms.validators import DataRequired, Optional, ValidationError

from app.models import Curriculum, Enrollment, Level, Student, Subject, Tutor, WhatsAppGroup


class EnrollmentForm(FlaskForm):
    """Form for creating/editing enrollments"""

    student_id = SelectField("Siswa", coerce=int, validators=[DataRequired()])
    subject_id = SelectField("Mata Pelajaran", coerce=int, validators=[DataRequired()])
    tutor_id = SelectField("Tutor", coerce=int, validators=[DataRequired()])
    curriculum_id = SelectField("Kurikulum", coerce=int, validators=[DataRequired()])
    level_id = SelectField("Jenjang", coerce=int, validators=[DataRequired()])
    grade = StringField("Kelas")
    meeting_quota_per_month = IntegerField(
        "Kuota Pertemuan/Bulan", default=4, validators=[DataRequired()]
    )
    student_rate_per_meeting = IntegerField(
        "Tarif Siswa/Pertemuan", validators=[DataRequired()]
    )
    tutor_rate_per_meeting = IntegerField(
        "Tarif Tutor/Pertemuan", validators=[DataRequired()]
    )
    whatsapp_group_db_id = SelectField(
        "Group WhatsApp", coerce=int, default=0, validators=[Optional()]
    )
    notes = TextAreaField("Catatan", validators=[Optional()])
    submit = SubmitField("Simpan")

    def __init__(self, *args, **kwargs):
        super(EnrollmentForm, self).__init__(*args, **kwargs)
        self.student_id.choices = [(s.id, s.name) for s in Student.query.all()]
        self.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
        self.tutor_id.choices = [(t.id, t.name) for t in Tutor.query.all()]
        self.curriculum_id.choices = [(c.id, c.name) for c in Curriculum.query.all()]
        self.level_id.choices = [(l.id, l.name) for l in Level.query.all()]
        self.whatsapp_group_db_id.choices = [(0, "— Tidak pilih group WA —")] + [
            (group.id, group.name)
            for group in WhatsAppGroup.query.order_by(WhatsAppGroup.name.asc()).all()
        ]


class EnrollmentScheduleForm(FlaskForm):
    """Form for creating enrollment schedule"""

    day_of_week = SelectField("Hari", coerce=int, validators=[DataRequired()])
    start_time = StringField("Jam Mulai (HH:MM)", validators=[DataRequired()])
    end_time = StringField("Jam Selesai (HH:MM)", validators=[Optional()])
    location = StringField("Lokasi", validators=[Optional()])
    submit = SubmitField("Simpan")

    def __init__(self, *args, **kwargs):
        super(EnrollmentScheduleForm, self).__init__(*args, **kwargs)
        self.day_of_week.choices = [
            (0, "Senin"),
            (1, "Selasa"),
            (2, "Rabu"),
            (3, "Kamis"),
            (4, "Jumat"),
            (5, "Sabtu"),
            (6, "Minggu"),
        ]
