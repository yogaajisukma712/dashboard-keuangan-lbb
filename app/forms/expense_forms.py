"""
Expense and related forms for Dashboard Keuangan LBB Super Smart
"""

from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.fields import DateTimeField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ExpenseForm(FlaskForm):
    """Form for adding/editing expenses"""

    expense_date = DateTimeField(
        "Tanggal Pengeluaran",
        format="%Y-%m-%d %H:%M",
        validators=[DataRequired()],
        render_kw={"class": "form-control"},
    )

    category = SelectField(
        "Kategori",
        validators=[DataRequired()],
        choices=[
            ("", "-- Pilih Kategori --"),
            ("iklan", "Iklan"),
            ("kuota", "Kuota"),
            ("tarik_tunai", "Tarik Tunai"),
            ("alat", "Alat/Perlengkapan"),
            ("transport", "Transport"),
            ("lainnya", "Lainnya"),
        ],
        render_kw={"class": "form-control"},
    )

    description = TextAreaField(
        "Deskripsi",
        validators=[DataRequired(), Length(min=5, max=500)],
        render_kw={"class": "form-control", "rows": 3},
    )

    amount = DecimalField(
        "Nominal",
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"class": "form-control"},
    )

    payment_method = SelectField(
        "Metode Pembayaran",
        validators=[Optional()],
        choices=[
            ("", "-- Pilih Metode --"),
            ("tunai", "Tunai"),
            ("transfer", "Transfer"),
            ("kartu_kredit", "Kartu Kredit"),
            ("cek", "Cek"),
        ],
        render_kw={"class": "form-control"},
    )

    reference_number = StringField(
        "No. Referensi",
        validators=[Optional(), Length(max=100)],
        render_kw={"class": "form-control"},
    )

    notes = TextAreaField(
        "Catatan",
        validators=[Optional(), Length(max=500)],
        render_kw={"class": "form-control", "rows": 2},
    )

    submit = SubmitField("Simpan", render_kw={"class": "btn btn-primary"})


class IncomeForm(FlaskForm):
    """Form for adding/editing other incomes"""

    income_date = DateTimeField(
        "Tanggal Pemasukan",
        format="%Y-%m-%d %H:%M",
        validators=[DataRequired()],
        render_kw={"class": "form-control"},
    )

    category = SelectField(
        "Kategori",
        validators=[DataRequired()],
        choices=[
            ("", "-- Pilih Kategori --"),
            ("iklan", "Iklan"),
            ("titipan", "Titipan"),
            ("koreksi", "Koreksi Kas"),
            ("bonus", "Bonus"),
            ("lainnya", "Lainnya"),
        ],
        render_kw={"class": "form-control"},
    )

    description = TextAreaField(
        "Deskripsi",
        validators=[DataRequired(), Length(min=5, max=500)],
        render_kw={"class": "form-control", "rows": 3},
    )

    amount = DecimalField(
        "Nominal",
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"class": "form-control"},
    )

    notes = TextAreaField(
        "Catatan",
        validators=[Optional(), Length(max=500)],
        render_kw={"class": "form-control", "rows": 2},
    )

    submit = SubmitField("Simpan", render_kw={"class": "btn btn-primary"})


class TutorPayoutForm(FlaskForm):
    """Form for recording tutor payouts"""

    tutor_id = SelectField(
        "Tutor",
        validators=[DataRequired()],
        coerce=int,
        render_kw={"class": "form-control"},
    )

    payout_date = DateTimeField(
        "Tanggal Pembayaran",
        format="%Y-%m-%d %H:%M",
        validators=[DataRequired()],
        render_kw={"class": "form-control"},
    )

    amount = DecimalField(
        "Nominal",
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"class": "form-control"},
    )

    service_month = DateTimeField(
        "Bulan Layanan",
        format="%Y-%m-%d",
        validators=[Optional()],
        render_kw={"class": "form-control"},
    )

    bank_name = StringField(
        "Nama Bank",
        validators=[Optional(), Length(max=50)],
        render_kw={"class": "form-control"},
    )

    account_number = StringField(
        "No. Rekening",
        validators=[Optional(), Length(max=50)],
        render_kw={"class": "form-control"},
    )

    payment_method = SelectField(
        "Metode Pembayaran",
        validators=[Optional()],
        choices=[
            ("transfer", "Transfer"),
            ("tunai", "Tunai"),
            ("cek", "Cek"),
        ],
        default="transfer",
        render_kw={"class": "form-control"},
    )

    reference_number = StringField(
        "No. Bukti Transfer",
        validators=[Optional(), Length(max=100)],
        render_kw={"class": "form-control"},
    )

    notes = TextAreaField(
        "Catatan",
        validators=[Optional(), Length(max=500)],
        render_kw={"class": "form-control", "rows": 2},
    )

    submit = SubmitField("Simpan Pembayaran", render_kw={"class": "btn btn-primary"})
