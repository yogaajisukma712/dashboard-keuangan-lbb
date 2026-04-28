"""
Quota Alert dan Invoice routes untuk Dashboard Keuangan LBB Super Smart
Mengelola quota alert siswa dan pembuatan invoice sederhana.
"""

from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    Student,
    StudentPayment,
    StudentPaymentLine,
)

quota_invoice_bp = Blueprint("quota_invoice", __name__, url_prefix="/quota")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _first_of_month(year: int, month: int) -> date:
    """Kembalikan tanggal pertama dari bulan yang diberikan."""
    return date(year, month, 1)


def calc_quota(enr_id: int, service_month_date: date) -> dict:
    """
    Hitung kuota berbayar vs terpakai untuk sebuah enrollment pada bulan tertentu.

    Returns:
        dict dengan keys: paid, used, remaining
    """
    month = service_month_date.month
    year = service_month_date.year

    paid = (
        db.session.query(
            db.func.coalesce(db.func.sum(StudentPaymentLine.meeting_count), 0)
        )
        .filter(
            StudentPaymentLine.enrollment_id == enr_id,
            StudentPaymentLine.service_month == service_month_date,
        )
        .scalar()
    )

    used = (
        db.session.query(db.func.count(AttendanceSession.id))
        .filter(
            AttendanceSession.enrollment_id == enr_id,
            db.extract("month", AttendanceSession.session_date) == month,
            db.extract("year", AttendanceSession.session_date) == year,
            AttendanceSession.status == "attended",
        )
        .scalar()
    )

    remaining = int(paid) - int(used)
    return {"paid": int(paid), "used": int(used), "remaining": remaining}


def count_quota_alerts() -> int:
    """
    Hitung jumlah enrollment aktif dengan sisa quota <= 0 pada bulan berjalan.
    Dipakai oleh context processor di __init__.py untuk badge di navbar.
    Dibungkus try/except agar error DB tidak merusak setiap halaman.
    """
    try:
        today = date.today()
        service_month_date = _first_of_month(today.year, today.month)

        active_enrollments = Enrollment.query.filter_by(
            status="active", is_active=True
        ).all()

        count = 0
        for enr in active_enrollments:
            quota = calc_quota(enr.id, service_month_date)
            if quota["remaining"] <= 0:
                count += 1
        return count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@quota_invoice_bp.route("/alerts", methods=["GET"])
@login_required
def quota_alerts():
    """Tampilkan semua enrollment dengan sisa quota <= 0 pada bulan berjalan."""
    today = date.today()
    service_month_date = _first_of_month(today.year, today.month)

    active_enrollments = Enrollment.query.filter_by(
        status="active", is_active=True
    ).all()

    alerts = []
    for enr in active_enrollments:
        quota = calc_quota(enr.id, service_month_date)
        if quota["remaining"] <= 0:
            alerts.append(
                {
                    "enrollment": enr,
                    "student": enr.student,
                    "subject": enr.subject,
                    "tutor": enr.tutor,
                    "paid": quota["paid"],
                    "used": quota["used"],
                    "remaining": quota["remaining"],
                    "service_month": service_month_date,
                }
            )

    return render_template(
        "quota/alerts.html",
        alerts=alerts,
        service_month=service_month_date,
    )


@quota_invoice_bp.route("/student/<int:student_id>", methods=["GET"])
@login_required
def student_quota_detail(student_id):
    """Tampilkan detail quota semua enrollment milik seorang siswa."""
    student = Student.query.get_or_404(student_id)
    today = date.today()

    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)
    service_month_date = _first_of_month(year, month)

    enrollments = Enrollment.query.filter_by(
        student_id=student_id, is_active=True
    ).all()

    quota_details = []
    for enr in enrollments:
        quota = calc_quota(enr.id, service_month_date)
        quota_details.append(
            {
                "enrollment": enr,
                "subject": enr.subject,
                "tutor": enr.tutor,
                "paid": quota["paid"],
                "used": quota["used"],
                "remaining": quota["remaining"],
            }
        )

    return render_template(
        "quota/student_detail.html",
        student=student,
        quota_details=quota_details,
        service_month=service_month_date,
    )


@quota_invoice_bp.route("/invoice/create", methods=["POST"])
@login_required
def create_invoice():
    """
    Buat invoice baru.

    Menerima data dari form HTML atau JSON:
        enrollment_id   : int   (wajib)
        service_month   : str   YYYY-MM atau YYYY-MM-DD (wajib)
        amount          : float
        notes           : str
    """
    # Support both JSON and HTML form
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    enrollment_id = data.get("enrollment_id")
    service_month_str = data.get("service_month", "")
    amount = data.get("amount", 0)
    notes = data.get("notes", "")

    def _error(msg, status=400):
        if request.is_json:
            return jsonify({"error": msg}), status
        flash(msg, "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    if not enrollment_id or not service_month_str:
        return _error("enrollment_id dan service_month wajib diisi.")

    # Parse service_month → normalisasi ke hari pertama bulan
    try:
        sm_str = str(service_month_str).strip()
        if len(sm_str) == 7:  # YYYY-MM
            service_month_date = datetime.strptime(sm_str, "%Y-%m").date()
        else:  # YYYY-MM-DD
            service_month_date = datetime.strptime(sm_str[:10], "%Y-%m-%d").date()
        service_month_date = date(service_month_date.year, service_month_date.month, 1)
    except (ValueError, TypeError):
        return _error("Format service_month tidak valid. Gunakan YYYY-MM.")

    enrollment = Enrollment.query.get_or_404(int(enrollment_id))

    try:
        result = db.session.execute(
            db.text(
                """
                INSERT INTO student_invoices
                    (student_id, enrollment_id, service_month, amount,
                     status, notes, created_by, created_at, updated_at)
                VALUES
                    (:student_id, :enrollment_id, :service_month, :amount,
                     'draft', :notes, :created_by, NOW(), NOW())
                RETURNING id
                """
            ),
            {
                "student_id": enrollment.student_id,
                "enrollment_id": int(enrollment_id),
                "service_month": service_month_date,
                "amount": float(amount),
                "notes": notes,
                "created_by": current_user.id,
            },
        )
        invoice_id = result.fetchone()[0]
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return _error(f"Gagal membuat invoice: {exc}", 500)

    if request.is_json:
        return jsonify({"success": True, "invoice_id": invoice_id}), 201

    flash(f"Invoice #{invoice_id} berhasil dibuat.", "success")
    return redirect(url_for("quota_invoice.invoice_detail", invoice_id=invoice_id))


@quota_invoice_bp.route("/invoice/<int:invoice_id>/complete", methods=["POST"])
@login_required
def complete_invoice(invoice_id):
    """
    Selesaikan invoice:
    - Ubah status menjadi 'paid'
    - Buat StudentPayment + StudentPaymentLine untuk menambah quota
    """
    row = db.session.execute(
        db.text("SELECT * FROM student_invoices WHERE id = :id"),
        {"id": invoice_id},
    ).fetchone()

    if not row:
        flash("Invoice tidak ditemukan.", "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    if row.status == "paid":
        flash("Invoice ini sudah diselesaikan sebelumnya.", "warning")
        return redirect(url_for("quota_invoice.invoice_detail", invoice_id=invoice_id))

    enrollment = Enrollment.query.get_or_404(row.enrollment_id)

    try:
        student_rate = float(enrollment.student_rate_per_meeting)
        tutor_rate = float(enrollment.tutor_rate_per_meeting)
        amount = float(row.amount)

        # Hitung jumlah pertemuan berdasarkan nominal invoice
        if student_rate > 0:
            meeting_count = max(1, round(amount / student_rate))
        else:
            meeting_count = 1

        nominal_amount = meeting_count * student_rate
        tutor_payable_amount = meeting_count * tutor_rate
        margin_amount = nominal_amount - tutor_payable_amount

        # Buat receipt number unik
        receipt_number = (
            f"INV-{invoice_id:05d}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        # Buat header StudentPayment
        payment = StudentPayment(
            payment_date=datetime.utcnow(),
            student_id=row.student_id,
            receipt_number=receipt_number,
            payment_method="invoice",
            total_amount=amount,
            notes=f"Dari Invoice #{invoice_id}"
            + (f": {row.notes}" if row.notes else ""),
            is_verified=True,
            verified_by=current_user.id,
            verified_at=datetime.utcnow(),
        )
        db.session.add(payment)
        db.session.flush()  # Dapatkan payment.id sebelum commit

        # Buat StudentPaymentLine untuk menambah quota
        payment_line = StudentPaymentLine(
            student_payment_id=payment.id,
            enrollment_id=row.enrollment_id,
            service_month=row.service_month,
            meeting_count=meeting_count,
            student_rate_per_meeting=student_rate,
            tutor_rate_per_meeting=tutor_rate,
            nominal_amount=nominal_amount,
            tutor_payable_amount=tutor_payable_amount,
            margin_amount=margin_amount,
            notes=f"Dari Invoice #{invoice_id}",
        )
        db.session.add(payment_line)

        # Update status invoice menjadi 'paid'
        db.session.execute(
            db.text(
                "UPDATE student_invoices SET status='paid', updated_at=NOW() WHERE id=:id"
            ),
            {"id": invoice_id},
        )

        db.session.commit()

        flash(
            f"Invoice #{invoice_id} berhasil diselesaikan. "
            f"Quota +{meeting_count} pertemuan ditambahkan untuk {enrollment.student.name}.",
            "success",
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal menyelesaikan invoice: {exc}", "danger")

    return redirect(url_for("quota_invoice.invoice_detail", invoice_id=invoice_id))


@quota_invoice_bp.route("/invoice/<int:invoice_id>", methods=["GET"])
@login_required
def invoice_detail(invoice_id):
    """Tampilkan detail sebuah invoice."""
    row = db.session.execute(
        db.text("SELECT * FROM student_invoices WHERE id = :id"),
        {"id": invoice_id},
    ).fetchone()

    if not row:
        flash("Invoice tidak ditemukan.", "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    enrollment = Enrollment.query.get(row.enrollment_id)
    student = Student.query.get(row.student_id)

    quota = calc_quota(row.enrollment_id, row.service_month)

    return render_template(
        "quota/invoice_detail.html",
        invoice=row,
        enrollment=enrollment,
        student=student,
        quota=quota,
    )
