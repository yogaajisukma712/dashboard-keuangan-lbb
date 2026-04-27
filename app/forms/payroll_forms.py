"""
Payroll forms for Dashboard Keuangan LBB Super Smart
Contains WTForms for tutor payout operations
"""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Optional, ValidationError

from app.models import Tutor


class TutorPayoutForm(FlaskForm):
    """Form for creating tutor payout"""

    tutor_id = SelectField(
        "Tutor", coerce=int, validators=[DataRequired(message="Pilih tutor")]
    )
    payout_date = DateField(
        "Tanggal Pembayaran",
        validators=[DataRequired(message="Tanggal pembayaran harus diisi")],
    )
    amount = DecimalField(
        "Nominal", places=2, validators=[DataRequired(message="Nominal harus diisi")]
    )
    service_month = DateField("Bulan Layanan", validators=[Optional()])
    bank_name = StringField("Nama Bank", validators=[Optional()])
    account_number = StringField("Nomor Rekening", validators=[Optional()])
    payment_method = SelectField(
        "Metode Pembayaran",
        choices=[
            ("transfer", "Transfer Bank"),
            ("cash", "Tunai"),
            ("check", "Cek"),
        ],
        default="transfer",
    )
    reference_number = StringField("Nomor Referensi", validators=[Optional()])
    notes = TextAreaField("Keterangan", validators=[Optional()])
    submit = SubmitField("Simpan Pembayaran")

    def validate_amount(self, field):
        """Validate amount is positive"""
        if field.data <= 0:
            raise ValidationError("Nominal harus lebih besar dari 0")

    def validate_tutor_id(self, field):
        """Validate tutor exists"""
        tutor = Tutor.query.get(field.data)
        if not tutor:
            raise ValidationError("Tutor tidak ditemukan")
