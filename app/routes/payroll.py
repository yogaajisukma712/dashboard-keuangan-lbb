"""
Payroll routes for Dashboard Keuangan LBB Super Smart
Handles tutor payment and payroll management
"""

import base64
import os
import json
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required
from werkzeug.utils import secure_filename

from app import db
from app.forms import TutorPayoutForm
from app.models import (
    AttendanceSession,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
    WhatsAppTutorValidation,
)
from app.utils import (
    admin_required,
    build_qr_code_data_uri,
    build_qr_code_image_buffer,
    decode_public_id,
    get_branding_logo_mark_data_uri,
)

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")
MONTH_NAMES_ID = [
    "",
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
]


def _format_rupiah(value) -> str:
    return f"Rp {float(value or 0):,.0f}".replace(",", ".")


def _format_period_label(payout: TutorPayout) -> str:
    months = []
    for line in payout.payout_lines:
        if line.service_month:
            months.append(line.service_month.replace(day=1))
    unique_months = sorted(set(months))
    if unique_months:
        return ", ".join(
            f"{MONTH_NAMES_ID[item.month]} {item.year}" for item in unique_months
        )
    if payout.payout_date:
        return f"{MONTH_NAMES_ID[payout.payout_date.month]} {payout.payout_date.year}"
    return "-"


def _bot_request(method: str, path: str, payload: dict | None = None, timeout: int = 10):
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib_request.Request(
        f"{current_app.config['WHATSAPP_BOT_INTERNAL_URL'].rstrip('/')}{path}",
        data=body,
        method=method.upper(),
        headers=headers,
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            return (json.loads(text) if text else {}), response.status
    except urllib_error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            payload = {"ok": False, "error": text or str(exc)}
        return payload, exc.code
    except Exception as exc:
        return {"ok": False, "error": str(exc)}, 502


def _get_whatsapp_session_status() -> dict:
    payload, status_code = _bot_request("GET", "/session", timeout=5)
    session = payload.get("session") if isinstance(payload, dict) else {}
    return {
        "ok": status_code == 200 and bool(payload.get("ok")),
        "ready": bool(session.get("ready")) or session.get("status") == "ready",
        "status": session.get("status") or "offline",
        "session_id": session.get("sessionId") or session.get("clientId"),
        "error": payload.get("error"),
    }


def _get_tutor_whatsapp_contact_options(tutor: Tutor) -> list[dict]:
    options = []
    seen = set()
    validations = (
        WhatsAppTutorValidation.query.filter_by(tutor_id=tutor.id)
        .order_by(WhatsAppTutorValidation.validated_at.desc())
        .all()
    )
    for validation in validations:
        contact = validation.contact
        contact_id = (
            contact.whatsapp_contact_id
            if contact
            else f"{validation.validated_phone_number}@c.us"
        )
        if not contact_id or contact_id in seen:
            continue
        seen.add(contact_id)
        label_name = (
            validation.validated_contact_name
            or (contact.display_name if contact else None)
            or (contact.push_name if contact else None)
            or tutor.name
        )
        phone = validation.validated_phone_number or (contact.phone_number if contact else "")
        options.append(
            {
                "value": contact_id,
                "label": f"{label_name} - {phone or contact_id}",
                "source": "Validasi tutor",
            }
        )

    if tutor.phone:
        normalized_phone = "".join(ch for ch in tutor.phone if ch.isdigit())
        if normalized_phone and normalized_phone not in seen:
            options.append(
                {
                    "value": normalized_phone,
                    "label": f"{tutor.name} - {tutor.phone}",
                    "source": "Data master tutor",
                }
            )
    return options


def _build_fee_slip_whatsapp_message(
    payout: TutorPayout,
    tutor: Tutor,
    total,
    period_label: str,
) -> str:
    payout_date = payout.payout_date.strftime("%d/%m/%Y") if payout.payout_date else "-"
    return (
        f"Halo {tutor.name},\n\n"
        "Terima kasih banyak atas dedikasi, kesabaran, dan kontribusi Kakak "
        "dalam mendampingi siswa-siswi LBB Super Smart.\n\n"
        f"Fee tutor untuk bulan {period_label} sebesar {_format_rupiah(total)} "
        f"telah kami proses/bayarkan pada {payout_date}.\n\n"
        "Detail slip fee kami lampirkan dalam file PDF pada pesan ini.\n\n"
        "Semoga apresiasi ini menjadi penyemangat untuk terus memberikan "
        "pembelajaran terbaik. Terima kasih atas kerja samanya."
    )


def _get_payout_by_ref_or_404(payout_ref):
    """Resolve opaque payout ref to model instance."""
    try:
        payout_id = decode_public_id(payout_ref, "tutor_payout")
    except ValueError:
        abort(404)
    return TutorPayout.query.get_or_404(payout_id)


def _get_tutor_by_ref_or_404(tutor_ref):
    """Resolve opaque tutor ref to model instance."""
    try:
        tutor_id = decode_public_id(tutor_ref, "tutor")
    except ValueError:
        abort(404)
    return Tutor.query.get_or_404(tutor_id)


def _build_proof_context(proof_image):
    """Prepare URLs and file metadata for uploaded proof files."""
    if not proof_image:
        return {
            "proof_download_url": None,
            "proof_image_url": None,
            "proof_is_image": False,
            "proof_is_pdf": False,
        }

    filename = os.path.basename(proof_image)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    download_url = url_for("payroll.serve_payroll_proof", filename=filename)
    return {
        "proof_download_url": download_url,
        "proof_image_url": download_url if ext in {"png", "jpg", "jpeg", "gif", "webp"} else None,
        "proof_is_image": ext in {"png", "jpg", "jpeg", "gif", "webp"},
        "proof_is_pdf": ext == "pdf",
    }


def _get_tutor_payable_for_period(tutor_id, month, year):
    """Get total tutor payable from attendance for a specific service period."""
    total = db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount)).filter(
        AttendanceSession.tutor_id == tutor_id,
        db.extract("month", AttendanceSession.session_date) == month,
        db.extract("year", AttendanceSession.session_date) == year,
        AttendanceSession.status == "attended",
    ).scalar() or Decimal("0")
    return Decimal(str(total))


def _get_tutor_paid_for_period(tutor_id, month, year):
    """Get total tutor payout already allocated to a specific service period."""
    total = db.session.query(db.func.sum(TutorPayoutLine.amount)).join(
        TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id
    ).filter(
        TutorPayout.tutor_id == tutor_id,
        TutorPayout.status == "completed",
        db.extract("month", TutorPayoutLine.service_month) == month,
        db.extract("year", TutorPayoutLine.service_month) == year,
    ).scalar() or Decimal("0")
    return Decimal(str(total))


def _get_tutor_balance_for_period(tutor_id, month, year):
    """Get remaining tutor payable balance for a specific service period."""
    payable = _get_tutor_payable_for_period(tutor_id, month, year)
    paid = _get_tutor_paid_for_period(tutor_id, month, year)
    return payable - paid


@payroll_bp.route("/tutor-summary", methods=["GET"])
@login_required
def tutor_summary():
    """
    Display summary of tutor payables
    Shows total payable per tutor and payment status
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    tutors = Tutor.query.filter_by(is_active=True).all()

    tutor_data = []
    for tutor in tutors:
        payable = _get_tutor_payable_for_period(tutor.id, month, year)
        paid = _get_tutor_paid_for_period(tutor.id, month, year)
        balance = payable - paid

        # Get latest payout ID for this tutor/month so we can link to fee slip
        latest_payout = (
            TutorPayout.query.join(
                TutorPayoutLine, TutorPayout.id == TutorPayoutLine.tutor_payout_id
            )
            .filter(
                TutorPayout.tutor_id == tutor.id,
                db.extract("month", TutorPayoutLine.service_month) == month,
                db.extract("year", TutorPayoutLine.service_month) == year,
            )
            .order_by(TutorPayout.created_at.desc())
            .first()
        )

        tutor_data.append(
            {
                "tutor": tutor,
                "payable": float(payable),
                "paid": float(paid),
                "balance": float(balance),
                "latest_payout": latest_payout,
                "latest_payout_id": latest_payout.id if latest_payout else None,
            }
        )

    return render_template(
        "payroll/tutor_summary.html", tutor_data=tutor_data, month=month, year=year
    )


@payroll_bp.route("/payout/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_payout():
    """
    Add new tutor payout
    Requires a valid service period and prevents overpayment.
    """
    form = TutorPayoutForm()
    form.tutor_id.choices = [
        (t.id, t.name) for t in Tutor.query.filter_by(is_active=True).all()
    ]

    if form.validate_on_submit():
        try:
            tutor_id = form.tutor_id.data
            service_month = form.service_month.data
            amount = Decimal(str(form.amount.data or 0)).quantize(Decimal("0.01"))

            if service_month is None:
                raise ValueError("Bulan layanan wajib diisi")

            period_month = service_month.month
            period_year = service_month.year

            balance = _get_tutor_balance_for_period(tutor_id, period_month, period_year)

            if balance <= 0:
                raise ValueError("Tutor tidak memiliki saldo payable untuk periode ini")

            if amount > balance:
                raise ValueError(
                    f"Nominal payout ({amount}) melebihi saldo tutor ({balance})"
                )

            payout = TutorPayout(
                tutor_id=tutor_id,
                payout_date=form.payout_date.data,
                amount=amount,
                bank_name=form.bank_name.data,
                account_number=form.account_number.data,
                payment_method=form.payment_method.data,
                reference_number=form.reference_number.data,
                notes=form.notes.data,
                status="completed",
            )

            db.session.add(payout)
            db.session.flush()

            payout_line = TutorPayoutLine(
                tutor_payout_id=payout.id,
                service_month=service_month,
                amount=amount,
                notes=form.notes.data,
            )
            db.session.add(payout_line)

            db.session.commit()
            flash(f"Pembayaran gaji ke {payout.tutor.name} berhasil dicatat", "success")
            return redirect(url_for("payroll.tutor_summary"))
        except Exception as e:
            db.session.rollback()
            flash(f"Terjadi kesalahan: {str(e)}", "danger")

    tutor_public_ids = {
        str(t.id): t.public_id for t in Tutor.query.filter_by(is_active=True).all()
    }
    return render_template(
        "payroll/payout_form.html",
        form=form,
        tutor_public_ids=tutor_public_ids,
    )


@payroll_bp.route("/payout/<string:payout_ref>", methods=["GET"])
@login_required
def payout_detail(payout_ref):
    """
    Display payout detail
    """
    payout = _get_payout_by_ref_or_404(payout_ref)
    return render_template("payroll/payout_detail.html", payout=payout)


@payroll_bp.route("/payout/<string:payout_ref>/delete", methods=["POST"])
@login_required
@admin_required
def delete_payout(payout_ref):
    """
    Delete payout
    """
    payout = _get_payout_by_ref_or_404(payout_ref)

    try:
        db.session.delete(payout)
        db.session.commit()
        flash("Pembayaran berhasil dihapus", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Terjadi kesalahan: {str(e)}", "danger")

    return redirect(url_for("payroll.tutor_summary"))


@payroll_bp.route("/transfer-list", methods=["GET"])
@login_required
def transfer_list():
    """
    Display list of pending transfers
    Can be exported to Excel for bulk transfer
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    tutors = Tutor.query.filter_by(is_active=True).all()

    transfer_data = []
    total_amount = 0

    for tutor in tutors:
        payable = _get_tutor_payable_for_period(tutor.id, month, year)
        paid = _get_tutor_paid_for_period(tutor.id, month, year)
        balance = payable - paid

        if balance > 0 and tutor.bank_account_number:
            transfer_data.append(
                {
                    "no": len(transfer_data) + 1,
                    "tutor_name": tutor.name,
                    "bank_name": tutor.bank_name or "-",
                    "account_number": tutor.bank_account_number,
                    "account_holder": tutor.account_holder_name,
                    "amount": float(balance),
                }
            )
            total_amount += float(balance)

    return render_template(
        "payroll/transfer_list.html",
        transfer_data=transfer_data,
        total_amount=total_amount,
        month=month,
        year=year,
    )


@payroll_bp.route("/api/tutor/<string:tutor_ref>/balance", methods=["GET"])
@login_required
def api_tutor_balance(tutor_ref):
    """
    API endpoint to get tutor balance
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    tutor = _get_tutor_by_ref_or_404(tutor_ref)

    payable = _get_tutor_payable_for_period(tutor_id, month, year)
    paid = _get_tutor_paid_for_period(tutor_id, month, year)
    balance = payable - paid

    return jsonify(
        {
            "tutor_id": tutor_id,
            "tutor_name": tutor.name,
            "payable": float(payable),
            "paid": float(paid),
            "balance": float(balance),
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fitur 2: Quick-pay checkbox + upload bukti transfer
# ─────────────────────────────────────────────────────────────────────────────


@payroll_bp.route("/api/quick-pay", methods=["POST"])
@login_required
def api_quick_pay():
    """Create payout via checkbox AJAX — returns JSON {success, payout_id}"""
    try:
        data = request.get_json(force=True) or {}
        tutor_id = data.get("tutor_id")
        amount = data.get("amount")
        month = data.get("month")
        year = data.get("year")
        notes = data.get("notes", "")

        if not all([tutor_id, amount, month, year]):
            return jsonify(
                {"success": False, "error": "tutor_id, amount, month, year wajib diisi"}
            ), 400

        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            return jsonify(
                {"success": False, "error": "Nominal harus lebih dari 0"}
            ), 400

        tutor = Tutor.query.get_or_404(int(tutor_id))
        service_month_date = date(int(year), int(month), 1)

        payout = TutorPayout(
            tutor_id=tutor.id,
            payout_date=datetime.now(),
            amount=amount_dec,
            bank_name=tutor.bank_name,
            account_number=tutor.bank_account_number,
            payment_method="transfer",
            status="completed",
            notes=notes,
        )
        db.session.add(payout)
        db.session.flush()

        payout_line = TutorPayoutLine(
            tutor_payout_id=payout.id,
            service_month=service_month_date,
            amount=amount_dec,
            notes=notes,
        )
        db.session.add(payout_line)
        db.session.commit()

        return jsonify({"success": True, "payout_id": payout.id})

    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


@payroll_bp.route("/payout/<string:payout_ref>/upload-proof", methods=["POST"])
@login_required
def upload_proof(payout_ref):
    """Upload bukti transfer image — simpan ke uploads/payroll_proofs/"""
    payout = _get_payout_by_ref_or_404(payout_ref)

    if "proof_file" not in request.files:
        flash("Tidak ada file yang dipilih", "warning")
        return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))

    file = request.files["proof_file"]
    if not file or file.filename == "":
        flash("Tidak ada file yang dipilih", "warning")
        return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))

    allowed_ext = {"png", "jpg", "jpeg", "gif", "pdf"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_ext:
        flash("Format file tidak didukung. Gunakan PNG, JPG, GIF, atau PDF.", "danger")
        return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))

    try:
        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "payroll_proofs")
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = secure_filename(f"proof_{payout.id}_{timestamp}.{ext}")
        file.save(os.path.join(upload_dir, filename))

        payout.proof_image = f"payroll_proofs/{filename}"
        payout.proof_notes = request.form.get("proof_notes", "")
        db.session.commit()

        flash("Bukti transfer berhasil diupload", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal upload: {exc}", "danger")

    return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))


# ─────────────────────────────────────────────────────────────────────────────
# Fitur 3: Fee Tutor Slip (HTML + PDF)
# ─────────────────────────────────────────────────────────────────────────────


def _get_sessions_for_payout(payout):
    """Return list of AttendanceSession records covered by this payout."""
    sessions = []
    for line in payout.payout_lines:
        sm = line.service_month  # date object
        month_sessions = (
            AttendanceSession.query.filter(
                AttendanceSession.tutor_id == payout.tutor_id,
                db.extract("month", AttendanceSession.session_date) == sm.month,
                db.extract("year", AttendanceSession.session_date) == sm.year,
                AttendanceSession.status == "attended",
            )
            .order_by(AttendanceSession.session_date)
            .all()
        )
        sessions.extend(month_sessions)
    return sessions


@payroll_bp.route("/fee-slip/<string:payout_ref>", methods=["GET"])
@login_required
def fee_slip(payout_ref):
    """Fee tutor slip — halaman HTML yang bisa di-print"""
    payout = _get_payout_by_ref_or_404(payout_ref)
    tutor = payout.tutor
    sessions = _get_sessions_for_payout(payout)
    total = sum(float(s.tutor_fee_amount or 0) for s in sessions)
    period_label = _format_period_label(payout)

    verify_url = url_for(
        "payroll.fee_slip_verify",
        payout_ref=payout.public_id,
        _external=True,
    )
    proof_ctx = _build_proof_context(payout.proof_image)
    ceo_name = current_app.config.get("INSTITUTION_CEO_NAME", "")
    whatsapp_session = _get_whatsapp_session_status()
    tutor_whatsapp_contacts = _get_tutor_whatsapp_contact_options(tutor)

    return render_template(
        "payroll/fee_slip.html",
        payout=payout,
        tutor=tutor,
        sessions=sessions,
        total=total,
        period_label=period_label,
        verify_url=verify_url,
        whatsapp_session=whatsapp_session,
        whatsapp_ready=whatsapp_session["ready"],
        tutor_whatsapp_contacts=tutor_whatsapp_contacts,
        default_whatsapp_message=_build_fee_slip_whatsapp_message(
            payout, tutor, total, period_label
        ),
        institution_name=current_app.config.get("INSTITUTION_NAME", "LBB Super Smart"),
        institution_phone=current_app.config.get("INSTITUTION_PHONE", ""),
        institution_city=current_app.config.get("INSTITUTION_CITY", "Surabaya"),
        ceo_name=ceo_name,
        ceo_title=current_app.config.get("INSTITUTION_CEO_TITLE", "CEO"),
        branding_logo_mark_data_uri=get_branding_logo_mark_data_uri(),
        verification_qr_data_uri=build_qr_code_data_uri(verify_url, box_size=5),
        signature_qr_data_uri=build_qr_code_data_uri(
            "|".join(
                [
                    "TUTOR-FEE-SLIP",
                    str(payout.id),
                    tutor.name or "-",
                    f"{float(total or 0):.0f}",
                    payout.payout_date.isoformat() if payout.payout_date else "-",
                    ceo_name or "-",
                ]
            ),
            box_size=4,
        ),
        **proof_ctx,
        now=datetime.now(),
    )


@payroll_bp.route("/fee-slip/<string:payout_ref>/send-whatsapp", methods=["POST"])
@login_required
def fee_slip_send_whatsapp(payout_ref):
    """Kirim slip fee tutor via WhatsApp bot."""
    payout = _get_payout_by_ref_or_404(payout_ref)
    tutor = payout.tutor
    contact_id = request.form.get("contact_id", "", type=str).strip()
    message = request.form.get("message", "", type=str).strip()
    allowed_contacts = {
        item["value"] for item in _get_tutor_whatsapp_contact_options(tutor)
    }

    if not contact_id or contact_id not in allowed_contacts:
        flash("Pilih nomor WhatsApp tutor dari kontak yang tersedia.", "warning")
        return redirect(url_for("payroll.fee_slip", payout_ref=payout.public_id))
    if not message:
        flash("Pesan WhatsApp tidak boleh kosong.", "warning")
        return redirect(url_for("payroll.fee_slip", payout_ref=payout.public_id))

    session_status = _get_whatsapp_session_status()
    if not session_status["ready"]:
        flash("WhatsApp bot belum ready. Silakan login/scan QR terlebih dahulu.", "warning")
        return redirect(url_for("whatsapp_bot.management"))

    pdf_response = fee_slip_pdf(payout.public_id)
    pdf_response.direct_passthrough = False
    pdf_bytes = pdf_response.get_data()
    pdf_filename = secure_filename(f"fee_slip_{payout.id}_{tutor.tutor_code}.pdf")

    payload, status_code = _bot_request(
        "POST",
        "/messages/send",
        {
            "to": contact_id,
            "message": message,
            "attachment": {
                "filename": pdf_filename,
                "mimetype": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode("ascii"),
            },
        },
        timeout=60,
    )
    if status_code == 200 and payload.get("ok"):
        flash(f"Slip fee berhasil dikirim ke WhatsApp {tutor.name}.", "success")
    else:
        flash(f"Kirim WhatsApp gagal: {payload.get('error') or 'Bot error'}", "danger")
    return redirect(url_for("payroll.fee_slip", payout_ref=payout.public_id))


@payroll_bp.route("/fee-slip/<string:payout_ref>/pdf", methods=["GET"])
@login_required
def fee_slip_pdf(payout_ref):
    """Download fee slip sebagai PDF yang stabil dan ringan."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    payout = _get_payout_by_ref_or_404(payout_ref)
    tutor = payout.tutor
    sessions = _get_sessions_for_payout(payout)
    total = sum(float(s.tutor_fee_amount or 0) for s in sessions)

    gold = colors.HexColor("#DAA520")
    yellow = colors.HexColor("#FFD700")
    light_yellow = colors.HexColor("#FFFDE7")

    months_id = [
        "",
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ]
    days_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

    payout_dt = payout.payout_date or datetime.now()
    date_id = f"{payout_dt.day} {months_id[payout_dt.month]} {payout_dt.year}"
    institution_name = current_app.config.get("INSTITUTION_NAME", "LBB Super Smart")
    institution_city = current_app.config.get("INSTITUTION_CITY", "Surabaya")
    institution_phone = current_app.config.get("INSTITUTION_PHONE", "0895-6359-07419")
    ceo_name = current_app.config.get("INSTITUTION_CEO_NAME", "Yoga Aji Sukma, S.Mat., M.Stat.")
    ceo_title = current_app.config.get("INSTITUTION_CEO_TITLE", "CEO")

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("fee_normal", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=11)
    small = ParagraphStyle("fee_small", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10)
    bold = ParagraphStyle("fee_bold", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=11)
    title = ParagraphStyle("fee_title", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=16, alignment=1)
    right_small = ParagraphStyle("fee_right_small", parent=small, alignment=2)
    center_small = ParagraphStyle("fee_center_small", parent=small, alignment=1)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
    )

    verify_url = url_for(
        "payroll.fee_slip_verify",
        payout_ref=payout.public_id,
        _external=True,
    )
    qr_cell = RLImage(build_qr_code_image_buffer(verify_url, box_size=4), width=2.2 * cm, height=2.2 * cm)

    story = []

    header_table = Table(
        [
            [
                Paragraph(
                    "<b>LEMBAGA BIMBINGAN BELAJAR</b><br/>"
                    f"<font size='16'><b>{institution_name}</b></font><br/>"
                    "Jl. Menur Pumpungan No 63, Sukolilo, Surabaya<br/>"
                    "Email: lbbsupersmart@gmail.com<br/>"
                    f"Handphone: {institution_phone}",
                    normal,
                ),
                qr_cell,
            ]
        ],
        colWidths=[14.2 * cm, 2.2 * cm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), yellow),
                ("BOX", (0, 0), (-1, -1), 1.2, gold),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("Fee Tutor", title))
    story.append(Spacer(1, 0.25 * cm))

    info_table = Table(
        [
            ["Nama", tutor.name or "-", "Tanggal", date_id],
            ["Email", tutor.email or "-", "No. Rekening", tutor.bank_account_number or "-"],
            ["ID Tutor", tutor.tutor_code or "-", "Bank", tutor.bank_name or "-"],
        ],
        colWidths=[2.6 * cm, 6.1 * cm, 3.0 * cm, 5.3 * cm],
    )
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), light_yellow),
                ("BOX", (0, 0), (-1, -1), 1.0, gold),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, gold),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 0.25 * cm))

    summary_table = Table(
        [[f"{len(sessions)} sesi", f"Total: Rp {total:,.0f}"]],
        colWidths=[8.2 * cm, 8.8 * cm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), yellow),
                ("BOX", (0, 0), (-1, -1), 1.0, gold),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.22 * cm))

    session_rows = [
        [
            Paragraph("<b>No</b>", center_small),
            Paragraph("<b>Tanggal</b>", center_small),
            Paragraph("<b>Hari</b>", center_small),
            Paragraph("<b>Siswa</b>", center_small),
            Paragraph("<b>Mapel</b>", center_small),
            Paragraph("<b>Nominal</b>", center_small),
        ]
    ]
    for idx, sess in enumerate(sessions, 1):
        session_date = sess.session_date
        date_str = (
            f"{session_date.day:02d}/{session_date.month:02d}/{session_date.year}"
            if session_date
            else "-"
        )
        day_name = days_id[session_date.weekday()] if session_date else "-"
        student_name = sess.student.name if sess.student else "-"
        subject_name = sess.subject.name if sess.subject else "-"
        nominal = f"Rp {float(sess.tutor_fee_amount or 0):,.0f}"
        session_rows.append(
            [
                Paragraph(str(idx), center_small),
                Paragraph(date_str, small),
                Paragraph(day_name, small),
                Paragraph(student_name, small),
                Paragraph(subject_name, small),
                Paragraph(nominal, right_small),
            ]
        )

    session_table = Table(
        session_rows,
        colWidths=[0.9 * cm, 2.5 * cm, 1.8 * cm, 5.5 * cm, 4.1 * cm, 2.3 * cm],
        repeatRows=1,
    )
    session_style = [
        ("BACKGROUND", (0, 0), (-1, 0), yellow),
        ("BOX", (0, 0), (-1, -1), 1.0, gold),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, gold),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for row_index in range(1, len(session_rows)):
        if row_index % 2 == 0:
            session_style.append(("BACKGROUND", (0, row_index), (-1, row_index), light_yellow))
    session_table.setStyle(TableStyle(session_style))
    story.append(session_table)

    proof_ctx = _build_proof_context(payout.proof_image)
    if proof_ctx["proof_is_image"]:
        story.append(Spacer(1, 0.28 * cm))
        story.append(Paragraph("<b>Bukti Transfer</b>", bold))
        story.append(Spacer(1, 0.12 * cm))
        proof_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            "payroll_proofs",
            os.path.basename(payout.proof_image),
        )
        story.append(RLImage(proof_path, width=7.5 * cm, height=4.8 * cm))
        if payout.proof_notes:
            story.append(Spacer(1, 0.1 * cm))
            story.append(Paragraph(f"Catatan: {payout.proof_notes}", small))
    elif proof_ctx["proof_is_pdf"]:
        story.append(Spacer(1, 0.28 * cm))
        story.append(Paragraph("Bukti transfer tersimpan sebagai file PDF di sistem.", small))
        if payout.proof_notes:
            story.append(Paragraph(f"Catatan: {payout.proof_notes}", small))

    story.append(Spacer(1, 0.35 * cm))
    footer_table = Table(
        [
            [
                Paragraph(
                    '"We sincerely appreciate your hard work<br/>and dedication to our students."',
                    small,
                ),
                Paragraph(f"{institution_city}, {date_id}", center_small),
            ],
            [
                Paragraph(f"<font color='#666666'><i>Dicetak: {datetime.now().strftime('%d/%m/%Y %H:%M')}</i></font>", small),
                RLImage(build_qr_code_image_buffer(verify_url, box_size=3), width=1.8 * cm, height=1.8 * cm),
            ],
            ["", Paragraph(f"<b>{ceo_name}</b><br/>{ceo_title}", center_small)],
        ],
        colWidths=[10.6 * cm, 6.4 * cm],
    )
    footer_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(footer_table)

    doc.build(story)
    buf.seek(0)
    safe_name = secure_filename(f"fee_slip_{payout.id}_{tutor.tutor_code}.pdf")
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=safe_name)


@payroll_bp.route("/fee-slip/<string:payout_ref>/verify", methods=["GET"])
def fee_slip_verify(payout_ref):
    """Verifikasi fee slip via QR code scan (tidak perlu login)"""
    payout = _get_payout_by_ref_or_404(payout_ref)
    tutor = payout.tutor
    sessions = _get_sessions_for_payout(payout)
    total = sum(float(s.tutor_fee_amount or 0) for s in sessions)
    return render_template(
        "payroll/fee_slip_verify.html",
        payout=payout,
        tutor=tutor,
        sessions=sessions,
        total=total,
        now=datetime.now(),
    )


@payroll_bp.route('/api/tutors-for-ocr', methods=['GET'])
@login_required
def api_tutors_for_ocr():
    """Return list of tutors dengan bank info untuk OCR matching di browser."""
    tutors = Tutor.query.filter_by(is_active=True).all()
    result = []
    for t in tutors:
        result.append({
            'id': t.id,
            'name': t.name,
            'bank_name': t.bank_name or '',
            'account_number': t.bank_account_number or '',
            'account_holder': t.account_holder_name or t.name,
            'tutor_code': t.tutor_code,
        })
    return jsonify(result)


@payroll_bp.route('/uploads/payroll_proofs/<path:filename>', methods=['GET'])
@login_required
def serve_payroll_proof(filename):
    """Serve uploaded payment proof files."""
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'payroll_proofs')
    return send_file(os.path.join(upload_dir, filename))
