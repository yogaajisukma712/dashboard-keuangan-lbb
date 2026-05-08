"""
Quota alert dan invoice siswa berbasis nama siswa.
Mendukung invoice multi-mapel dengan dua mode tagihan:
- prepaid  : tambah sesi baru saat quota habis / perlu top up
- postpaid : tagihkan sesi terhutang saat quota sudah minus
"""

from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    Student,
    StudentPayment,
    StudentPaymentLine,
)
from app.utils import (
    build_qr_code_data_uri,
    decode_public_id,
    encode_public_id,
    get_per_page,
    get_branding_logo_mark_data_uri,
)

quota_invoice_bp = Blueprint("quota_invoice", __name__, url_prefix="/quota")

MONTHS_ID = [
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

BILLING_TYPE_LABELS = {
    "prepaid": "Pra Bayar",
    "postpaid": "Pasca Bayar",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _first_of_month(year: int, month: int) -> date:
    """Kembalikan tanggal pertama dari bulan yang diberikan."""
    return date(year, month, 1)


def _shift_month(service_month_date: date, offset: int) -> date:
    """Geser tanggal awal bulan tanpa dependency eksternal."""
    month_index = service_month_date.year * 12 + service_month_date.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def build_postpaid_month_options(service_month_date: date):
    """Bulan penagihan pasca bayar: dua bulan sebelumnya + bulan berjalan."""
    options = []
    for offset in (-2, -1, 0):
        month_date = _shift_month(service_month_date, offset)
        options.append(
            {
                "value": month_date.strftime("%Y-%m"),
                "date": month_date,
                "label": _month_label(month_date),
                "is_current": offset == 0,
            }
        )
    return options


def calc_unpaid_attendance_by_month(enr_id: int, service_month_date: date) -> dict:
    """Kelompokkan sesi attended yang belum tertutup pembayaran per bulan."""
    paid = (
        db.session.query(
            db.func.coalesce(db.func.sum(StudentPaymentLine.meeting_count), 0)
        )
        .filter(StudentPaymentLine.enrollment_id == enr_id)
        .scalar()
    )
    paid_remaining = int(paid or 0)
    service_month_end = _shift_month(service_month_date, 1)
    sessions = (
        AttendanceSession.query.with_entities(AttendanceSession.session_date)
        .filter(
            AttendanceSession.enrollment_id == enr_id,
            AttendanceSession.status == "attended",
            AttendanceSession.session_date < service_month_end,
        )
        .order_by(AttendanceSession.session_date.asc(), AttendanceSession.id.asc())
        .all()
    )

    unpaid_by_month = {}
    for (session_date,) in sessions:
        if paid_remaining > 0:
            paid_remaining -= 1
            continue
        month_key = _first_of_month(session_date.year, session_date.month).strftime(
            "%Y-%m"
        )
        unpaid_by_month[month_key] = unpaid_by_month.get(month_key, 0) + 1
    return unpaid_by_month


def _month_label(service_month_date: date) -> str:
    """Format label bulan dalam bahasa Indonesia."""
    return f"{MONTHS_ID[service_month_date.month]} {service_month_date.year}"


def _safe_int(value, default=None):
    """Konversi aman ke integer."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_service_month(value) -> date:
    """Parse YYYY-MM atau YYYY-MM-DD menjadi tanggal awal bulan."""
    sm_str = str(value or "").strip()
    if not sm_str:
        raise ValueError("service_month wajib diisi")

    if len(sm_str) == 7:
        parsed = datetime.strptime(sm_str, "%Y-%m").date()
    else:
        parsed = datetime.strptime(sm_str[:10], "%Y-%m-%d").date()
    return date(parsed.year, parsed.month, 1)


def _coerce_int_list(values):
    """Ubah list/string menjadi list integer unik dengan urutan terjaga."""
    if values is None:
        return []

    if isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        raw_values = str(values).split(",")

    result = []
    for raw in raw_values:
        parsed = _safe_int(str(raw).strip())
        if parsed and parsed not in result:
            result.append(parsed)
    return result


def _request_payload():
    """Ambil payload request, baik form maupun JSON."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def _error_response(
    message, status=400, redirect_endpoint="quota_invoice.quota_alerts"
):
    """Response helper untuk form biasa dan JSON."""
    if request.is_json:
        return jsonify({"error": message}), status
    flash(message, "danger")
    return redirect(url_for(redirect_endpoint))


def calc_quota(enr_id: int, service_month_date: date) -> dict:
    """
    Hitung total quota berbayar vs total terpakai untuk sebuah enrollment.

    `service_month_date` tetap diterima untuk kompatibilitas pemanggil invoice,
    tetapi saldo sesi sengaja kumulatif lintas bulan agar invoice bisa memakai
    sisa sesi total siswa, bukan reset per bulan.

    Returns:
        dict dengan keys: paid, used, remaining
    """
    paid = (
        db.session.query(
            db.func.coalesce(db.func.sum(StudentPaymentLine.meeting_count), 0)
        )
        .filter(
            StudentPaymentLine.enrollment_id == enr_id,
        )
        .scalar()
    )

    used = (
        db.session.query(db.func.count(AttendanceSession.id))
        .filter(
            AttendanceSession.enrollment_id == enr_id,
            AttendanceSession.status == "attended",
        )
        .scalar()
    )

    remaining = int(paid) - int(used)
    return {"paid": int(paid), "used": int(used), "remaining": remaining}


def _get_student_quota_details(student_id: int, service_month_date: date):
    """Ambil detail quota seluruh enrollment aktif milik siswa."""
    enrollments = Enrollment.query.filter_by(
        student_id=student_id,
        status="active",
        is_active=True,
    ).all()

    details = []
    for enrollment in enrollments:
        quota = calc_quota(enrollment.id, service_month_date)
        postpaid_month_counts = calc_unpaid_attendance_by_month(
            enrollment.id, service_month_date
        )
        details.append(
            {
                "enrollment": enrollment,
                "subject": enrollment.subject,
                "tutor": enrollment.tutor,
                "paid": quota["paid"],
                "used": quota["used"],
                "remaining": quota["remaining"],
                "deficit": max(0, -quota["remaining"]),
                "postpaid_month_counts": postpaid_month_counts,
                "is_problem": quota["remaining"] <= 0,
            }
        )

    return sorted(
        details,
        key=lambda item: (
            item["subject"].name.lower() if item.get("subject") else "",
            item["enrollment"].id,
        ),
    )


def _build_quota_summary(quota_details):
    """Summarize quota detail rows for one student."""
    return {
        "total_enrollments": len(quota_details),
        "total_paid_sessions": sum(item["paid"] for item in quota_details),
        "total_used_sessions": sum(item["used"] for item in quota_details),
        "total_remaining_sessions": sum(item["remaining"] for item in quota_details),
        "problem_subject_count": sum(1 for item in quota_details if item["remaining"] <= 0),
        "zero_subject_count": sum(1 for item in quota_details if item["remaining"] == 0),
        "minus_subject_count": sum(1 for item in quota_details if item["remaining"] < 0),
        "total_debt_sessions": sum(item["deficit"] for item in quota_details),
        "has_alert": any(item["remaining"] <= 0 for item in quota_details),
    }


def _get_student_quota_alert_map(student_ids, service_month_date: date):
    """Return alert summary keyed by student_id for the selected period."""
    active_student_ids = {
        student_id
        for (student_id,) in db.session.query(Student.id)
        .filter(Student.id.in_(student_ids), Student.is_active.is_(True))
        .all()
    }
    summary_map = {}
    for student_id in active_student_ids:
        details = _get_student_quota_details(student_id, service_month_date)
        summary = _build_quota_summary(details)
        if summary["has_alert"]:
            summary_map[student_id] = summary
    return summary_map


def _get_student_invoice_history(student_id: int, limit=None):
    """Fetch invoice history for a student."""
    params = {"student_id": student_id}
    limit_sql = ""
    if limit is not None:
        params["limit"] = int(limit)
        limit_sql = "LIMIT :limit"

    rows = (
        db.session.execute(
            db.text(
                f"""
                SELECT
                    si.*,
                    COALESCE(line_stats.line_count, 0) AS line_count
                FROM student_invoices si
                LEFT JOIN (
                    SELECT invoice_id, COUNT(*) AS line_count
                    FROM student_invoice_lines
                    GROUP BY invoice_id
                ) AS line_stats ON line_stats.invoice_id = si.id
                WHERE si.student_id = :student_id
                ORDER BY si.created_at DESC, si.id DESC
                {limit_sql}
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        item = dict(row)
        item["public_id"] = encode_public_id("student_invoice", item["id"])
        result.append(item)
    return result


def _get_student_by_ref_or_404(student_ref: str):
    """Resolve opaque student ref to model instance."""
    try:
        student_id = decode_public_id(student_ref, "student")
    except ValueError:
        abort(404)
    return Student.query.get_or_404(student_id)


def _encode_invoice_public_id(invoice_id: int):
    """Encode invoice integer id into opaque public ref."""
    return encode_public_id("student_invoice", invoice_id)


def _decode_invoice_ref_or_404(invoice_ref: str):
    """Decode opaque invoice ref to integer id."""
    try:
        return decode_public_id(invoice_ref, "student_invoice")
    except ValueError:
        abort(404)


def _fetch_invoice(invoice_id: int):
    """Ambil header invoice."""
    row = (
        db.session.execute(
            db.text("SELECT * FROM student_invoices WHERE id = :id"),
            {"id": invoice_id},
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    invoice = dict(row)
    invoice["public_id"] = _encode_invoice_public_id(invoice["id"])
    return invoice


def _fetch_invoice_lines(invoice_id: int):
    """Ambil detail line invoice beserta informasi mapel/tutor."""
    rows = (
        db.session.execute(
            db.text(
                """
            SELECT
                l.*,
                s.name  AS subject_name,
                t.name  AS tutor_name,
                e.meeting_quota_per_month,
                e.grade,
                lv.name AS level_name
            FROM student_invoice_lines l
            JOIN enrollments e ON e.id = l.enrollment_id
            LEFT JOIN subjects s ON s.id = e.subject_id
            LEFT JOIN tutors t ON t.id = e.tutor_id
            LEFT JOIN levels lv ON lv.id = e.level_id
            WHERE l.invoice_id = :invoice_id
            ORDER BY l.service_month, LOWER(COALESCE(s.name, '')), l.enrollment_id
            """
            ),
            {"invoice_id": invoice_id},
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        item = dict(row)
        item["invoice_public_id"] = _encode_invoice_public_id(item["invoice_id"])
        result.append(item)
    return result


def _build_legacy_invoice_lines(invoice: dict):
    """Fallback untuk invoice lama yang masih satu enrollment/satu nominal."""
    enrollment_id = invoice.get("enrollment_id")
    if not enrollment_id:
        return []

    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return []

    service_month = invoice.get("service_month")
    if not service_month:
        return []

    quota = calc_quota(enrollment.id, service_month)

    student_rate = float(enrollment.student_rate_per_meeting or 0)
    tutor_rate = float(enrollment.tutor_rate_per_meeting or 0)
    amount = float(invoice.get("amount") or 0)

    if student_rate > 0:
        meeting_count = max(1, round(amount / student_rate))
    else:
        meeting_count = 1

    nominal_amount = meeting_count * student_rate
    tutor_payable_amount = meeting_count * tutor_rate
    margin_amount = nominal_amount - tutor_payable_amount

    return [
        {
            "invoice_id": invoice.get("id"),
            "enrollment_id": enrollment.id,
            "service_month": service_month,
            "billing_type": invoice.get("billing_type") or "prepaid",
            "meeting_count": meeting_count,
            "student_rate_per_meeting": student_rate,
            "tutor_rate_per_meeting": tutor_rate,
            "nominal_amount": nominal_amount,
            "tutor_payable_amount": tutor_payable_amount,
            "margin_amount": margin_amount,
            "quota_paid_before": quota["paid"],
            "quota_used_before": quota["used"],
            "quota_remaining_before": quota["remaining"],
            "notes": invoice.get("notes") or "Invoice legacy satu mapel",
            "subject_name": enrollment.subject.name if enrollment.subject else "—",
            "tutor_name": enrollment.tutor.name if enrollment.tutor else "—",
            "meeting_quota_per_month": enrollment.meeting_quota_per_month,
            "grade": enrollment.grade,
            "level_name": enrollment.level.name if enrollment.level else "",
        }
    ]


def _build_invoice_lines(
    student: Student, service_month_date: date, billing_type: str, data
):
    """Bangun detail line invoice dari enrollment yang dipilih."""
    if request.is_json:
        selected_ids = _coerce_int_list(
            data.get("selected_enrollment_ids") or data.get("enrollment_ids")
        )
    else:
        selected_ids = _coerce_int_list(request.form.getlist("selected_enrollment_ids"))

    if not selected_ids and data.get("enrollment_id"):
        selected_ids = _coerce_int_list([data.get("enrollment_id")])

    if not selected_ids:
        raise ValueError("Pilih minimal satu mata pelajaran yang akan ditagihkan.")

    json_items = {}
    if request.is_json and isinstance(data.get("items"), list):
        for item in data.get("items", []):
            enrollment_id = _safe_int(item.get("enrollment_id"))
            if enrollment_id:
                json_items[enrollment_id] = item

    def add_line(enrollment, line_month, meeting_count, quota, note):
        student_rate = float(enrollment.student_rate_per_meeting or 0)
        tutor_rate = float(enrollment.tutor_rate_per_meeting or 0)
        amounts = StudentPaymentLine.calculate_amounts(
            meeting_count, student_rate, tutor_rate
        )
        lines.append(
            {
                "enrollment_id": enrollment.id,
                "service_month": line_month,
                "billing_type": billing_type,
                "meeting_count": meeting_count,
                "student_rate_per_meeting": student_rate,
                "tutor_rate_per_meeting": tutor_rate,
                "nominal_amount": float(amounts["nominal_amount"]),
                "tutor_payable_amount": float(amounts["tutor_payable_amount"]),
                "margin_amount": float(amounts["margin_amount"]),
                "quota_paid_before": quota["paid"],
                "quota_used_before": quota["used"],
                "quota_remaining_before": quota["remaining"],
                "notes": note,
            }
        )

    lines = []
    for enrollment_id in selected_ids:
        enrollment = Enrollment.query.filter_by(
            id=enrollment_id,
            student_id=student.id,
            status="active",
            is_active=True,
        ).first()

        if not enrollment:
            raise ValueError(
                f"Enrollment #{enrollment_id} tidak valid untuk siswa {student.name}."
            )

        quota = calc_quota(enrollment.id, service_month_date)
        subject_name = (
            enrollment.subject.name if enrollment.subject else f"Mapel #{enrollment.id}"
        )

        if billing_type == "postpaid":
            monthly_counts = []
            if request.is_json:
                raw_months = (json_items.get(enrollment.id) or {}).get("months") or []
                for item in raw_months:
                    try:
                        month_date = _parse_service_month(item.get("service_month"))
                    except (TypeError, ValueError, AttributeError):
                        continue
                    count = _safe_int(item.get("meeting_count"), 0)
                    if count > 0:
                        monthly_counts.append((month_date, count))
            else:
                prefix = f"postpaid_month_count_{enrollment.id}_"
                for key, raw_value in request.form.items():
                    if not key.startswith(prefix):
                        continue
                    month_value = key.removeprefix(prefix)
                    try:
                        month_date = _parse_service_month(month_value)
                    except (TypeError, ValueError):
                        continue
                    count = _safe_int(raw_value, 0)
                    if count > 0:
                        monthly_counts.append((month_date, count))

            if monthly_counts:
                seen_months = set()
                for month_date, meeting_count in sorted(monthly_counts):
                    if month_date in seen_months:
                        continue
                    seen_months.add(month_date)
                    month_quota = calc_quota(enrollment.id, month_date)
                    add_line(
                        enrollment,
                        month_date,
                        meeting_count,
                        month_quota,
                        f"Pasca Bayar {_month_label(month_date)}",
                    )
                continue

            meeting_count = max(0, -quota["remaining"])
            if meeting_count <= 0:
                raise ValueError(
                    f"Mapel {subject_name} tidak memiliki sesi terhutang / minus untuk ditagihkan."
                )
            add_line(
                enrollment,
                service_month_date,
                meeting_count,
                quota,
                BILLING_TYPE_LABELS.get(billing_type, billing_type),
            )
            continue
        else:
            raw_count = None
            if request.is_json:
                raw_count = (json_items.get(enrollment.id) or {}).get("meeting_count")
            if raw_count in (None, ""):
                raw_count = data.get(f"meeting_count_{enrollment.id}")

            meeting_count = _safe_int(raw_count, 0)
            if meeting_count <= 0:
                raise ValueError(
                    f"Jumlah sesi pra bayar untuk mapel {subject_name} harus lebih dari 0."
                )
        add_line(
            enrollment,
            service_month_date,
            meeting_count,
            quota,
            BILLING_TYPE_LABELS.get(billing_type, billing_type),
        )

    return lines


def count_quota_alerts() -> int:
    """
    Hitung jumlah siswa aktif yang memiliki minimal satu enrollment
    dengan sisa quota <= 0 pada bulan berjalan.
    """
    try:
        today = date.today()
        service_month_date = _first_of_month(today.year, today.month)

        active_enrollments = (
            Enrollment.query.join(Enrollment.student)
            .filter(
                Enrollment.status == "active",
                Enrollment.is_active.is_(True),
                Student.is_active.is_(True),
            )
            .all()
        )

        student_ids = set()
        for enrollment in active_enrollments:
            quota = calc_quota(enrollment.id, service_month_date)
            if quota["remaining"] <= 0:
                student_ids.add(enrollment.student_id)
        return len(student_ids)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@quota_invoice_bp.route("/alerts", methods=["GET"])
@login_required
def quota_alerts():
    """Tampilkan alert quota per siswa untuk bulan berjalan."""
    today = date.today()
    service_month_date = _first_of_month(today.year, today.month)

    active_enrollments = (
        Enrollment.query.join(Enrollment.student)
        .filter(
            Enrollment.status == "active",
            Enrollment.is_active.is_(True),
            Student.is_active.is_(True),
        )
        .all()
    )

    grouped = {}
    for enrollment in active_enrollments:
        quota = calc_quota(enrollment.id, service_month_date)
        if quota["remaining"] > 0:
            continue

        bucket = grouped.setdefault(
            enrollment.student_id,
            {
                "student": enrollment.student,
                "subjects": [],
                "problem_subject_count": 0,
                "zero_subject_count": 0,
                "minus_subject_count": 0,
                "total_debt_sessions": 0,
            },
        )

        bucket["subjects"].append(
            {
                "enrollment": enrollment,
                "subject": enrollment.subject,
                "tutor": enrollment.tutor,
                "paid": quota["paid"],
                "used": quota["used"],
                "remaining": quota["remaining"],
                "deficit": max(0, -quota["remaining"]),
            }
        )
        bucket["problem_subject_count"] += 1

        if quota["remaining"] == 0:
            bucket["zero_subject_count"] += 1
        else:
            bucket["minus_subject_count"] += 1
            bucket["total_debt_sessions"] += max(0, -quota["remaining"])

    alerts = sorted(
        grouped.values(),
        key=lambda item: item["student"].name.lower() if item.get("student") else "",
    )
    for item in alerts:
        item["subjects"] = sorted(
            item["subjects"],
            key=lambda row: row["subject"].name.lower() if row.get("subject") else "",
        )

    return render_template(
        "quota/alerts.html",
        alerts=alerts,
        service_month=service_month_date,
        service_month_label=_month_label(service_month_date),
    )


@quota_invoice_bp.route("/student/<string:student_ref>", methods=["GET"])
@login_required
def student_quota_detail(student_ref):
    """Redirect detail quota siswa ke dashboard siswa terpadu."""
    student = _get_student_by_ref_or_404(student_ref)
    today = date.today()

    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)
    return redirect(
        url_for(
            "master.student_detail",
            student_ref=student.public_id,
            month=month,
            year=year,
        )
    )


@quota_invoice_bp.route("/student/<string:student_ref>/refresh", methods=["POST"])
@login_required
def refresh_student_quota(student_ref):
    """Refresh detail siswa agar quota dibaca ulang dari pembayaran dan presensi."""
    student = _get_student_by_ref_or_404(student_ref)
    today = date.today()
    month = request.form.get("month", today.month, type=int)
    year = request.form.get("year", today.year, type=int)

    db.session.expire_all()
    flash(
        "Perhitungan sesi diperbarui dari riwayat pembayaran dan presensi terbaru.",
        "success",
    )
    return redirect(
        url_for(
            "master.student_detail",
            student_ref=student.public_id,
            month=month,
            year=year,
            refreshed=1,
        )
    )


@quota_invoice_bp.route("/invoice/create", methods=["POST"])
@login_required
def create_invoice():
    """
    Buat invoice draft per siswa dengan banyak mapel.

    Payload yang didukung:
    - student_id
    - service_month (YYYY-MM / YYYY-MM-DD)
    - billing_type: prepaid | postpaid
    - selected_enrollment_ids[]
    - meeting_count_<enrollment_id> (untuk prepaid)
    - notes
    """
    data = _request_payload()

    billing_type = str(data.get("billing_type") or "prepaid").strip().lower()
    if billing_type not in BILLING_TYPE_LABELS:
        return _error_response("billing_type harus prepaid atau postpaid.")

    try:
        service_month_date = _parse_service_month(data.get("service_month"))
    except (TypeError, ValueError):
        return _error_response("Format service_month tidak valid. Gunakan YYYY-MM.")

    student_id = _safe_int(data.get("student_id"))
    if not student_id and data.get("enrollment_id"):
        enrollment = Enrollment.query.get_or_404(_safe_int(data.get("enrollment_id")))
        student_id = enrollment.student_id

    if not student_id:
        return _error_response("student_id wajib diisi.")

    student = Student.query.get_or_404(student_id)

    try:
        lines = _build_invoice_lines(student, service_month_date, billing_type, data)
    except ValueError as exc:
        return _error_response(str(exc))

    if not lines:
        return _error_response("Tidak ada detail invoice yang bisa dibuat.")

    total_amount = sum(float(line["nominal_amount"] or 0) for line in lines)
    first_enrollment_id = lines[0]["enrollment_id"] if lines else None
    notes = (data.get("notes") or "").strip()

    try:
        result = db.session.execute(
            db.text(
                """
                INSERT INTO student_invoices
                    (student_id, enrollment_id, service_month, amount,
                     billing_type, status, notes, created_by, created_at, updated_at)
                VALUES
                    (:student_id, :enrollment_id, :service_month, :amount,
                     :billing_type, 'draft', :notes, :created_by, NOW(), NOW())
                RETURNING id
                """
            ),
            {
                "student_id": student.id,
                "enrollment_id": first_enrollment_id,
                "service_month": service_month_date,
                "amount": total_amount,
                "billing_type": billing_type,
                "notes": notes,
                "created_by": current_user.id,
            },
        )
        invoice_id = result.scalar_one()

        for line in lines:
            db.session.execute(
                db.text(
                    """
                    INSERT INTO student_invoice_lines
                        (invoice_id, enrollment_id, service_month, billing_type,
                         meeting_count, student_rate_per_meeting,
                         tutor_rate_per_meeting, nominal_amount,
                         tutor_payable_amount, margin_amount,
                         quota_paid_before, quota_used_before,
                         quota_remaining_before, notes,
                         created_at, updated_at)
                    VALUES
                        (:invoice_id, :enrollment_id, :service_month, :billing_type,
                         :meeting_count, :student_rate_per_meeting,
                         :tutor_rate_per_meeting, :nominal_amount,
                         :tutor_payable_amount, :margin_amount,
                         :quota_paid_before, :quota_used_before,
                         :quota_remaining_before, :notes,
                         NOW(), NOW())
                    """
                ),
                {
                    **line,
                    "invoice_id": invoice_id,
                },
            )

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return _error_response(f"Gagal membuat invoice: {exc}", 500)

    if request.is_json:
        return (
            jsonify(
                {
                    "success": True,
                    "invoice_id": invoice_id,
                    "billing_type": billing_type,
                    "line_count": len(lines),
                    "total_amount": total_amount,
                }
            ),
            201,
        )

    flash(
        f"Invoice #{invoice_id} berhasil dibuat untuk {student.name} "
        f"({len(lines)} mapel, {BILLING_TYPE_LABELS[billing_type]}).",
        "success",
    )
    return redirect(
        url_for(
            "quota_invoice.invoice_detail",
            invoice_ref=_encode_invoice_public_id(invoice_id),
        )
    )


@quota_invoice_bp.route("/invoice/<string:invoice_ref>/complete", methods=["POST"])
@login_required
def complete_invoice(invoice_ref):
    """
    Selesaikan invoice:
    - Ubah status menjadi 'paid'
    - Buat StudentPayment + StudentPaymentLine untuk seluruh mapel invoice
    """
    invoice_id = _decode_invoice_ref_or_404(invoice_ref)
    invoice = _fetch_invoice(invoice_id)
    if not invoice:
        flash("Invoice tidak ditemukan.", "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    if invoice.get("status") == "paid":
        flash("Invoice ini sudah diselesaikan sebelumnya.", "warning")
        return redirect(
            url_for("quota_invoice.invoice_detail", invoice_ref=invoice["public_id"])
        )

    invoice_lines = _fetch_invoice_lines(invoice_id)
    if not invoice_lines:
        invoice_lines = _build_legacy_invoice_lines(invoice)

    if not invoice_lines:
        flash("Invoice tidak memiliki detail mapel yang bisa diproses.", "danger")
        return redirect(
            url_for("quota_invoice.invoice_detail", invoice_ref=invoice["public_id"])
        )

    student = Student.query.get(invoice["student_id"])
    total_amount = sum(float(line["nominal_amount"] or 0) for line in invoice_lines)
    total_meetings = sum(int(line["meeting_count"] or 0) for line in invoice_lines)

    try:
        receipt_number = (
            f"INV-{invoice_id:05d}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        payment = StudentPayment(
            payment_date=datetime.utcnow(),
            student_id=invoice["student_id"],
            receipt_number=receipt_number,
            payment_method="invoice",
            total_amount=total_amount,
            notes=f"Dari Invoice #{invoice_id}"
            + (f": {invoice.get('notes')}" if invoice.get("notes") else ""),
            is_verified=True,
            verified_by=current_user.id,
            verified_at=datetime.utcnow(),
        )
        db.session.add(payment)
        db.session.flush()

        for line in invoice_lines:
            payment_line = StudentPaymentLine(
                student_payment_id=payment.id,
                enrollment_id=line["enrollment_id"],
                service_month=line["service_month"],
                meeting_count=int(line["meeting_count"] or 0),
                student_rate_per_meeting=float(line["student_rate_per_meeting"] or 0),
                tutor_rate_per_meeting=float(line["tutor_rate_per_meeting"] or 0),
                nominal_amount=float(line["nominal_amount"] or 0),
                tutor_payable_amount=float(line["tutor_payable_amount"] or 0),
                margin_amount=float(line["margin_amount"] or 0),
                notes=f"Dari Invoice #{invoice_id}",
            )
            db.session.add(payment_line)

        db.session.execute(
            db.text(
                """
                UPDATE student_invoices
                SET status = 'paid',
                    amount = :amount,
                    completed_payment_id = :payment_id,
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            {
                "id": invoice_id,
                "amount": total_amount,
                "payment_id": payment.id,
            },
        )

        db.session.commit()
        flash(
            f"Invoice #{invoice_id} berhasil diselesaikan. "
            f"{len(invoice_lines)} mapel / {total_meetings} sesi ditambahkan"
            f" untuk {student.name if student else 'siswa'}.",
            "success",
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal menyelesaikan invoice: {exc}", "danger")

    return redirect(
        url_for("quota_invoice.invoice_detail", invoice_ref=invoice["public_id"])
    )


@quota_invoice_bp.route("/invoice/<string:invoice_ref>/delete", methods=["POST"])
@login_required
def delete_invoice(invoice_ref):
    """Hapus invoice draft beserta detail line-nya."""
    invoice_id = _decode_invoice_ref_or_404(invoice_ref)
    invoice = _fetch_invoice(invoice_id)
    if not invoice:
        flash("Invoice tidak ditemukan.", "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    student = Student.query.get(invoice["student_id"])
    redirect_target = (
        url_for("master.student_detail", student_ref=student.public_id)
        if student
        else url_for("quota_invoice.invoice_list")
    )

    if invoice.get("status") == "paid" or invoice.get("completed_payment_id"):
        flash(
            "Invoice lunas tidak bisa dihapus dari detail siswa karena sudah terhubung ke pembayaran.",
            "warning",
        )
        return redirect(redirect_target)

    try:
        db.session.execute(
            db.text("DELETE FROM student_invoice_lines WHERE invoice_id = :id"),
            {"id": invoice_id},
        )
        db.session.execute(
            db.text("DELETE FROM student_invoices WHERE id = :id"),
            {"id": invoice_id},
        )
        db.session.commit()
        flash(f"Invoice #{invoice_id} berhasil dihapus.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Gagal menghapus invoice: {exc}", "danger")

    return redirect(redirect_target)


@quota_invoice_bp.route("/invoice/<string:invoice_ref>", methods=["GET"])
@login_required
def invoice_detail(invoice_ref):
    """Tampilkan detail invoice siswa beserta line mapelnya."""
    invoice_id = _decode_invoice_ref_or_404(invoice_ref)
    invoice = _fetch_invoice(invoice_id)
    if not invoice:
        flash("Invoice tidak ditemukan.", "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    student = Student.query.get(invoice["student_id"])
    invoice_lines = _fetch_invoice_lines(invoice_id)
    if not invoice_lines:
        invoice_lines = _build_legacy_invoice_lines(invoice)

    for line in invoice_lines:
        line["current_quota"] = calc_quota(line["enrollment_id"], line["service_month"])

    completed_payment = None
    if invoice.get("completed_payment_id"):
        completed_payment = StudentPayment.query.get(
            invoice.get("completed_payment_id")
        )

    return render_template(
        "quota/invoice_detail.html",
        invoice=invoice,
        student=student,
        invoice_lines=invoice_lines,
        completed_payment=completed_payment,
        billing_type_label=BILLING_TYPE_LABELS.get(
            invoice.get("billing_type") or "prepaid", "Pra Bayar"
        ),
        service_month_label=_month_label(invoice["service_month"]),
        total_meetings=sum(int(line["meeting_count"] or 0) for line in invoice_lines),
        total_subjects=len(invoice_lines),
        MONTHS_ID=MONTHS_ID,
    )


@quota_invoice_bp.route("/invoice/<string:invoice_ref>/verify", methods=["GET"])
def invoice_verify(invoice_ref):
    """Public invoice verification page for QR/barcode scans."""
    invoice_id = _decode_invoice_ref_or_404(invoice_ref)
    invoice = _fetch_invoice(invoice_id)
    if not invoice:
        abort(404)

    student = Student.query.get(invoice["student_id"])
    invoice_lines = _fetch_invoice_lines(invoice_id)
    if not invoice_lines:
        invoice_lines = _build_legacy_invoice_lines(invoice)

    total_amount = sum(float(line.get("nominal_amount") or line.get("line_total") or 0) for line in invoice_lines)
    total_meetings = sum(int(line.get("meeting_count") or 0) for line in invoice_lines)
    seen_subj, subjects = set(), []
    for line in invoice_lines:
        name = line.get("subject_name") or ""
        if name and name not in seen_subj:
            seen_subj.add(name)
            subjects.append(name)
    program = " & ".join(subjects) if subjects else "—"
    grade_level = "—"
    for line in invoice_lines:
        grade = line.get("grade") or ""
        level = line.get("level_name") or ""
        grade_level = (grade + " " + level).strip() or "—"
        break

    bank_str = current_app.config.get("INSTITUTION_BANK_ACCOUNTS", "")
    bank_accounts = [bank.strip() for bank in bank_str.split("|") if bank.strip()]
    reg_fee = current_app.config.get("DEFAULT_REGISTRATION_FEE", 0)
    created_at = invoice.get("created_at") or datetime.utcnow()
    invoice_verify_url = url_for(
        "quota_invoice.invoice_verify",
        invoice_ref=invoice_ref,
        _external=True,
    )

    return render_template(
        "quota/invoice_print.html",
        invoice=invoice,
        invoice_ref=invoice_ref,
        student=student,
        invoice_lines=invoice_lines,
        total_amount=total_amount,
        total_meetings=total_meetings,
        program=program,
        grade_level=grade_level,
        reg_fee=reg_fee,
        billing_type_label=BILLING_TYPE_LABELS.get(
            invoice.get("billing_type") or "prepaid", "Pra Bayar"
        ),
        service_month_label=_month_label(invoice["service_month"]),
        bank_accounts=bank_accounts,
        created_at=created_at,
        invoice_verify_url=invoice_verify_url,
        branding_logo_mark_data_uri=get_branding_logo_mark_data_uri(),
        signature_qr_data_uri=build_qr_code_data_uri(invoice_verify_url, box_size=4),
        institution_name=current_app.config.get("INSTITUTION_NAME", "LBB Super Smart"),
        institution_phone=current_app.config.get("INSTITUTION_PHONE", ""),
        institution_city=current_app.config.get("INSTITUTION_CITY", "Surabaya"),
        ceo_name=current_app.config.get("INSTITUTION_CEO_NAME", ""),
        ceo_title=current_app.config.get("INSTITUTION_CEO_TITLE", "CEO"),
        MONTHS_ID=MONTHS_ID,
        verify_mode=True,
        hide_login_link=True,
    )


@quota_invoice_bp.route("/invoices", methods=["GET"])
@login_required
def invoice_list():
    """Daftar semua invoice dengan filter dan pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = get_per_page()
    student_ref = (request.args.get("student_ref") or "").strip()
    student_id = None
    status = request.args.get("status", "").strip()
    billing_type = request.args.get("billing_type", "").strip()
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if student_ref:
        try:
            student_id = decode_public_id(student_ref, "student")
        except ValueError:
            student_id = None
    elif request.args.get("student_id", type=int):
        legacy_student = Student.query.get(request.args.get("student_id", type=int))
        if legacy_student:
            return redirect(
                url_for(
                    "quota_invoice.invoice_list",
                    page=page,
                    student_ref=legacy_student.public_id,
                    status=status,
                    billing_type=billing_type,
                    month=month,
                    year=year,
                )
            )

    where_parts = ["1=1"]
    params: dict = {}

    if student_id:
        where_parts.append("si.student_id = :student_id")
        params["student_id"] = student_id
    if status:
        where_parts.append("si.status = :status")
        params["status"] = status
    if billing_type:
        where_parts.append("COALESCE(si.billing_type,'prepaid') = :billing_type")
        params["billing_type"] = billing_type
    if month:
        where_parts.append("EXTRACT(MONTH FROM si.service_month) = :month")
        params["month"] = month
    if year:
        where_parts.append("EXTRACT(YEAR FROM si.service_month) = :year")
        params["year"] = year

    where_sql = " AND ".join(where_parts)

    count_row = db.session.execute(
        db.text(f"SELECT COUNT(*) FROM student_invoices si WHERE {where_sql}"),
        params,
    ).scalar()
    total = int(count_row or 0)
    total_pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    rows = (
        db.session.execute(
            db.text(
                f"""
            SELECT si.*, s.name AS student_name, s.student_code
            FROM student_invoices si
            JOIN students s ON s.id = si.student_id
            WHERE {where_sql}
            ORDER BY si.created_at DESC
            LIMIT :limit OFFSET :offset
            """
            ),
            {**params, "limit": per_page, "offset": offset},
        )
        .mappings()
        .all()
    )

    invoices = [dict(r) for r in rows]

    # Hitung jumlah line per invoice
    for inv in invoices:
        cnt = db.session.execute(
            db.text(
                "SELECT COUNT(*) FROM student_invoice_lines WHERE invoice_id = :id"
            ),
            {"id": inv["id"]},
        ).scalar()
        inv["line_count"] = int(cnt or 0)

    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()

    today = date.today()
    return render_template(
        "quota/invoice_list.html",
        invoices=invoices,
        students=students,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        filters={
            "student_ref": student_ref,
            "status": status,
            "billing_type": billing_type,
            "month": month,
            "year": year,
        },
        BILLING_TYPE_LABELS=BILLING_TYPE_LABELS,
        current_year=today.year,
    )


@quota_invoice_bp.route("/invoice/<string:invoice_ref>/print", methods=["GET"])
@login_required
def invoice_print(invoice_ref):
    """Render invoice dalam format cetak / download PNG."""
    from flask import current_app

    invoice_id = _decode_invoice_ref_or_404(invoice_ref)
    invoice = _fetch_invoice(invoice_id)
    if not invoice:
        flash("Invoice tidak ditemukan.", "danger")
        return redirect(url_for("quota_invoice.quota_alerts"))

    student = Student.query.get(invoice["student_id"])
    invoice_lines = _fetch_invoice_lines(invoice_id)
    if not invoice_lines:
        invoice_lines = _build_legacy_invoice_lines(invoice)

    total_amount = sum(float(line["nominal_amount"] or 0) for line in invoice_lines)
    total_meetings = sum(int(line["meeting_count"] or 0) for line in invoice_lines)

    # Program = daftar nama mapel unik
    seen_subj, subjects = set(), []
    for line in invoice_lines:
        n = line.get("subject_name") or ""
        if n and n not in seen_subj:
            seen_subj.add(n)
            subjects.append(n)
    program = " & ".join(subjects) if subjects else "—"

    # Kelas = grade + level dari line pertama
    grade_level = "—"
    for line in invoice_lines:
        g = line.get("grade") or ""
        lv = line.get("level_name") or ""
        grade_level = (g + " " + lv).strip() or "—"
        break

    bank_str = current_app.config.get("INSTITUTION_BANK_ACCOUNTS", "")
    bank_accounts = [b.strip() for b in bank_str.split("|") if b.strip()]
    reg_fee = current_app.config.get("DEFAULT_REGISTRATION_FEE", 0)

    created_at = invoice.get("created_at") or datetime.utcnow()
    invoice_verify_url = url_for(
        "quota_invoice.invoice_verify",
        invoice_ref=invoice_ref,
        _external=True,
    )

    return render_template(
        "quota/invoice_print.html",
        invoice=invoice,
        student=student,
        invoice_lines=invoice_lines,
        total_amount=total_amount,
        total_meetings=total_meetings,
        program=program,
        grade_level=grade_level,
        reg_fee=reg_fee,
        billing_type_label=BILLING_TYPE_LABELS.get(
            invoice.get("billing_type") or "prepaid", "Pra Bayar"
        ),
        service_month_label=_month_label(invoice["service_month"]),
        bank_accounts=bank_accounts,
        MONTHS_ID=MONTHS_ID,
        institution_name=current_app.config.get("INSTITUTION_NAME", "LBB Super Smart"),
        institution_phone=current_app.config.get("INSTITUTION_PHONE", ""),
        institution_city=current_app.config.get("INSTITUTION_CITY", "Surabaya"),
        ceo_name=current_app.config.get("INSTITUTION_CEO_NAME", ""),
        ceo_title=current_app.config.get("INSTITUTION_CEO_TITLE", "CEO"),
        created_at=created_at,
        invoice_verify_url=invoice_verify_url,
        branding_logo_mark_data_uri=get_branding_logo_mark_data_uri(),
        signature_qr_data_uri=build_qr_code_data_uri(invoice_verify_url, box_size=4),
    )
