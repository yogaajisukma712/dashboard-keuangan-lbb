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
from threading import Thread
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    has_request_context,
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
    TutorPayoutProof,
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


def _send_fee_slip_whatsapp_attachment(
    payout: TutorPayout,
    contact_id: str,
    message: str,
    base_url: str | None = None,
) -> tuple[bool, str]:
    """Send fee slip PDF to one WhatsApp contact and update payout audit fields."""
    tutor = payout.tutor
    if has_request_context():
        pdf_response = fee_slip_pdf(payout.public_id)
        pdf_response.direct_passthrough = False
        pdf_bytes = pdf_response.get_data()
    else:
        pdf_bytes = _render_fee_slip_pdf_via_bot(payout, base_url=base_url)
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
        payout.whatsapp_last_contact_id = contact_id
        payout.whatsapp_last_message = message
        payout.whatsapp_last_sent_at = datetime.utcnow()
        payout.whatsapp_last_status = "sent"
        return True, ""
    return False, payload.get("error") or "Bot error"


def _send_fee_slips_whatsapp_bulk_background(
    app,
    payout_refs: list[str],
    message: str,
    base_url: str,
) -> None:
    """Run bulk WhatsApp send outside the web request to avoid Gunicorn timeout."""
    with app.app_context():
        sent_count = 0
        failed = []
        skipped = []
        try:
            with app.test_request_context(base_url=base_url):
                for payout_ref in payout_refs:
                    try:
                        payout_id = decode_public_id(payout_ref, "tutor_payout")
                        payout = TutorPayout.query.get(payout_id)
                    except Exception as exc:
                        failed.append(f"Slip {payout_ref}: {exc}")
                        continue
                    if not payout:
                        failed.append(f"Slip {payout_ref}: tidak ditemukan")
                        continue

                    contacts = _get_tutor_whatsapp_contact_options(payout.tutor)
                    if not contacts:
                        skipped.append(
                            f"{payout.tutor.name}: nomor WA tutor belum divalidasi"
                        )
                        continue

                    contact_id = contacts[0]["value"]
                    sent, error = _send_fee_slip_whatsapp_attachment(
                        payout,
                        contact_id,
                        message,
                        base_url=base_url,
                    )
                    if sent:
                        sent_count += 1
                        db.session.commit()
                    else:
                        db.session.rollback()
                        failed.append(f"{payout.tutor.name}: {error}")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Bulk WhatsApp fee slip job crashed")
        finally:
            current_app.logger.info(
                "Bulk WhatsApp fee slip job finished: sent=%s skipped=%s failed=%s",
                sent_count,
                len(skipped),
                len(failed),
            )
            if skipped:
                current_app.logger.warning(
                    "Bulk WhatsApp fee slip skipped: %s", "; ".join(skipped[:20])
                )
            if failed:
                current_app.logger.warning(
                    "Bulk WhatsApp fee slip failed: %s", "; ".join(failed[:20])
                )
            db.session.remove()


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
        "proof_image_url": download_url
        if ext in {"png", "jpg", "jpeg", "gif", "webp"}
        else None,
        "proof_is_image": ext in {"png", "jpg", "jpeg", "gif", "webp"},
        "proof_is_pdf": ext == "pdf",
    }


def _proof_context_from_path(file_path, notes=None, uploaded_at=None, original_filename=None):
    """Prepare URLs and file metadata for one uploaded proof file path."""
    if not file_path:
        return None

    filename = os.path.basename(file_path)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    download_url = url_for("payroll.serve_payroll_proof", filename=filename)
    return {
        "file_path": file_path,
        "filename": filename,
        "original_filename": original_filename or filename,
        "notes": notes,
        "uploaded_at": uploaded_at,
        "download_url": download_url,
        "image_url": download_url
        if ext in {"png", "jpg", "jpeg", "gif", "webp"}
        else None,
        "is_image": ext in {"png", "jpg", "jpeg", "gif", "webp"},
        "is_pdf": ext == "pdf",
        "extension": ext,
    }


def _payroll_proof_upload_dir():
    return os.path.join(current_app.config["UPLOAD_FOLDER"], "payroll_proofs")


def _backfill_legacy_payout_proof(payout):
    """Copy legacy single proof_image into the multi-proof table once."""
    if not payout.proof_image:
        return

    legacy_filename = os.path.basename(payout.proof_image)
    exists = False
    for proof in payout.transfer_proofs.all():
        if proof.file_path == payout.proof_image or proof.filename == legacy_filename:
            exists = True
            break
    if exists:
        return

    db.session.add(
        TutorPayoutProof(
            tutor_payout_id=payout.id,
            file_path=payout.proof_image,
            notes=payout.proof_notes,
            original_filename=legacy_filename,
            uploaded_at=payout.updated_at or payout.created_at or datetime.utcnow(),
        )
    )


def _get_payout_proof_contexts(payout):
    """Return all proof files, including legacy single proof_image data."""
    contexts = []
    seen = set()
    for proof in payout.transfer_proofs.all():
        ctx = _proof_context_from_path(
            proof.file_path,
            notes=proof.notes,
            uploaded_at=proof.uploaded_at,
            original_filename=proof.original_filename,
        )
        if ctx:
            contexts.append(ctx)
            seen.add(ctx["filename"])

    if payout.proof_image:
        legacy_ctx = _proof_context_from_path(
            payout.proof_image,
            notes=payout.proof_notes,
            uploaded_at=payout.updated_at or payout.created_at,
        )
        if legacy_ctx and legacy_ctx["filename"] not in seen:
            contexts.append(legacy_ctx)
            seen.add(legacy_ctx["filename"])

    upload_dir = _payroll_proof_upload_dir()
    if os.path.isdir(upload_dir):
        prefix = f"proof_{payout.id}_"
        allowed_ext = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
        for filename in os.listdir(upload_dir):
            if filename in seen or not filename.startswith(prefix):
                continue
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in allowed_ext:
                continue
            full_path = os.path.join(upload_dir, filename)
            ctx = _proof_context_from_path(
                f"payroll_proofs/{filename}",
                uploaded_at=datetime.fromtimestamp(os.path.getmtime(full_path)),
            )
            if ctx:
                contexts.append(ctx)
                seen.add(filename)

    contexts.sort(key=lambda item: item.get("uploaded_at") or datetime.min, reverse=True)
    return contexts


def _get_tutor_attendance_for_period(tutor_id, month, year):
    """Get raw attendance total (sum of tutor_fee_amount for attended sessions)."""
    total = db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount)).filter(
        AttendanceSession.tutor_id == tutor_id,
        db.extract("month", AttendanceSession.session_date) == month,
        db.extract("year", AttendanceSession.session_date) == year,
        AttendanceSession.status == "attended",
    ).scalar() or Decimal("0")
    return Decimal(str(total))


def _get_tutor_payable_for_period(tutor_id, month, year):
    """Get payable from attendance sessions (presensi = sumber kebenaran payroll).

    Data presensi adalah cerminan payroll — payable selalu dihitung dari
    total sesi yang tercatat di attendance_sessions.  Jika payout CSV
    lebih besar dari presensi, itu menandakan ada sesi yang belum dicatat
    di Data Presensi dan perlu dikoreksi.
    """
    return _get_tutor_attendance_for_period(tutor_id, month, year)


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
    Display summary of tutor payables.
    Default: only tutors with payable > 0 for the period.
    Pass ?show_all=1 to see all active tutors.
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)
    show_all = request.args.get("show_all", "0") == "1"

    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name).all()

    tutor_data = []
    for tutor in tutors:
        attendance_total = _get_tutor_attendance_for_period(tutor.id, month, year)
        payable = _get_tutor_payable_for_period(tutor.id, month, year)
        paid = _get_tutor_paid_for_period(tutor.id, month, year)
        balance = payable - paid
        # Flag discrepancy: payout CSV had more data than attendance CSV
        has_presensi_gap = paid > attendance_total

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
                "attendance_total": float(attendance_total),
                "payable": float(payable),
                "paid": float(paid),
                "balance": float(balance),
                "has_presensi_gap": has_presensi_gap,
                "latest_payout": latest_payout,
                "latest_payout_id": latest_payout.id if latest_payout else None,
            }
        )

    # Default: tampilkan tutor yang:
    # - payable > 0  (ada sesi presensi → perlu digaji), ATAU
    # - paid > payable (kelebihan bayar → presensi belum lengkap, perlu dikoreksi)
    if not show_all:
        tutor_data = [
            d for d in tutor_data if d["payable"] > 0 or d["has_presensi_gap"]
        ]

    return render_template(
        "payroll/tutor_summary.html",
        tutor_data=tutor_data,
        month=month,
        year=year,
        show_all=show_all,
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
                status="pending",  # user harus konfirmasi di detail sebelum 'completed'
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
    """Display payout detail with session list for review."""
    payout = _get_payout_by_ref_or_404(payout_ref)
    payout_sessions = _get_sessions_for_payout(payout)

    excluded_ids = list(payout.excluded_session_ids or [])
    included_sessions = [s for s in payout_sessions if s.id not in excluded_ids]
    sessions_total = sum(float(s.tutor_fee_amount or 0) for s in included_sessions)

    # Jika payout masih PENDING dan amount tidak sesuai total sesi saat ini,
    # sync otomatis supaya badge dan tabel presensi selalu konsisten.
    if payout.status == "pending" and abs(sessions_total - float(payout.amount)) > 0.01:
        payout.amount = Decimal(str(sessions_total))
        for line in payout.payout_lines:
            sm = line.service_month
            line_sessions = [
                s
                for s in included_sessions
                if s.session_date.month == sm.month and s.session_date.year == sm.year
            ]
            line.amount = Decimal(
                str(sum(float(s.tutor_fee_amount or 0) for s in line_sessions))
            )
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return render_template(
        "payroll/payout_detail.html",
        payout=payout,
        payout_sessions=payout_sessions,
        sessions_total=sessions_total,
        excluded_ids=excluded_ids,
        proof_items=_get_payout_proof_contexts(payout),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Auto-buat payout langsung dari list (redirect ke detail untuk konfirmasi)
# ─────────────────────────────────────────────────────────────────────────────


@payroll_bp.route("/payout/auto-create", methods=["POST"])
@login_required
def auto_create_payout():
    """Buat pending payout otomatis dengan nominal penuh, langsung redirect ke detail.

    Kalau sudah ada payout untuk tutor+periode ini, redirect ke payout yang ada.
    """
    tutor_id = request.form.get("tutor_id", type=int)
    month = request.form.get("month", type=int)
    year = request.form.get("year", type=int)

    if not all([tutor_id, month, year]):
        flash("Data tidak lengkap.", "danger")
        return redirect(url_for("payroll.tutor_summary"))

    tutor = Tutor.query.get_or_404(tutor_id)
    balance = _get_tutor_balance_for_period(tutor_id, month, year)

    if balance <= 0:
        flash(
            "Tutor %s tidak memiliki saldo untuk dibayar periode ini." % tutor.name,
            "warning",
        )
        return redirect(url_for("payroll.tutor_summary", month=month, year=year))

    # Cek apakah sudah ada payout aktif untuk periode ini
    existing = (
        TutorPayout.query.join(
            TutorPayoutLine, TutorPayout.id == TutorPayoutLine.tutor_payout_id
        )
        .filter(
            TutorPayout.tutor_id == tutor_id,
            TutorPayout.status != "cancelled",
            db.extract("month", TutorPayoutLine.service_month) == month,
            db.extract("year", TutorPayoutLine.service_month) == year,
        )
        .order_by(TutorPayout.created_at.desc())
        .first()
    )
    if existing:
        flash("Payout sudah ada untuk periode ini. Silakan review di bawah.", "info")
        return redirect(url_for("payroll.payout_detail", payout_ref=existing.public_id))

    # Buat payout baru (pending)
    try:
        payout = TutorPayout(
            tutor_id=tutor.id,
            payout_date=datetime.now(),
            amount=balance,
            bank_name=tutor.bank_name,
            account_number=tutor.bank_account_number,
            payment_method="transfer",
            status="pending",
            notes="",
        )
        db.session.add(payout)
        db.session.flush()

        payout_line = TutorPayoutLine(
            tutor_payout_id=payout.id,
            service_month=date(year, month, 1),
            amount=balance,
        )
        db.session.add(payout_line)
        db.session.commit()

        flash(
            "Payout untuk %s berhasil dibuat. "
            "Periksa rincian dan klik 'Konfirmasi Dibayar' setelah transfer."
            % tutor.name,
            "success",
        )
        return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))

    except Exception as exc:
        db.session.rollback()
        flash("Gagal membuat payout: %s" % exc, "danger")
        return redirect(url_for("payroll.tutor_summary", month=month, year=year))


@payroll_bp.route("/payout/<string:payout_ref>/revise", methods=["POST"])
@login_required
def revise_payout(payout_ref):
    """Update detail payout (nominal, bank, tanggal, catatan).

    Hanya bisa untuk payout berstatus 'pending'. Kalau sudah 'completed',
    toggle dulu ke pending sebelum merevisi.
    """
    payout = _get_payout_by_ref_or_404(payout_ref)

    if payout.status == "completed":
        flash(
            "Payout sudah dikonfirmasi. Ubah ke 'Belum Dibayar' terlebih dahulu sebelum merevisi.",
            "warning",
        )
        return redirect(url_for("payroll.payout_detail", payout_ref=payout_ref))

    try:
        # ── Nominal ──────────────────────────────────────────────────────────
        amount_str = (request.form.get("amount") or "").strip()
        if amount_str:
            new_amount = Decimal(amount_str)
            if new_amount <= 0:
                raise ValueError("Nominal harus lebih dari 0.")

            # Validasi: tidak melebihi payable tutor
            lines = list(payout.payout_lines)
            if lines:
                sm = lines[0].service_month
                payable = _get_tutor_payable_for_period(
                    payout.tutor_id, sm.month, sm.year
                )
                if new_amount > payable:
                    raise ValueError(
                        "Nominal (Rp %s) melebihi payable tutor (Rp %s)."
                        % (
                            "{:,.0f}".format(float(new_amount)),
                            "{:,.0f}".format(float(payable)),
                        )
                    )

            payout.amount = new_amount
            # Update semua line secara proporsional
            for line in lines:
                line.amount = new_amount  # simplifikasi: set ke nominal baru

        # ── Bank & Rekening ──────────────────────────────────────────────────
        bank_name = (request.form.get("bank_name") or "").strip()
        account_number = (request.form.get("account_number") or "").strip()
        if bank_name:
            payout.bank_name = bank_name
        if account_number:
            payout.account_number = account_number

        # ── Tanggal Pembayaran ───────────────────────────────────────────────
        payout_date_str = (request.form.get("payout_date") or "").strip()
        if payout_date_str:
            payout.payout_date = datetime.strptime(payout_date_str, "%Y-%m-%d")

        # ── Catatan ──────────────────────────────────────────────────────────
        notes = request.form.get("notes", "").strip()
        payout.notes = notes or None

        db.session.commit()
        flash("Payout berhasil direvisi.", "success")

    except Exception as exc:
        db.session.rollback()
        flash("Gagal merevisi payout: %s" % exc, "danger")

    return redirect(url_for("payroll.payout_detail", payout_ref=payout_ref))


@payroll_bp.route("/payout/<string:payout_ref>/toggle-paid", methods=["POST"])
@login_required
def toggle_paid(payout_ref):
    """Toggle payout status antara 'pending' dan 'completed'.

    - completed  → gaji sudah ditransfer; terhitung di Estimasi Gaji Tutor dashboard
    - pending    → belum dibayar; TIDAK terhitung di dashboard (saldo tetap tinggi)
    """
    payout = _get_payout_by_ref_or_404(payout_ref)
    if payout.status == "completed":
        payout.status = "pending"
    else:
        payout.status = "completed"
        if not payout.payout_date:
            payout.payout_date = datetime.now()
    try:
        db.session.commit()
        return jsonify({"success": True, "status": payout.status})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


@payroll_bp.route(
    "/payout/<string:payout_ref>/session/<int:session_id>/toggle", methods=["POST"]
)
@login_required
def toggle_session(payout_ref, session_id):
    """Exclude/include a session from this payout and recalculate the amount."""
    payout = _get_payout_by_ref_or_404(payout_ref)
    session_obj = AttendanceSession.query.get_or_404(session_id)

    # Verify the session belongs to this tutor
    if session_obj.tutor_id != payout.tutor_id:
        return jsonify({"success": False, "error": "Sesi tidak milik tutor ini."}), 400

    excluded = list(payout.excluded_session_ids or [])
    if session_id in excluded:
        excluded.remove(session_id)
        action = "included"
    else:
        excluded.append(session_id)
        action = "excluded"

    payout.excluded_session_ids = excluded

    # Recalculate payout amount from remaining included sessions
    all_sessions = _get_sessions_for_payout(payout)
    new_total = sum(
        float(s.tutor_fee_amount or 0) for s in all_sessions if s.id not in excluded
    )
    payout.amount = Decimal(str(new_total))

    # Update payout line amounts proportionally
    lines = list(payout.payout_lines)
    for line in lines:
        sm = line.service_month
        line_sessions = [
            s
            for s in all_sessions
            if s.session_date.month == sm.month
            and s.session_date.year == sm.year
            and s.id not in excluded
        ]
        line.amount = Decimal(
            str(sum(float(s.tutor_fee_amount or 0) for s in line_sessions))
        )

    try:
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "action": action,
                "session_id": session_id,
                "new_total": float(payout.amount),
                "excluded_ids": excluded,
            }
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


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

    payable = _get_tutor_payable_for_period(tutor.id, month, year)
    paid = _get_tutor_paid_for_period(tutor.id, month, year)
    balance = payable - paid

    return jsonify(
        {
            "tutor_id": tutor.id,
            "tutor_name": tutor.name,
            "payable": float(payable),
            "paid": float(paid),
            "balance": float(balance),
        }
    )


@payroll_bp.route("/api/tutor/<string:tutor_ref>/info", methods=["GET"])
@login_required
def api_tutor_info(tutor_ref):
    """Return tutor profile info (bank, rekening, dll) untuk auto-fill form."""
    tutor = _get_tutor_by_ref_or_404(tutor_ref)
    return jsonify(
        {
            "id": tutor.id,
            "name": tutor.name,
            "tutor_code": tutor.tutor_code or "",
            "bank_name": tutor.bank_name or "",
            "bank_account_number": tutor.bank_account_number or "",
            "account_holder_name": tutor.account_holder_name or "",
            "phone": tutor.phone or "",
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
            status="pending",  # dikonfirmasi di detail payout
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
    """Upload one or more transfer proof files."""
    payout = _get_payout_by_ref_or_404(payout_ref)

    files = request.files.getlist("proof_files")
    if not files and "proof_file" in request.files:
        files = request.files.getlist("proof_file")
    files = [item for item in files if item and item.filename]

    if not files:
        flash("Tidak ada file yang dipilih", "warning")
        return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))

    allowed_ext = {"png", "jpg", "jpeg", "gif", "pdf"}
    invalid_files = []
    for file in files:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in allowed_ext:
            invalid_files.append(file.filename)
    if invalid_files:
        flash(
            "Format file tidak didukung: %s. Gunakan PNG, JPG, GIF, atau PDF."
            % ", ".join(invalid_files),
            "danger",
        )
        return redirect(url_for("payroll.payout_detail", payout_ref=payout.public_id))

    try:
        upload_dir = _payroll_proof_upload_dir()
        os.makedirs(upload_dir, exist_ok=True)

        had_legacy_proof = bool(payout.proof_image)
        _backfill_legacy_payout_proof(payout)

        notes = request.form.get("proof_notes", "")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        saved_paths = []
        for index, file in enumerate(files, 1):
            ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
            filename = secure_filename(f"proof_{payout.id}_{timestamp}_{index}.{ext}")
            file.save(os.path.join(upload_dir, filename))
            file_path = f"payroll_proofs/{filename}"
            saved_paths.append(file_path)
            db.session.add(
                TutorPayoutProof(
                    tutor_payout_id=payout.id,
                    file_path=file_path,
                    notes=notes,
                    original_filename=file.filename,
                )
            )

        if not had_legacy_proof:
            payout.proof_image = saved_paths[0]
            payout.proof_notes = notes
        db.session.commit()

        flash(f"{len(saved_paths)} bukti transfer berhasil diupload", "success")
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


def _proof_image_data_uri(proof_image):
    """Embed uploaded proof image for browser-based PDF rendering."""
    if not proof_image:
        return None

    filename = os.path.basename(proof_image)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mimetype = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext)
    if not mimetype:
        return None

    proof_path = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        "payroll_proofs",
        filename,
    )
    if not os.path.exists(proof_path):
        return None

    with open(proof_path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mimetype};base64,{encoded}"


def _build_fee_slip_template_context(payout, *, embed_proof=False):
    """Build one shared context for web, print, PDF, and WhatsApp slip output."""
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
    proof_items = _get_payout_proof_contexts(payout)
    if embed_proof and proof_ctx.get("proof_image_url"):
        proof_ctx["proof_image_url"] = _proof_image_data_uri(payout.proof_image)
    if embed_proof:
        for proof in proof_items:
            if proof.get("is_image"):
                embedded_image = _proof_image_data_uri(proof.get("file_path"))
                if embedded_image:
                    proof["image_url"] = embedded_image

    ceo_name = current_app.config.get("INSTITUTION_CEO_NAME", "")
    whatsapp_session = _get_whatsapp_session_status()

    return {
        "payout": payout,
        "tutor": tutor,
        "sessions": sessions,
        "total": total,
        "period_label": period_label,
        "verify_url": verify_url,
        "whatsapp_session": whatsapp_session,
        "whatsapp_ready": whatsapp_session["ready"],
        "tutor_whatsapp_contacts": _get_tutor_whatsapp_contact_options(tutor),
        "default_whatsapp_message": _build_fee_slip_whatsapp_message(
            payout, tutor, total, period_label
        ),
        "proof_items": proof_items,
        "institution_name": current_app.config.get(
            "INSTITUTION_NAME", "LBB Super Smart"
        ),
        "institution_phone": current_app.config.get("INSTITUTION_PHONE", ""),
        "institution_city": current_app.config.get("INSTITUTION_CITY", "Surabaya"),
        "ceo_name": ceo_name,
        "ceo_title": current_app.config.get("INSTITUTION_CEO_TITLE", "CEO"),
        "branding_logo_mark_data_uri": get_branding_logo_mark_data_uri(),
        "verification_qr_data_uri": build_qr_code_data_uri(verify_url, box_size=5),
        "signature_qr_data_uri": build_qr_code_data_uri(
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
        "now": datetime.now(),
    }


def _render_fee_slip_pdf_via_bot(payout, base_url: str | None = None):
    """Render the same HTML slip with Chromium so PDF matches the web view."""
    resolved_base_url = base_url
    if not resolved_base_url and has_request_context():
        resolved_base_url = request.host_url
    if not resolved_base_url:
        resolved_base_url = current_app.config.get("APP_BASE_URL", "")

    html = render_template(
        "payroll/fee_slip.html",
        **_build_fee_slip_template_context(payout, embed_proof=True),
        pdf_mode=True,
    )
    payload, status_code = _bot_request(
        "POST",
        "/render/pdf",
        {
            "html": html,
            "baseUrl": resolved_base_url,
            "selector": ".fee-slip-document",
        },
        timeout=90,
    )
    if status_code != 200 or not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "Bot PDF renderer gagal")
    return base64.b64decode(payload["pdf_base64"])


@payroll_bp.route("/fee-slip/<string:payout_ref>", methods=["GET"])
@login_required
def fee_slip(payout_ref):
    """Fee tutor slip — halaman HTML yang bisa di-print"""
    payout = _get_payout_by_ref_or_404(payout_ref)
    return render_template(
        "payroll/fee_slip.html",
        **_build_fee_slip_template_context(payout),
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

    sent, error = _send_fee_slip_whatsapp_attachment(payout, contact_id, message)
    if sent:
        db.session.commit()
        flash(f"Slip fee berhasil dikirim ke WhatsApp {tutor.name}.", "success")
    else:
        flash(f"Kirim WhatsApp gagal: {error}", "danger")
    return redirect(url_for("payroll.fee_slip", payout_ref=payout.public_id))


@payroll_bp.route("/tutor-summary/send-whatsapp-bulk", methods=["POST"])
@login_required
def tutor_summary_send_whatsapp_bulk():
    """Kirim slip gaji PDF ke banyak tutor dari halaman rekap payroll."""
    month = request.form.get("month", default=datetime.now().month, type=int)
    year = request.form.get("year", default=datetime.now().year, type=int)
    show_all = request.form.get("show_all", "0") == "1"
    message = request.form.get("message", "", type=str).strip()
    payout_refs = request.form.getlist("payout_ref")

    redirect_url = url_for(
        "payroll.tutor_summary",
        month=month,
        year=year,
        show_all=1 if show_all else 0,
    )
    if not payout_refs:
        flash("Pilih minimal satu slip gaji yang sudah punya payout.", "warning")
        return redirect(redirect_url)
    if not message:
        flash("Pesan WhatsApp bulk tidak boleh kosong.", "warning")
        return redirect(redirect_url)

    session_status = _get_whatsapp_session_status()
    if not session_status["ready"]:
        flash("WhatsApp bot belum ready. Silakan login/scan QR terlebih dahulu.", "warning")
        return redirect(url_for("whatsapp_bot.management"))

    unique_refs = list(dict.fromkeys(ref for ref in payout_refs if ref))
    app = current_app._get_current_object()
    base_url = current_app.config.get("APP_BASE_URL") or request.host_url
    worker = Thread(
        target=_send_fee_slips_whatsapp_bulk_background,
        args=(app, unique_refs, message, base_url),
        daemon=True,
    )
    worker.start()

    flash(
        f"Proses kirim {len(unique_refs)} slip gaji berjalan di background. "
        "Halaman tidak perlu ditunggu agar server tidak timeout.",
        "info",
    )
    return redirect(redirect_url)


@payroll_bp.route("/fee-slip/<string:payout_ref>/pdf", methods=["GET"])
@login_required
def fee_slip_pdf(payout_ref):
    """Download fee slip sebagai PDF dari render HTML web agar konsisten."""
    payout = _get_payout_by_ref_or_404(payout_ref)
    tutor = payout.tutor
    pdf_filename = secure_filename(f"fee_slip_{payout.id}_{tutor.tutor_code}.pdf")
    try:
        pdf_bytes = _render_fee_slip_pdf_via_bot(payout)
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=pdf_filename,
        )
    except Exception as exc:
        current_app.logger.warning("Chromium fee slip PDF renderer failed: %s", exc)

    # Fallback lama tetap dipakai jika bot renderer belum hidup, agar download
    # tidak langsung gagal saat WhatsApp bot sedang restart.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

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
    ceo_name = current_app.config.get(
        "INSTITUTION_CEO_NAME", "Yoga Aji Sukma, S.Mat., M.Stat."
    )
    ceo_title = current_app.config.get("INSTITUTION_CEO_TITLE", "CEO")

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "fee_normal",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )
    small = ParagraphStyle(
        "fee_small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )
    bold = ParagraphStyle(
        "fee_bold",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
    )
    title = ParagraphStyle(
        "fee_title",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        alignment=1,
    )
    right_small = ParagraphStyle("fee_right_small", parent=small, alignment=2)
    center_small = ParagraphStyle("fee_center_small", parent=small, alignment=1)

    def _fit_image_size(image_source, max_width, max_height):
        reader = ImageReader(image_source)
        raw_width, raw_height = reader.getSize()
        if not raw_width or not raw_height:
            return max_width, max_height
        scale = min(max_width / raw_width, max_height / raw_height)
        return raw_width * scale, raw_height * scale

    def _branding_logo_path():
        for base_path in (current_app.root_path, os.path.dirname(current_app.root_path)):
            candidate = os.path.join(base_path, "logo.png")
            if os.path.exists(candidate):
                return candidate
        return None

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
    header_qr_cell = RLImage(
        build_qr_code_image_buffer(verify_url, box_size=4),
        width=2.2 * cm,
        height=2.2 * cm,
    )
    header_qr = Table(
        [[header_qr_cell], [Paragraph("Scan untuk<br/>verifikasi", center_small)]],
        colWidths=[2.4 * cm],
    )
    header_qr.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.4, gold),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    logo_path = _branding_logo_path()
    logo_cell = ""
    if logo_path:
        logo_width, logo_height = _fit_image_size(logo_path, 1.45 * cm, 1.45 * cm)
        logo_cell = RLImage(logo_path, width=logo_width, height=logo_height)

    story = []

    header_table = Table(
        [
            [
                logo_cell,
                Paragraph(
                    "<b>LEMBAGA BIMBINGAN BELAJAR</b><br/>"
                    f"<font size='16'><b>{institution_name}</b></font><br/>"
                    "Jl. Menur Pumpungan No 63, Sukolilo, Surabaya<br/>"
                    "Email: lbbsupersmart@gmail.com<br/>"
                    f"Handphone: {institution_phone}",
                    normal,
                ),
                header_qr,
            ]
        ],
        colWidths=[1.6 * cm, 12.3 * cm, 2.7 * cm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), yellow),
                ("BOX", (0, 0), (-1, -1), 1.2, gold),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "CENTER"),
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
            [
                "Email",
                tutor.email or "-",
                "No. Rekening",
                tutor.bank_account_number or "-",
            ],
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
            session_style.append(
                ("BACKGROUND", (0, row_index), (-1, row_index), light_yellow)
            )
    session_table.setStyle(TableStyle(session_style))
    story.append(session_table)

    proof_items = _get_payout_proof_contexts(payout)
    if proof_items:
        story.append(Spacer(1, 0.28 * cm))
        story.append(Paragraph("<b>Bukti Transfer</b>", bold))
        story.append(Spacer(1, 0.12 * cm))
        for index, proof in enumerate(proof_items, 1):
            story.append(Paragraph(f"Bukti #{index}: {proof['original_filename']}", small))
            if proof["is_image"]:
                proof_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    "payroll_proofs",
                    proof["filename"],
                )
                if os.path.exists(proof_path):
                    proof_width, proof_height = _fit_image_size(
                        proof_path, 15.5 * cm, 10.2 * cm
                    )
                    proof_image = RLImage(
                        proof_path, width=proof_width, height=proof_height
                    )
                    proof_table = Table([[proof_image]], colWidths=[16.8 * cm])
                    proof_table.setStyle(
                        TableStyle(
                            [
                                ("BOX", (0, 0), (-1, -1), 0.8, gold),
                                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 8),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ]
                        )
                    )
                    story.append(proof_table)
            elif proof["is_pdf"]:
                story.append(
                    Paragraph("Bukti transfer tersimpan sebagai file PDF di sistem.", small)
                )
            if proof.get("notes"):
                story.append(Spacer(1, 0.1 * cm))
                story.append(Paragraph(f"Catatan: {proof['notes']}", small))
            if index < len(proof_items):
                story.append(Spacer(1, 0.18 * cm))

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
                Paragraph(
                    f"<font color='#666666'><i>Dicetak: {datetime.now().strftime('%d/%m/%Y %H:%M')}</i></font>",
                    small,
                ),
                RLImage(
                    build_qr_code_image_buffer(verify_url, box_size=3),
                    width=1.8 * cm,
                    height=1.8 * cm,
                ),
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
    return send_file(
        buf, mimetype="application/pdf", as_attachment=True, download_name=safe_name
    )


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
        hide_login_link=True,
    )


@payroll_bp.route("/api/tutors-for-ocr", methods=["GET"])
@login_required
def api_tutors_for_ocr():
    """Return list of tutors dengan bank info untuk OCR matching di browser."""
    tutors = Tutor.query.filter_by(is_active=True).all()
    result = []
    for t in tutors:
        result.append(
            {
                "id": t.id,
                "name": t.name,
                "bank_name": t.bank_name or "",
                "account_number": t.bank_account_number or "",
                "account_holder": t.account_holder_name or t.name,
                "tutor_code": t.tutor_code,
            }
        )
    return jsonify(result)


@payroll_bp.route("/uploads/payroll_proofs/<path:filename>", methods=["GET"])
@login_required
def serve_payroll_proof(filename):
    """Serve uploaded payment proof files."""
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "payroll_proofs")
    return send_file(os.path.join(upload_dir, filename))
