"""
Payment forms for Dashboard Keuangan LBB Super Smart
Contains WTForms for payment-related operations
"""

from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError


class StudentPaymentForm(FlaskForm):
    """Form for creating student payment"""

    payment_date = StringField(
        "Tanggal Pembayaran",
        validators=[DataRequired()],
        render_kw={"type": "date"},
    )
    receipt_number = StringField(
        "Nomor Kwitansi",
        validators=[DataRequired(), Length(min=3, max=50)],
    )
    payment_method = StringField(
        "Metode Pembayaran",
        validators=[DataRequired()],
        render_kw={
            "class": "form-control",
        },
    )
    total_amount = DecimalField(
        "Total Pembayaran",
        validators=[DataRequired()],
        places=2,
    )
    notes = TextAreaField(
        "Catatan",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Simpan Pembayaran")


class StudentPaymentLineForm(FlaskForm):
    """Form for payment line item"""

    enrollment_id = IntegerField(
        "Enrollment",
        validators=[DataRequired()],
    )
    meeting_count = IntegerField(
        "Jumlah Pertemuan",
        validators=[DataRequired()],
    )
    submit = SubmitField("Tambah")
