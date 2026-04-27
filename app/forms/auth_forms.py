"""
Authentication forms for Dashboard Keuangan LBB Super Smart
Contains LoginForm and RegisterForm
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from app.models import User


class LoginForm(FlaskForm):
    """Form for user login"""

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username harus diisi"),
            Length(min=3, max=80, message="Username harus 3-80 karakter"),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password harus diisi")],
    )
    remember_me = BooleanField("Ingat saya")
    submit = SubmitField("Login")


class RegisterForm(FlaskForm):
    """Form for user registration"""

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username harus diisi"),
            Length(min=3, max=80, message="Username harus 3-80 karakter"),
        ],
    )
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email harus diisi"),
            Email(message="Format email tidak valid"),
        ],
    )
    full_name = StringField(
        "Nama Lengkap",
        validators=[
            DataRequired(message="Nama lengkap harus diisi"),
            Length(min=3, max=120, message="Nama harus 3-120 karakter"),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password harus diisi"),
            Length(min=6, message="Password minimal 6 karakter"),
        ],
    )
    password_confirm = PasswordField(
        "Konfirmasi Password",
        validators=[
            DataRequired(message="Konfirmasi password harus diisi"),
            EqualTo("password", message="Password tidak cocok"),
        ],
    )
    submit = SubmitField("Daftar")

    def validate_username(self, field):
        """Check if username already exists"""
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Username sudah digunakan")

    def validate_email(self, field):
        """Check if email already exists"""
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("Email sudah terdaftar")
