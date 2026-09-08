"""Surat Paklaring — generate PDF surat keterangan aktif/ Alumni siswa.

Nomor surat otomatis dari tabel `paklaring_letters` (mulai 37, tiap generate
+1). Format nomor: 037/LBB/PAK/MM/YYYY.
"""

import io
import os
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
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
from app.models.master import Student
from app.utils.decorators import admin_required
from app.utils.public_ids import encode_public_id

paklaring_bp = Blueprint("paklaring", __name__, url_prefix="/paklaring")

MONTHS_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember",
]

PAKLARING_START_NUMBER = 37


def _ensure_table():
    db.session.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS paklaring_letters (
            id SERIAL PRIMARY KEY,
            sequence_number INTEGER NOT NULL,
            letter_number TEXT NOT NULL,
            student_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            student_class TEXT,
            student_school TEXT,
            purpose TEXT,
            issued_date DATE NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT now()
        )
        """
        )
    )
    db.session.commit()


def _next_sequence_and_number(issued_date: datetime):
    """Ambil nomor urut berikutnya (mulai 37) + format nomor surat."""
    row = db.session.execute(
        text(
            "SELECT COALESCE(MAX(sequence_number), :start - 1) AS mx "
            "FROM paklaring_letters"
        ),
        {"start": PAKLARING_START_NUMBER},
    ).fetchone()
    seq = int(row.mx or (PAKLARING_START_NUMBER - 1)) + 1
    number = f"{seq:03d}/LBB/PAK/{issued_date.month:02d}/{issued_date.year}"
    return seq, number


@paklaring_bp.route("/", methods=["GET"])
@login_required
def index():
    _ensure_table()
    rows = (
        db.session.execute(
            text(
                "SELECT id, sequence_number, letter_number, student_name, "
                "student_class, student_school, purpose, issued_date "
                "FROM paklaring_letters ORDER BY sequence_number DESC LIMIT 100"
            )
        )
        .mappings()
        .all()
    )
    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()
    student_options = []
    for st in students:
        student_options.append(
            {
                "id": st.id,
                "name": st.name,
                "public_id": st.public_id,
                "class": getattr(st, "grade", "") or "",
                "school": getattr(st, "school_name", "") or "",
            }
        )
    today = datetime.now()
    next_seq, next_number = _next_sequence_and_number(today)
    return render_template(
        "paklaring/index.html",
        letters=[dict(r) for r in rows],
        students=student_options,
        next_number=next_number,
        today=today,
        today_id=f"{today.day} {MONTHS_ID[today.month]} {today.year}",
    )


@paklaring_bp.route("/generate", methods=["POST"])
@login_required
@admin_required
def generate():
    """Simpan metadata + render PDF. File PDF tidak disimpan — di-generate
    on-demand dari metadata (isi selalu konsisten)."""
    _ensure_table()
    student_id = request.form.get("student_id", type=int)
    if not student_id:
        flash("Pilih siswa terlebih dahulu.", "warning")
        return redirect(url_for("paklaring.index"))

    student = Student.query.get(student_id)
    if not student:
        abort(404)

    issued_str = request.form.get("issued_date") or datetime.now().strftime("%Y-%m-%d")
    try:
        issued = datetime.strptime(issued_str, "%Y-%m-%d")
    except ValueError:
        issued = datetime.now()

    purpose = (request.form.get("purpose") or "").strip()
    student_class = (request.form.get("student_class") or "").strip()
    student_school = (request.form.get("student_school") or "").strip()
    student_name = (request.form.get("student_name") or student.name or "").strip()

    seq, number = _next_sequence_and_number(issued)
    db.session.execute(
        text(
            "INSERT INTO paklaring_letters "
            "(sequence_number, letter_number, student_id, student_name, student_class, "
            "student_school, purpose, issued_date, created_by) "
            "VALUES (:seq, :num, :sid, :sname, :sclass, :sschool, :purpose, :issued, :by)"
        ),
        {
            "seq": seq,
            "num": number,
            "sid": student.id,
            "sname": student_name or student.name,
            "sclass": student_class,
            "sschool": student_school,
            "purpose": purpose,
            "issued": issued.date(),
            "by": getattr(request, "user_id", None),
        },
    )
    db.session.commit()
    flash(f"Surat paklaring {number} berhasil dibuat.", "success")
    return redirect(url_for("paklaring.index"))


@paklaring_bp.route("/<int:letter_id>/pdf", methods=["GET"])
@login_required
def pdf(letter_id: int):
    _ensure_table()
    row = (
        db.session.execute(
            text(
                "SELECT * FROM paklaring_letters WHERE id = :id"
            ),
            {"id": letter_id},
        )
        .mappings()
        .first()
    )
    if not row:
        abort(404)

    cfg = current_app.config
    issued = row["issued_date"]
    date_id = f"{issued.day} {MONTHS_ID[issued.month]} {issued.year}"

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
    style_center_bold = ParagraphStyle(
        "centerbold", parent=style_center, fontName="Helvetica-Bold"
    )
    style_body = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=11, leading=17, alignment=4
    )

    story = []

    # ── KOP ──────────────────────────────────────────────────────────
    logo_path = None
    for candidate in (
        os.path.join(cfg.get("ROOT_PATH", os.getcwd()), "logo.png"),
        os.path.join(cfg.get("ROOT_PATH", os.getcwd()), "app", "static", "branding", "logo.png"),
    ):
        if os.path.exists(candidate):
            logo_path = candidate
            break

    kop_left = [
        Paragraph(
            f"<b>{cfg.get('INSTITUTION_NAME', 'LBB Super Smart')}</b>",
            ParagraphStyle("kop1", parent=style_center_bold, fontSize=16, leading=20),
        ),
        Paragraph(cfg.get("INSTITUTION_TAGLINE", ""), style_center),
        Paragraph(
            cfg.get("INSTITUTION_ADDRESS", "Surabaya"), style_center
        ),
        Paragraph(f"Telp. {cfg.get('INSTITUTION_PHONE', '')}", style_center),
    ]
    kop_data = [[kop_left, ""]] if not logo_path else None
    if logo_path:
        logo = RLImage(logo_path, width=4.2 * cm, height=1.4 * cm, kind="proportional")
        kop_data = [[logo, kop_left]]
    kop = Table(kop_data, colWidths=[5.5 * cm, 11.5 * cm])
    kop.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ]
        )
    )
    story.append(kop)
    story.append(Spacer(1, 4))
    story.append(
        Table(
            [[""]],
            style=TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, 0), 2.2, colors.HexColor("#0f1d3e")),
                ]
            ),
            colWidths=[17 * cm],
        )
    )
    story.append(Spacer(1, 0.9 * cm))

    # ── Judul + nomor ───────────────────────────────────────────────
    story.append(
        Paragraph("<u>SURAT KETERANGAN</u>", ParagraphStyle("judul", parent=style_center_bold, fontSize=14, leading=18))
    )
    story.append(Paragraph(f"Nomor: {row['letter_number']}", style_center))
    story.append(Spacer(1, 0.9 * cm))

    # ── Isi ─────────────────────────────────────────────────────────
    student_name = row["student_name"]
    student_class = row["student_class"] or "-"
    student_school = row["student_school"] or "-"
    purpose = row["purpose"] or "keperluan administrasi"

    body = (
        f"Yang bertanda tangan di bawah ini, pemilik/kepala Lembaga Bimbingan Belajar "
        f"<b>{cfg.get('INSTITUTION_NAME', 'LBB Super Smart')}</b>, menerangkan dengan "
        f"sesungguhnya bahwa:<br/><br/>"
        f"<table>"
        f"<tr><td>Nama</td><td>:</td><td><b>{student_name}</b></td></tr>"
        f"<tr><td>Kelas</td><td>:</td><td>{student_class}</td></tr>"
        f"<tr><td>Sekolah</td><td>:</td><td>{student_school}</td></tr>"
        f"</table><br/>"
        f"Adalah siswa aktif pada Lembaga Bimbingan Belajar "
        f"<b>{cfg.get('INSTITUTION_NAME', 'LBB Super Smart')}</b> dan mengikuti program "
        f"bimbingan belajar di lembaga kami.<br/><br/>"
        f"Surat keterangan ini dibuat untuk keperluan <b>{purpose}</b>."
    )
    story.append(Paragraph(body, style_body))
    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            "Demikian surat keterangan ini dibuat dengan sebenarnya, untuk dipergunakan "
            "sebagaimana mestinya.",
            style_body,
        )
    )
    story.append(Spacer(1, 1.1 * cm))

    # ── Tanggal + tanda tangan ──────────────────────────────────────
    ceo_name = cfg.get("INSTITUTION_CEO_NAME", "Yoga Aji Sukma, S.Mat., M.Stat.")
    ceo_title = cfg.get("INSTITUTION_CEO_TITLE", "CEO")
    city = cfg.get("INSTITUTION_CITY", "Surabaya")

    sign = Table(
        [
            [Paragraph(f"{city}, {date_id}", style_center), ""],
            [Paragraph(f"{ceo_title} {cfg.get('INSTITUTION_NAME', 'LBB Super Smart')}", style_center), ""],
            [Spacer(1, 2.2 * cm), ""],
            [
                Paragraph(f"<b><u>{ceo_name}</u></b>", style_center),
                "",
            ],
        ],
        colWidths=[9.5 * cm, 7.5 * cm],
        hAlign="RIGHT",
    )
    sign.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sign)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    from flask import Response

    safe_name = secure_filename(f"paklaring_{student_name}_{row['sequence_number']:03d}.pdf") or "paklaring.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{safe_name}\"",
            "Cache-Control": "no-store",
        },
    )
