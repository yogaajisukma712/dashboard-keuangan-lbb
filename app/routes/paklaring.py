"""Surat Paklaring Tutor — PDF masa kerja + QR verifikasi digital publik.

- Masa kerja otomatis dari presensi pertama s.d. terakhir (attended).
- Durasi dihitung (tahun/bulan/hari).
- Tanda tangan = QR code yang mengarah ke halaman verifikasi digital
  (tanpa login) berisi metadata surat.
- Nomor surat otomatis mulai 037, format 037/LBB/PAK/MM/YYYY.
"""

import base64
import io
import os
import uuid
from datetime import datetime

import qrcode
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text
from werkzeug.utils import secure_filename

from app import db
from app.models.attendance import AttendanceSession
from app.models.master import Tutor
from app.utils.decorators import admin_required

paklaring_bp = Blueprint("paklaring", __name__, url_prefix="/paklaring")

MONTHS_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember",
]

PAKLARING_START_NUMBER = 37

DEFAULT_APPRECIATION = (
    "Menunjukkan dedikasi, profesionalisme, dan komitmen yang tinggi selama "
    "menjadi bagian dari tim pengajar kami. Kehadiran dan kontribusinya dalam "
    "membimbing para siswa sangat kami hargai, dan kami percaya pengalaman "
    "serta nilai kerjanya akan menjadi bekal berharga di masa depan."
)


def _ensure_table():
    db.session.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS paklaring_tutor_letters (
            id SERIAL PRIMARY KEY,
            sequence_number INTEGER NOT NULL UNIQUE,
            letter_number TEXT NOT NULL,
            tutor_id INTEGER NOT NULL,
            tutor_name TEXT NOT NULL,
            first_session DATE,
            last_session DATE,
            duration_text TEXT,
            total_sessions INTEGER,
            appreciation TEXT,
            purpose TEXT,
            issued_date DATE NOT NULL,
            public_token TEXT NOT NULL UNIQUE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT now()
        )
        """
        )
    )
    db.session.commit()


def _duration_text(first: datetime, last: datetime) -> str:
    """Durasi masa kerja: X tahun Y bulan Z hari."""
    months = (last.year - first.year) * 12 + (last.month - first.month)
    if last.day < first.day:
        months -= 1
    years, months = divmod(months, 12)
    # sisa hari
    anchor_year = first.year + years
    anchor_month = first.month + months
    if anchor_month > 12:
        anchor_year += 1
        anchor_month -= 12
    days = (last - datetime(anchor_year, anchor_month, first.day)).days
    parts = []
    if years > 0:
        parts.append(f"{years} tahun")
    if months > 0:
        parts.append(f"{months} bulan")
    if days > 0 or not parts:
        parts.append(f"{max(days, 0)} hari")
    return " ".join(parts)


def _tutor_work_period(tutor_id: int):
    """(first_session, last_session, total) dari presensi attended."""
    row = (
        db.session.execute(
            text(
                "SELECT MIN(CAST(session_date AS DATE)) AS first_s, "
                "MAX(CAST(session_date AS DATE)) AS last_s, "
                "COUNT(*) AS total "
                "FROM attendance_sessions "
                "WHERE tutor_id = :tid AND status = 'attended'"
            ),
            {"tid": tutor_id},
        )
        .mappings()
        .first()
    )
    return (row["first_s"], row["last_s"], int(row["total"] or 0))


def _next_sequence_and_number(issued_date: datetime):
    row = db.session.execute(
        text(
            "SELECT COALESCE(MAX(sequence_number), :start - 1) AS mx "
            "FROM paklaring_tutor_letters"
        ),
        {"start": PAKLARING_START_NUMBER},
    ).fetchone()
    seq = int(row.mx or (PAKLARING_START_NUMBER - 1)) + 1
    number = f"{seq:03d}/LBB/PAK/{issued_date.month:02d}/{issued_date.year}"
    return seq, number


def _qr_data_uri(url: str) -> str:
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@paklaring_bp.route("/", methods=["GET"])
@login_required
def index():
    _ensure_table()
    rows = (
        db.session.execute(
            text(
                "SELECT id, sequence_number, letter_number, tutor_name, "
                "first_session, last_session, duration_text, total_sessions, "
                "issued_date, public_token FROM paklaring_tutor_letters "
                "ORDER BY sequence_number DESC LIMIT 100"
            )
        )
        .mappings()
        .all()
    )
    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name).all()
    today = datetime.now()
    _, next_number = _next_sequence_and_number(today)
    return render_template(
        "paklaring/index.html",
        letters=[dict(r) for r in rows],
        tutors=tutors,
        next_number=next_number,
        today=today,
        today_id=f"{today.day} {MONTHS_ID[today.month]} {today.year}",
        base_url=request.host_url.rstrip("/"),
    )


@paklaring_bp.route("/generate", methods=["POST"])
@login_required
@admin_required
def generate():
    _ensure_table()
    tutor_id = request.form.get("tutor_id", type=int)
    if not tutor_id:
        flash("Pilih tutor terlebih dahulu.", "warning")
        return redirect(url_for("paklaring.index"))

    tutor = Tutor.query.get(tutor_id)
    if not tutor:
        abort(404)

    issued_str = request.form.get("issued_date") or datetime.now().strftime("%Y-%m-%d")
    try:
        issued = datetime.strptime(issued_str, "%Y-%m-%d")
    except ValueError:
        issued = datetime.now()

    appreciation = (request.form.get("appreciation") or "").strip() or DEFAULT_APPRECIATION
    purpose = (request.form.get("purpose") or "sebagai dokumen karier dan referensi profesional").strip()

    first_s, last_s, total = _tutor_work_period(tutor_id)
    if not first_s or not last_s:
        flash("Tutor ini belum memiliki presensi (attended) sama sekali.", "warning")
        return redirect(url_for("paklaring.index"))

    duration = _duration_text(
        datetime(first_s.year, first_s.month, first_s.day),
        datetime(last_s.year, last_s.month, last_s.day),
    )

    seq, number = _next_sequence_and_number(issued)
    token = uuid.uuid4().hex
    row = db.session.execute(
        text(
            "INSERT INTO paklaring_tutor_letters "
            "(sequence_number, letter_number, tutor_id, tutor_name, first_session, "
            "last_session, duration_text, total_sessions, appreciation, purpose, "
            "issued_date, public_token) "
            "VALUES (:seq, :num, :tid, :tname, :first, :last, :dur, :tot, :appr, :purp, :issued, :tok) "
            "RETURNING id"
        ),
        {
            "seq": seq,
            "num": number,
            "tid": tutor.id,
            "tname": tutor.name,
            "first": first_s,
            "last": last_s,
            "dur": duration,
            "tot": total,
            "appr": appreciation,
            "purp": purpose,
            "issued": issued.date(),
            "tok": token,
        },
    ).mappings().first()
    letter_id = int(row["id"])
    db.session.commit()
    flash(f"Surat paklaring {number} untuk {tutor.name} berhasil dibuat.", "success")
    return redirect(url_for("paklaring.pdf", letter_id=letter_id))


@paklaring_bp.route("/<int:letter_id>/pdf", methods=["GET"])
@login_required
def pdf(letter_id: int):
    row = _get_letter(letter_id)
    if not row:
        abort(404)

    cfg = current_app.config
    verify_url = request.host_url.rstrip("/") + "/paklaring/verify/" + row["public_token"]
    qr_data_uri = _qr_data_uri(verify_url)
    pdf_bytes = _render_pdf(row, cfg, verify_url, qr_data_uri)

    safe_name = secure_filename(f"paklaring_{row['tutor_name']}_{row['sequence_number']:03d}.pdf") or "paklaring.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"', "Cache-Control": "no-store"},
    )


def _get_letter(letter_id: int):
    return (
        db.session.execute(
            text("SELECT * FROM paklaring_tutor_letters WHERE id = :id"),
            {"id": letter_id},
        )
        .mappings()
        .first()
    )


def _render_pdf(row, cfg, verify_url: str, qr_data_uri: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.5 * cm,
        title=f"Surat Paklaring {row['letter_number']}",
    )

    styles = getSampleStyleSheet()
    style_center = ParagraphStyle("center", parent=styles["Normal"], alignment=1)
    style_center_bold = ParagraphStyle("centerbold", parent=style_center, fontName="Helvetica-Bold")
    style_body = ParagraphStyle("body", parent=styles["Normal"], fontSize=11, leading=17, alignment=4)

    story = []

    # ── KOP ──────────────────────────────────────────────────────────
    logo_path = None
    for candidate in (
        os.path.join(os.getcwd(), "logo.png"),
        os.path.join(os.getcwd(), "app", "static", "branding", "logo.png"),
    ):
        if os.path.exists(candidate):
            logo_path = candidate
            break

    inst_name = cfg.get("INSTITUTION_NAME", "LBB Super Smart")
    kop_left = [
        Paragraph(f"<b>{inst_name}</b>", ParagraphStyle("kop1", parent=style_center_bold, fontSize=16, leading=20)),
        Paragraph(cfg.get("INSTITUTION_TAGLINE", ""), style_center),
        Paragraph(cfg.get("INSTITUTION_ADDRESS", "Surabaya"), style_center),
        Paragraph(f"Telp. {cfg.get('INSTITUTION_PHONE', '')}", style_center),
    ]
    if logo_path:
        logo = RLImage(logo_path, width=4.2 * cm, height=1.4 * cm, kind="proportional")
        kop = Table([[logo, kop_left]], colWidths=[5.5 * cm, 11.5 * cm])
    else:
        kop = Table([[kop_left, ""]], colWidths=[5.5 * cm, 11.5 * cm])
    kop.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "CENTER")]))
    story.append(kop)
    story.append(Spacer(1, 4))
    story.append(
        Table(
            [[""]],
            style=TableStyle([("LINEBELOW", (0, 0), (-1, 0), 2.2, colors.HexColor("#0f1d3e"))]),
            colWidths=[17 * cm],
        )
    )
    story.append(Spacer(1, 0.9 * cm))

    # ── Judul + nomor ────────────────────────────────────────────────
    story.append(
        Paragraph("<u>SURAT KETERANGAN PENGALAMAN KERJA</u>", ParagraphStyle("judul", parent=style_center_bold, fontSize=13, leading=17))
    )
    story.append(Paragraph(f"Nomor: {row['letter_number']}", style_center))
    story.append(Spacer(1, 0.8 * cm))

    # ── Isi ──────────────────────────────────────────────────────────
    issued = row["issued_date"]
    date_id = f"{issued.day} {MONTHS_ID[issued.month]} {issued.year}"
    first_id = f"{row['first_session'].day} {MONTHS_ID[row['first_session'].month]} {row['first_session'].year}"
    last_id = f"{row['last_session'].day} {MONTHS_ID[row['last_session'].month]} {row['last_session'].year}"

    intro = (
        f"Yang bertanda tangan di bawah ini, pemilik/kepala Lembaga Bimbingan Belajar "
        f"<b>{inst_name}</b>, menerangkan dengan sesungguhnya bahwa:<br/><br/>"
        f"<b>{row['tutor_name']}</b> telah bekerja sebagai Tutor/Guru Bimbingan Belajar "
        f"di lembaga kami dalam periode:"
    )
    story.append(Paragraph(intro, style_body))
    story.append(Spacer(1, 0.25 * cm))

    style_ident = ParagraphStyle("ident", parent=styles["Normal"], fontSize=11, leading=17)
    ident_rows = [
        ["Mulai", first_id, ""],
        ["Sampai dengan", last_id, ""],
        ["Durasi masa kerja", f"<b>{row['duration_text']}</b>", ""],
        ["Jumlah sesi mengajar tercatat", f"{row['total_sessions']} sesi presensi", ""],
    ]
    ident_data = [
        [Paragraph(lbl, style_ident), Paragraph(":", style_ident), Paragraph(val, style_ident)]
        for lbl, val, _ in ident_rows
    ]
    ident = Table(ident_data, colWidths=[6.5 * cm, 0.6 * cm, 8.2 * cm], hAlign="LEFT")
    ident.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(ident)
    story.append(Spacer(1, 0.3 * cm))

    closing = f"Selama bekerja di lembaga kami, {row['tutor_name']} {row['appreciation'] or ''}"
    story.append(Paragraph(closing, style_body))
    story.append(Spacer(1, 0.7 * cm))
    story.append(
        Paragraph(
            "Surat keterangan pengalaman kerja ini diterbitkan untuk keperluan "
            f"{row['purpose'] or 'dokumen karier dan referensi profesional'} dan dapat "
            "diverifikasi keasliannya dengan memindai kode QR tanda tangan di bawah.",
            style_body,
        )
    )
    story.append(Spacer(1, 0.9 * cm))

    # ── Tanggal + TTD (QR verifikasi) ────────────────────────────────
    city = cfg.get("INSTITUTION_CITY", "Surabaya")
    ceo_name = cfg.get("INSTITUTION_CEO_NAME", "Yoga Aji Sukma, S.Mat., M.Stat.")
    ceo_title = cfg.get("INSTITUTION_CEO_TITLE", "CEO")

    
    qr_png_bytes = base64.b64decode(qr_data_uri.split(",")[1])
    qr_img = RLImage(
        io.BytesIO(qr_png_bytes),
        width=3.0 * cm,
        height=3.0 * cm,
    )
    sign = Table(
        [
            [Paragraph(f"{city}, {date_id}", style_center)],
            [Paragraph(f"{ceo_title} {inst_name}", style_center)],
            [Spacer(1, 0.4 * cm)],
            [qr_img],
            [Paragraph("<i>(Tanda tangan elektronik — pindai untuk verifikasi)</i>", ParagraphStyle("cap", parent=style_center, fontSize=8, leading=10))],
            [Spacer(1, 0.2 * cm)],
            [Paragraph(f"<b><u>{ceo_name}</u></b>", style_center)],
        ],
        colWidths=[7.5 * cm],
        hAlign="RIGHT",
    )
    sign.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    story.append(sign)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ── Halaman verifikasi publik (tanpa login) ─────────────────────────
@paklaring_bp.route("/verify/<token>", methods=["GET"])
def verify(token: str):
    row = (
        db.session.execute(
            text("SELECT * FROM paklaring_tutor_letters WHERE public_token = :tok"),
            {"tok": token},
        )
        .mappings()
        .first()
    )
    if not row:
        return render_template("paklaring/verify_invalid.html"), 404

    cfg = current_app.config
    inst_name = cfg.get("INSTITUTION_NAME", "LBB Super Smart")
    issued = row["issued_date"]
    date_id = f"{issued.day} {MONTHS_ID[issued.month]} {issued.year}"
    first_id = f"{row['first_session'].day} {MONTHS_ID[row['first_session'].month]} {row['first_session'].year}"
    last_id = f"{row['last_session'].day} {MONTHS_ID[row['last_session'].month]} {row['last_session'].year}"

    return render_template(
        "paklaring/verify.html",
        letter=dict(row),
        inst_name=inst_name,
        inst_tagline=cfg.get("INSTITUTION_TAGLINE", ""),
        date_id=date_id,
        first_id=first_id,
        last_id=last_id,
    )


@paklaring_bp.route("/verify-invalid", methods=["GET"])
def verify_invalid():
    return render_template("paklaring/verify_invalid.html"), 404
