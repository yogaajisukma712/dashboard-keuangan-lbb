"""
Master forms for Dashboard Keuangan LBB Super Smart
Contains WTForms for Student, Tutor, Subject, Curriculum, Level, and Pricing
"""

from flask_wtf import FlaskForm
from wtforms import (
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

from app.models import Curriculum, Level, Subject, Tutor


class StudentForm(FlaskForm):
    """Form for creating/editing student"""

    _nullable_int = staticmethod(
        lambda value: int(value) if value not in (None, "", "None") else None
    )

    student_code = StringField(
        "Kode Siswa", validators=[DataRequired(), Length(min=3, max=50)]
    )
    name = StringField(
        "Nama Siswa", validators=[DataRequired(), Length(min=3, max=120)]
    )
    curriculum_id = SelectField(
        "Kurikulum", coerce=_nullable_int, validators=[Optional()]
    )
    level_id = SelectField("Jenjang", coerce=_nullable_int, validators=[Optional()])
    grade = StringField("Kelas", validators=[Optional(), Length(max=20)])
    phone = StringField("No. Telepon", validators=[Optional(), Length(max=20)])
    email = StringField("Email", validators=[Optional(), Email()])
    parent_name = StringField(
        "Nama Orang Tua", validators=[Optional(), Length(max=120)]
    )
    parent_phone = StringField(
        "No. Telepon Orang Tua", validators=[Optional(), Length(max=20)]
    )
    address = TextAreaField("Alamat", validators=[Optional()])
    submit = SubmitField("Simpan")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curriculum_id.choices = [(None, "-- Pilih Kurikulum --")] + [
            (c.id, c.name) for c in Curriculum.query.order_by(Curriculum.name).all()
        ]
        self.level_id.choices = [(None, "-- Pilih Jenjang --")] + [
            (l.id, l.name) for l in Level.query.order_by(Level.name).all()
        ]


class TutorForm(FlaskForm):
    """Form for creating/editing tutor"""

    tutor_code = StringField(
        "Kode Tutor", validators=[DataRequired(), Length(min=3, max=50)]
    )
    name = StringField(
        "Nama Tutor", validators=[DataRequired(), Length(min=3, max=120)]
    )
    phone = StringField("No. Telepon", validators=[Optional(), Length(max=20)])
    email = StringField("Email", validators=[Optional(), Email()])
    address = TextAreaField("Alamat", validators=[Optional()])
    identity_type = SelectField(
        "Jenis Identitas",
        choices=[("KTP", "KTP"), ("SIM", "SIM"), ("Passport", "Passport")],
        validators=[Optional()],
    )
    identity_number = StringField(
        "No. Identitas", validators=[Optional(), Length(max=50)]
    )
    bank_name = StringField("Nama Bank", validators=[Optional(), Length(max=50)])
    bank_account_number = StringField(
        "No. Rekening", validators=[Optional(), Length(max=50)]
    )
    account_holder_name = StringField(
        "Nama Pemilik Rekening", validators=[Optional(), Length(max=120)]
    )
    submit = SubmitField("Simpan")


class SubjectForm(FlaskForm):
    """Form for creating/editing subject"""

    name = StringField(
        "Nama Mata Pelajaran", validators=[DataRequired(), Length(min=3, max=120)]
    )
    description = TextAreaField("Deskripsi", validators=[Optional()])
    submit = SubmitField("Simpan")


class SubjectTutorAssignmentForm(FlaskForm):
    """Form for manual tutor include on a subject detail page."""

    tutor_id = SelectField("Tutor", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Tambah Tutor")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tutor_id.choices = [
            (t.id, f"{t.name} ({t.tutor_code})" if t.tutor_code else t.name)
            for t in Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc()).all()
        ]


class CurriculumForm(FlaskForm):
    """Form for creating/editing curriculum"""

    name = StringField(
        "Nama Kurikulum", validators=[DataRequired(), Length(min=3, max=120)]
    )
    description = TextAreaField("Deskripsi", validators=[Optional()])
    submit = SubmitField("Simpan")


class PricingRuleForm(FlaskForm):
    """Form for creating/editing pricing rule"""

    _nullable_int = staticmethod(
        lambda value: int(value) if value not in (None, "", "None") else None
    )

    curriculum_id = SelectField(
        "Kurikulum", coerce=_nullable_int, validators=[Optional()]
    )
    level_id = SelectField("Jenjang", coerce=_nullable_int, validators=[Optional()])
    subject_id = SelectField(
        "Mata Pelajaran", coerce=_nullable_int, validators=[Optional()]
    )
    grade = StringField("Kelas", validators=[Optional(), Length(max=20)])
    student_rate_per_meeting = DecimalField(
        "Tarif Siswa per Pertemuan",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    tutor_rate_per_meeting = DecimalField(
        "Tarif Tutor per Pertemuan",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    default_meeting_quota = IntegerField(
        "Kuota Pertemuan Default", validators=[Optional(), NumberRange(min=1)]
    )
    submit = SubmitField("Simpan")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curriculum_id.choices = [(None, "-- Semua Kurikulum --")] + [
            (c.id, c.name) for c in Curriculum.query.order_by(Curriculum.name).all()
        ]
        self.level_id.choices = [(None, "-- Semua Jenjang --")] + [
            (l.id, l.name) for l in Level.query.order_by(Level.name).all()
        ]
        self.subject_id.choices = [(None, "-- Semua Mapel --")] + [
            (s.id, s.name) for s in Subject.query.order_by(Subject.name).all()
        ]
