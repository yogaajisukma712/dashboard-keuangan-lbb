"""
Payroll routes for Dashboard Keuangan LBB Super Smart
Handles tutor payment and payroll management
"""

import os
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from flask import (
    Blueprint,
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
from app.models import AttendanceSession, Tutor, TutorPayout, TutorPayoutLine
from app.utils import admin_required

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")


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

    return render_template("payroll/payout_form.html", form=form)


@payroll_bp.route("/payout/<int:payout_id>", methods=["GET"])
@login_required
def payout_detail(payout_id):
    """
    Display payout detail
    """
    payout = TutorPayout.query.get_or_404(payout_id)
    return render_template("payroll/payout_detail.html", payout=payout)


@payroll_bp.route("/payout/<int:payout_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_payout(payout_id):
    """
    Delete payout
    """
    payout = TutorPayout.query.get_or_404(payout_id)

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


@payroll_bp.route("/api/tutor/<int:tutor_id>/balance", methods=["GET"])
@login_required
def api_tutor_balance(tutor_id):
    """
    API endpoint to get tutor balance
    """
    month = request.args.get("month", default=datetime.now().month, type=int)
    year = request.args.get("year", default=datetime.now().year, type=int)

    tutor = Tutor.query.get_or_404(tutor_id)

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


@payroll_bp.route("/payout/<int:payout_id>/upload-proof", methods=["POST"])
@login_required
def upload_proof(payout_id):
    """Upload bukti transfer image — simpan ke uploads/payroll_proofs/"""
    payout = TutorPayout.query.get_or_404(payout_id)

    if "proof_file" not in request.files:
        flash("Tidak ada file yang dipilih", "warning")
        return redirect(url_for("payroll.payout_detail", payout_id=payout_id))

    file = request.files["proof_file"]
    if not file or file.filename == "":
        flash("Tidak ada file yang dipilih", "warning")
        return redirect(url_for("payroll.payout_detail", payout_id=payout_id))

    allowed_ext = {"png", "jpg", "jpeg", "gif", "pdf"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_ext:
        flash("Format file tidak didukung. Gunakan PNG, JPG, GIF, atau PDF.", "danger")
        return redirect(url_for("payroll.payout_detail", payout_id=payout_id))

    try:
        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "payroll_proofs")
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = secure_filename(f"proof_{payout_id}_{timestamp}.{ext}")
        file.save(os.path.join(upload_dir, filename))

        payout.proof_image = f"payroll_proofs/{filename}"
        payout.proof_notes = request.form.get("proof_notes", "")
        db.session.commit()

        flash("Bukti transfer berhasil diupload", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal upload: {exc}", "danger")

    return redirect(url_for("payroll.payout_detail", payout_id=payout_id))


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


@payroll_bp.route("/fee-slip/<int:payout_id>", methods=["GET"])
@login_required
def fee_slip(payout_id):
    """Fee tutor slip — halaman HTML yang bisa di-print"""
    payout = TutorPayout.query.get_or_404(payout_id)
    tutor = payout.tutor
    sessions = _get_sessions_for_payout(payout)
    total = sum(float(s.tutor_fee_amount or 0) for s in sessions)

    verify_url = f"{request.host_url.rstrip('/')}/payroll/fee-slip/{payout_id}/verify"
    encoded_verify_url = quote(verify_url, safe="")

    return render_template(
        "payroll/fee_slip.html",
        payout=payout,
        tutor=tutor,
        sessions=sessions,
        total=total,
        verify_url=verify_url,
        encoded_verify_url=encoded_verify_url,
        now=datetime.now(),
    )


@payroll_bp.route("/fee-slip/<int:payout_id>/pdf", methods=["GET"])
@login_required
def fee_slip_pdf(payout_id):
    """Download fee slip sebagai PDF menggunakan ReportLab"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    payout = TutorPayout.query.get_or_404(payout_id)
    tutor = payout.tutor
    sessions = _get_sessions_for_payout(payout)
    total = sum(float(s.tutor_fee_amount or 0) for s in sessions)

    GOLD = colors.HexColor("#DAA520")
    YELLOW = colors.HexColor("#FFD700")
    LIGHT_YELLOW = colors.HexColor("#FFFDE7")

    MONTHS_ID = [
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
    DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

    payout_dt = payout.payout_date or datetime.now()
    date_id = f"{payout_dt.day} {MONTHS_ID[payout_dt.month - 1]} {payout_dt.year}"

    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", fontSize=8, fontName="Helvetica", leading=10)
    small_bold = ParagraphStyle(
        "small_bold", fontSize=8, fontName="Helvetica-Bold", leading=10
    )
    normal = ParagraphStyle("normal", fontSize=9, fontName="Helvetica", leading=12)
    bold = ParagraphStyle("bold", fontSize=9, fontName="Helvetica-Bold", leading=12)
    title_style = ParagraphStyle(
        "title", fontSize=13, fontName="Helvetica-Bold", alignment=1, leading=16
    )
    center_small = ParagraphStyle(
        "center_small", fontSize=8, fontName="Helvetica", alignment=1
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    elements = []

    # ── Header ──────────────────────────────────────────────────────────────
    header_left = [
        [Paragraph("<b>LEMBAGA BIMBINGAN BELAJAR</b>", bold)],
        [Paragraph("<b>SUPER SMART</b>", bold)],
        [Paragraph("Jl. Menur Pumpungan No 63, Sukolilo, Surabaya", small)],
        [Paragraph("Email: lbbsupersmart@gmail.com", small)],
        [Paragraph("Handphone: 0895-6359-07419", small)],
    ]
    header_left_tbl = Table(header_left, colWidths=[12 * cm])
    header_left_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), YELLOW),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    verify_url = f"{request.host_url.rstrip('/')}/payroll/fee-slip/{payout_id}/verify"
    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=90x90&data={quote(verify_url, safe='')}"
    )
    try:
        import tempfile
        import urllib.request

        from PIL import Image as PILImage
        from reportlab.platypus import Image as RLImage

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            urllib.request.urlretrieve(qr_url, tmp.name)
            qr_img = RLImage(tmp.name, width=2.5 * cm, height=2.5 * cm)
        qr_cell = qr_img
    except Exception:
        qr_cell = Paragraph("QR\nCode", center_small)

    header_tbl = Table(
        [[header_left_tbl, qr_cell]],
        colWidths=[13 * cm, 3.5 * cm],
    )
    header_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), YELLOW),
                ("BOX", (0, 0), (-1, -1), 1.5, GOLD),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(header_tbl)
    elements.append(Spacer(1, 0.4 * cm))

    # ── Judul ───────────────────────────────────────────────────────────────
    elements.append(Paragraph("<b>Fee Tutor</b>", title_style))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=GOLD))
    elements.append(Spacer(1, 0.3 * cm))

    # ── Info Tutor ───────────────────────────────────────────────────────────
    info_data = [
        [
            Paragraph("<b>Nama</b>", bold),
            Paragraph(":", normal),
            Paragraph(tutor.name, normal),
            Paragraph("<b>Tanggal</b>", bold),
            Paragraph(":", normal),
            Paragraph(date_id, normal),
        ],
        [
            Paragraph("<b>Email</b>", bold),
            Paragraph(":", normal),
            Paragraph(tutor.email or "-", normal),
            Paragraph("<b>No. Rekening</b>", bold),
            Paragraph(":", normal),
            Paragraph(tutor.bank_account_number or "-", normal),
        ],
        [
            Paragraph("<b>ID Tutor</b>", bold),
            Paragraph(":", normal),
            Paragraph(tutor.tutor_code, normal),
            Paragraph("<b>Bank</b>", bold),
            Paragraph(":", normal),
            Paragraph(tutor.bank_name or "-", normal),
        ],
    ]
    info_tbl = Table(
        info_data, colWidths=[2.5 * cm, 0.4 * cm, 5 * cm, 3 * cm, 0.4 * cm, 5.2 * cm]
    )
    info_tbl.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(info_tbl)
    elements.append(Spacer(1, 0.3 * cm))

    # ── Summary ──────────────────────────────────────────────────────────────
    summary_tbl = Table(
        [
            [
                Paragraph(f"<b>{len(sessions)} sesi</b>", bold),
                Paragraph(f"<b>Total: Rp {total:,.0f}</b>", bold),
            ]
        ],
        colWidths=[10 * cm, 6.5 * cm],
    )
    summary_tbl.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(summary_tbl)
    elements.append(Spacer(1, 0.2 * cm))

    # ── Tabel Sesi ───────────────────────────────────────────────────────────
    tbl_header = [
        Paragraph("<b>No</b>", small_bold),
        Paragraph("<b>Tanggal</b>", small_bold),
        Paragraph("<b>Hari</b>", small_bold),
        Paragraph("<b>Siswa</b>", small_bold),
        Paragraph("<b>Kurikulum</b>", small_bold),
        Paragraph("<b>Jenjang</b>", small_bold),
        Paragraph("<b>Mapel</b>", small_bold),
        Paragraph("<b>Nominal</b>", small_bold),
    ]
    tbl_rows = [tbl_header]
    for i, sess in enumerate(sessions, 1):
        d = sess.session_date
        date_str = f"{d.day:02d}/{d.month:02d}/{str(d.year)[2:]}"
        day_name = DAYS_ID[d.weekday()]
        student_name = sess.student.name if sess.student else "-"
        curriculum = (
            sess.enrollment.curriculum.name
            if sess.enrollment
            and hasattr(sess.enrollment, "curriculum")
            and sess.enrollment.curriculum
            else "-"
        )
        level = (
            sess.enrollment.level.name
            if sess.enrollment
            and hasattr(sess.enrollment, "level")
            and sess.enrollment.level
            else "-"
        )
        subject = sess.subject.name if sess.subject else "-"
        nominal = f"Rp {float(sess.tutor_fee_amount or 0):,.0f}"

        tbl_rows.append(
            [
                Paragraph(str(i), small),
                Paragraph(date_str, small),
                Paragraph(day_name, small),
                Paragraph(student_name, small),
                Paragraph(curriculum, small),
                Paragraph(level, small),
                Paragraph(subject, small),
                Paragraph(nominal, small),
            ]
        )

    col_w = [
        0.8 * cm,
        2 * cm,
        1.6 * cm,
        3.5 * cm,
        2.6 * cm,
        1.8 * cm,
        2.6 * cm,
        2.1 * cm,
    ]
    sess_tbl = Table(tbl_rows, colWidths=col_w, repeatRows=1)
    row_bg = [colors.white, LIGHT_YELLOW]
    sess_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), YELLOW),
                ("GRID", (0, 0), (-1, -1), 0.5, GOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (7, 0), (7, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                *[
                    ("BACKGROUND", (0, r), (-1, r), row_bg[(r - 1) % 2])
                    for r in range(1, len(tbl_rows))
                ],
            ]
        )
    )
    elements.append(sess_tbl)
    elements.append(Spacer(1, 1 * cm))

    # ── Footer / Tanda Tangan ────────────────────────────────────────────────
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    footer_data = [
        [
            Paragraph(
                '"We sincerely appreciate your hard work\nand dedication to our students."',
                small,
            ),
            Paragraph(f"Surabaya, {date_id}", center_small),
        ],
        ["", Paragraph("", normal)],
        ["", Paragraph("", normal)],
        [
            Paragraph(f"<i>Dicetak: {now_str}</i>", small),
            Paragraph("<b>Yoga Aji Sukma, S.Mat., M.Stat.</b>", center_small),
        ],
        ["", Paragraph("CEO", center_small)],
    ]
    footer_tbl = Table(footer_data, colWidths=[9 * cm, 7.5 * cm])
    footer_tbl.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(footer_tbl)

    doc.build(elements)
    buf.seek(0)

    safe_name = secure_filename(f"fee_slip_{payout_id}_{tutor.tutor_code}.pdf")
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=safe_name,
    )


@payroll_bp.route("/fee-slip/<int:payout_id>/verify", methods=["GET"])
def fee_slip_verify(payout_id):
    """Verifikasi fee slip via QR code scan (tidak perlu login)"""
    payout = TutorPayout.query.get_or_404(payout_id)
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
