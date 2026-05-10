"""Tutor-facing portal routes."""

import json
import os
import re
import smtplib
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from email.message import EmailMessage
from functools import wraps
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    EnrollmentSchedule,
    Tutor,
    TutorPayout,
    TutorPortalRequest,
    WhatsAppEvaluation,
)
from app.routes.master import _build_tutor_weekly_schedule_grid
from app.utils import decode_public_id


tutor_portal_bp = Blueprint("tutor_portal", __name__, url_prefix="/tutor")

PORTAL_MIN_DATE = date(2026, 4, 1)
ATTENDANCE_TABLE_PER_PAGE = 10
WEEKDAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES = [
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
SCHEDULE_HOUR_SLOTS = list(range(8, 22))
REQUEST_TYPES = {
    "schedule_change": "Perubahan Jadwal Siswa",
    "availability": "Jadwal Merah/Hijau",
    "profile_update": "Perbaikan Data Diri",
}


def _token_serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="lbb-tutor-portal-login"
    )


def _normalize_email(value):
    return (value or "").strip().lower()


def _current_user_can_view_tutor_dashboard():
    return bool(
        current_user.is_authenticated
        and getattr(current_user, "role", None) == "admin"
    )


def _selected_admin_tutor_id():
    if not _current_user_can_view_tutor_dashboard():
        return None

    tutor_ref = request.args.get("tutor_ref")
    if tutor_ref:
        try:
            tutor_id = decode_public_id(tutor_ref, "tutor")
        except ValueError:
            abort(404)
        session["tutor_portal_admin_tutor_id"] = tutor_id
        return tutor_id
    return session.get("tutor_portal_admin_tutor_id")


def _is_admin_tutor_dashboard_view():
    return bool(_current_user_can_view_tutor_dashboard() and _selected_admin_tutor_id())


def _current_tutor():
    tutor_id = _selected_admin_tutor_id() or session.get("tutor_portal_tutor_id")
    if not tutor_id:
        return None
    return Tutor.query.get(tutor_id)


def _portal_username_base(tutor):
    raw = tutor.tutor_code or tutor.name or f"tutor{tutor.id}"
    username = re.sub(r"[^a-z0-9]+", "", raw.lower())
    return username or f"tutor{tutor.id}"


def _initial_portal_password(tutor):
    code = re.sub(r"[^A-Za-z0-9]+", "", tutor.tutor_code or str(tutor.id)).upper()
    return f"SS-{code}-2026"


def _ensure_tutor_portal_credentials(tutor):
    changed = False
    if not tutor.portal_username:
        base = _portal_username_base(tutor)
        username = base
        suffix = 2
        while Tutor.query.filter(
            Tutor.portal_username == username,
            Tutor.id != tutor.id,
        ).first():
            username = f"{base}{suffix}"
            suffix += 1
        tutor.portal_username = username
        changed = True
    if not tutor.portal_password_hash:
        tutor.set_portal_password(_initial_portal_password(tutor))
        tutor.portal_must_change_password = True
        changed = True
    if tutor.portal_must_change_password is None:
        tutor.portal_must_change_password = True
        changed = True
    if tutor.portal_email_verified is None:
        tutor.portal_email_verified = False
        changed = True
    return changed


def _ensure_all_tutor_portal_credentials():
    rows = Tutor.query.order_by(Tutor.name.asc(), Tutor.id.asc()).all()
    changed = False
    for tutor in rows:
        changed = _ensure_tutor_portal_credentials(tutor) or changed
    if changed:
        db.session.commit()
    return rows


def _tutor_needs_onboarding(tutor):
    return bool(tutor.portal_must_change_password or not tutor.portal_email_verified)


def tutor_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        tutor = _current_tutor()
        if not tutor:
            if _current_user_can_view_tutor_dashboard():
                return redirect(url_for("tutor_portal.admin_dashboard_select"))
            flash("Silakan masuk dengan Gmail tutor terlebih dahulu.", "warning")
            return redirect(url_for("tutor_portal.login"))
        if _is_admin_tutor_dashboard_view() and request.endpoint not in {
            "tutor_portal.dashboard",
            "tutor_portal.uploaded_file",
        }:
            flash("Mode admin hanya untuk melihat dashboard tutor.", "warning")
            return redirect(url_for("tutor_portal.dashboard"))
        if (
            not _is_admin_tutor_dashboard_view()
            and _tutor_needs_onboarding(tutor)
            and request.endpoint != "tutor_portal.onboarding"
        ):
            flash("Lengkapi password baru dan verifikasi Gmail terlebih dahulu.", "warning")
            return redirect(url_for("tutor_portal.onboarding"))
        return view(*args, **kwargs)

    return wrapped


def _parse_portal_min_date():
    configured = current_app.config.get("TUTOR_PORTAL_MIN_DATE", "2026-04-01")
    try:
        return datetime.strptime(configured, "%Y-%m-%d").date()
    except ValueError:
        return PORTAL_MIN_DATE


def _send_login_email(tutor, verify_url):
    username = current_app.config.get("MAIL_USERNAME")
    sender = (
        current_app.config.get("MAIL_DEFAULT_SENDER")
        or username
        or current_app.config.get("INSTITUTION_EMAIL")
    )
    server = current_app.config.get("MAIL_SERVER")
    if not server:
        current_app.logger.warning("MAIL_SERVER is empty; tutor login link: %s", verify_url)
        return False
    if not sender:
        current_app.logger.warning("MAIL_DEFAULT_SENDER is empty; tutor login link: %s", verify_url)
        return False

    message = EmailMessage()
    message["Subject"] = "Link masuk Dashboard Tutor Super Smart"
    message["From"] = sender
    message["To"] = tutor.email
    message.set_content(
        "\n".join(
            [
                f"Halo {tutor.name},",
                "",
                "Klik link berikut untuk masuk ke Dashboard Tutor Super Smart:",
                verify_url,
                "",
                "Link berlaku 30 menit. Abaikan email ini jika bukan Anda yang meminta.",
            ]
        )
    )

    port = int(current_app.config.get("MAIL_PORT", 587))
    password = current_app.config.get("MAIL_PASSWORD")
    use_ssl = current_app.config.get("MAIL_USE_SSL")
    use_tls = current_app.config.get("MAIL_USE_TLS")

    if username and not password:
        current_app.logger.warning(
            "MAIL_USERNAME is set but MAIL_PASSWORD is empty; tutor login link: %s",
            verify_url,
        )
        return False

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(server, port, timeout=20) as smtp:
        if use_tls and not use_ssl:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
    return True


def _send_verification_email(tutor):
    token = _token_serializer().dumps(
        {"tutor_id": tutor.id, "email": _normalize_email(tutor.email), "purpose": "verify_email"}
    )
    verify_url = _build_email_verification_url(token)
    return _send_login_email(tutor, verify_url)


def _build_login_url(token):
    base_url = current_app.config.get("TUTOR_PORTAL_BASE_URL", "").rstrip("/")
    path = url_for("tutor_portal.verify", token=token)
    return f"{base_url}{path}" if base_url else url_for(
        "tutor_portal.verify", token=token, _external=True
    )


def _build_email_verification_url(token):
    base_url = current_app.config.get("TUTOR_PORTAL_BASE_URL", "").rstrip("/")
    path = url_for("tutor_portal.verify_email", token=token)
    return f"{base_url}{path}" if base_url else url_for(
        "tutor_portal.verify_email", token=token, _external=True
    )


def _build_tutor_login_url():
    base_url = current_app.config.get("TUTOR_PORTAL_BASE_URL", "").rstrip("/")
    if not base_url or "localhost" in base_url:
        base_url = "https://tutor.supersmart.click"
    path = url_for("tutor_portal.login")
    return f"{base_url}{path}"


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
    session_data = payload.get("session") if isinstance(payload, dict) else {}
    return {
        "ok": status_code == 200 and bool(payload.get("ok")),
        "ready": bool(session_data.get("ready")) or session_data.get("status") == "ready",
        "status": session_data.get("status") or "offline",
        "error": payload.get("error"),
    }


def _normalize_whatsapp_phone(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("0"):
        return f"62{digits[1:]}"
    if digits.startswith("8"):
        return f"62{digits}"
    return digits


def _build_tutor_credential_whatsapp_template():
    return (
        "Halo {tutor_name},\n\n"
        "Ini akses Dashboard Tutor LBB Super Smart.\n\n"
        "Link dashboard: {dashboard_url}\n"
        "Username: {username}\n"
        "Password awal: {password}\n\n"
        "Cara login pertama:\n"
        "1. Buka link dashboard tutor.\n"
        "2. Login memakai username dan password awal.\n"
        "3. Ganti password baru.\n"
        "4. Masukkan Gmail aktif.\n"
        "5. Klik link verifikasi yang dikirim ke Gmail.\n\n"
        "Fungsi dashboard tutor:\n"
        "- Melihat jadwal siswa.\n"
        "- Mengajukan perubahan jadwal ke admin.\n"
        "- Melihat kalender presensi bulanan.\n"
        "- Melihat presensi dan status validasi admin.\n"
        "- Melihat akumulasi fee dari presensi tervalidasi.\n"
        "- Mengajukan perbaikan data diri, CV, dan foto profil.\n\n"
        "Mohon segera aktivasi akun agar dashboard bisa digunakan."
    )


def _render_tutor_credential_whatsapp_message(tutor, initial_password, template):
    password_line = initial_password or "Password sudah diganti tutor, tidak ditampilkan ulang."
    values = {
        "tutor_name": tutor.name or "",
        "dashboard_url": _build_tutor_login_url(),
        "username": tutor.portal_username or "",
        "password": password_line,
        "tutor_code": tutor.tutor_code or "",
    }
    message = template or _build_tutor_credential_whatsapp_template()
    for key, value in values.items():
        message = message.replace(f"{{{key}}}", str(value))
    return message


def _attendance_validation_map(session_ids):
    if not session_ids:
        return {}
    rows = (
        WhatsAppEvaluation.query.filter(
            WhatsAppEvaluation.attendance_session_id.in_(session_ids)
        )
        .order_by(WhatsAppEvaluation.updated_at.desc(), WhatsAppEvaluation.id.desc())
        .all()
    )
    result = {}
    for row in rows:
        result.setdefault(row.attendance_session_id, row.manual_review_status or "pending")
    return result


def _normalize_calendar_period(month, year):
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year
    if target_month < 1 or target_month > 12:
        target_month = today.month
    if target_year < 2000 or target_year > 2100:
        target_year = today.year
    return target_month, target_year


def _month_bounds(month, year):
    period_start = date(year, month, 1)
    period_end = date(year, month, monthrange(year, month)[1])
    return period_start, period_end


def _normalize_portal_attendance_period(month, year, min_date):
    target_month, target_year = _normalize_calendar_period(month, year)
    period_start, _period_end = _month_bounds(target_month, target_year)
    min_period_start = date(min_date.year, min_date.month, 1)
    if period_start < min_period_start:
        return min_date.month, min_date.year
    return target_month, target_year


def _build_tutor_attendance_calendar(tutor_id, month=None, year=None, min_date=None):
    if min_date is None:
        min_date = _parse_portal_min_date()
    target_month, target_year = _normalize_portal_attendance_period(
        month,
        year,
        min_date,
    )
    period_start = date(target_year, target_month, 1)
    period_end = date(target_year, target_month, monthrange(target_year, target_month)[1])
    sessions = (
        AttendanceSession.query.filter(
            AttendanceSession.tutor_id == tutor_id,
            AttendanceSession.session_date.between(period_start, period_end),
        )
        .order_by(AttendanceSession.session_date.asc(), AttendanceSession.id.asc())
        .all()
    )
    validation_map = _attendance_validation_map([session_item.id for session_item in sessions])
    sessions = [
        session_item
        for session_item in sessions
        if validation_map.get(session_item.id) == "valid"
    ]
    items_by_date = defaultdict(list)
    for session_item in sessions:
        student_name = session_item.student.name if session_item.student else "Siswa"
        subject_name = session_item.subject.name if session_item.subject else "Mapel"
        items_by_date[session_item.session_date].append(
            {
                "id": session_item.id,
                "student_name": student_name,
                "student_short_name": " ".join(student_name.split()[:2]),
                "subject_name": subject_name,
                "status": session_item.status,
                "review_status": validation_map.get(session_item.id, "pending"),
                "fee": Decimal(session_item.tutor_fee_amount or 0),
            }
        )

    grid_start = period_start - timedelta(days=period_start.weekday())
    grid_end = period_end + timedelta(days=6 - period_end.weekday())
    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        days = []
        for _ in range(7):
            day_items = items_by_date.get(cursor, [])
            days.append(
                {
                    "date": cursor,
                    "in_month": cursor.month == target_month,
                    "is_today": cursor == date.today(),
                    "items": day_items,
                    "count": len(day_items),
                }
            )
            cursor += timedelta(days=1)
        weeks.append(days)

    previous_month = target_month - 1 if target_month > 1 else 12
    previous_year = target_year if target_month > 1 else target_year - 1
    next_month = target_month + 1 if target_month < 12 else 1
    next_year = target_year if target_month < 12 else target_year + 1
    previous_period_start = date(previous_year, previous_month, 1)
    min_period_start = date(min_date.year, min_date.month, 1)
    valid_fee_total = sum(
        item["fee"]
        for items in items_by_date.values()
        for item in items
        if item["review_status"] == "valid"
    )
    return {
        "month": target_month,
        "year": target_year,
        "title": f"{MONTH_NAMES[target_month]} {target_year}",
        "weekday_names": WEEKDAY_NAMES,
        "month_options": list(enumerate(MONTH_NAMES))[1:],
        "weeks": weeks,
        "session_count": len(sessions),
        "active_day_count": len(items_by_date),
        "valid_fee_total": valid_fee_total,
        "previous_month": previous_month,
        "previous_year": previous_year,
        "can_view_previous": previous_period_start >= min_period_start,
        "next_month": next_month,
        "next_year": next_year,
    }


def _validated_tutor_attendance_sessions(tutor_id, period_start, period_end):
    sessions = (
        AttendanceSession.query.filter(
            AttendanceSession.tutor_id == tutor_id,
            AttendanceSession.session_date.between(period_start, period_end),
        )
        .order_by(AttendanceSession.session_date.desc(), AttendanceSession.id.desc())
        .all()
    )
    validation_map = _attendance_validation_map([session.id for session in sessions])
    valid_sessions = [
        session for session in sessions if validation_map.get(session.id) == "valid"
    ]
    return valid_sessions, validation_map


class _ListPagination:
    def __init__(self, items, page, per_page):
        self.total = len(items)
        self.per_page = per_page
        self.pages = max((self.total + per_page - 1) // per_page, 1)
        self.page = min(max(page, 1), self.pages)
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else 1
        self.next_num = self.page + 1 if self.has_next else self.pages
        start_index = (self.page - 1) * per_page
        end_index = start_index + per_page
        self.items = items[start_index:end_index]
        self.first = start_index + 1 if self.total else 0
        self.last = min(end_index, self.total)

    def iter_pages(
        self,
        left_edge=1,
        right_edge=1,
        left_current=2,
        right_current=2,
    ):
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or num > self.pages - right_edge
                or self.page - left_current <= num <= self.page + right_current
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num


def _allowed_upload(filename, extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def _save_tutor_upload(file_storage, tutor, folder, extensions):
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_upload(file_storage.filename, extensions):
        raise ValueError("Format file tidak didukung.")
    filename = secure_filename(file_storage.filename)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    relative_dir = os.path.join("tutor_portal", folder)
    target_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_dir)
    os.makedirs(target_dir, exist_ok=True)
    relative_path = os.path.join(relative_dir, f"tutor-{tutor.id}-{stamp}-{filename}")
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path))
    return relative_path


def _active_tutor_enrollments(tutor_id):
    return (
        Enrollment.query.filter(
            Enrollment.tutor_id == tutor_id,
            Enrollment.is_active.is_(True),
        )
        .order_by(Enrollment.status.asc(), Enrollment.id.asc())
        .all()
    )


def _build_schedule_change_rows(tutor_id):
    enrollments_by_value = {
        f"enrollment:{enrollment.id}": enrollment
        for enrollment in _active_tutor_enrollments(tutor_id)
    }
    label_by_value = {
        value: f"{enrollment.student.name if enrollment.student else 'Siswa'} - {enrollment.subject.name if enrollment.subject else 'Mapel'}"
        for value, enrollment in enrollments_by_value.items()
    }
    active_schedules = (
        EnrollmentSchedule.query.join(Enrollment)
        .filter(
            Enrollment.tutor_id == tutor_id,
            Enrollment.status == "active",
            Enrollment.is_active.is_(True),
            EnrollmentSchedule.is_active.is_(True),
        )
        .order_by(
            EnrollmentSchedule.day_of_week.asc(),
            EnrollmentSchedule.start_time.asc(),
            EnrollmentSchedule.id.asc(),
        )
        .all()
    )
    selected_by_slot = defaultdict(list)
    for schedule in active_schedules:
        if schedule.start_time is None:
            continue
        hour = schedule.start_time.hour
        weekday = schedule.day_of_week
        if weekday not in range(7) or hour not in SCHEDULE_HOUR_SLOTS:
            continue
        value = f"enrollment:{schedule.enrollment_id}"
        if value not in selected_by_slot[(weekday, hour)]:
            selected_by_slot[(weekday, hour)].append(value)

    schedule_grid = _build_tutor_weekly_schedule_grid(tutor_id)
    for row in schedule_grid.get("rows", []):
        hour = row.get("hour")
        if hour not in SCHEDULE_HOUR_SLOTS:
            continue
        for cell in row.get("cells", []):
            weekday = cell.get("weekday")
            if weekday not in range(7):
                continue
            for item in cell.get("items", []):
                enrollment_ref = item.get("enrollment_ref")
                if not enrollment_ref:
                    continue
                try:
                    enrollment_id = decode_public_id(enrollment_ref, "enrollment")
                except ValueError:
                    continue
                value = f"enrollment:{enrollment_id}"
                label_by_value[value] = (
                    f"{item.get('student_name') or 'Siswa'} - "
                    f"{item.get('subject_name') or 'Mapel'}"
                )
                if value not in selected_by_slot[(weekday, hour)]:
                    selected_by_slot[(weekday, hour)].append(value)

    rows = []
    waiting_values = []
    for hour in SCHEDULE_HOUR_SLOTS:
        cells = []
        for weekday in range(7):
            selections = selected_by_slot.get((weekday, hour))
            if not selections:
                selections = ["unavailable" if hour < 16 else "available"]
            selected = selections[0]
            selected_label = (
                label_by_value.get(selected)
                if selected.startswith("enrollment:")
                else "Available" if selected == "available" else "Tidak Available"
            )
            cell_waiting_values = [
                value for value in selections[1:] if value.startswith("enrollment:")
            ]
            waiting_values.extend(cell_waiting_values)
            cells.append(
                {
                    "weekday": weekday,
                    "day_name": WEEKDAY_NAMES[weekday],
                    "hour": hour,
                    "field_name": f"slot_{weekday}_{hour}",
                    "selected": selected,
                    "selected_label": selected_label,
                    "waiting_values": cell_waiting_values,
                }
            )
        rows.append({"hour": hour, "cells": cells})
    return rows


def _schedule_editor_waitinglist(enrollments, rows):
    enrollment_by_value = {f"enrollment:{enrollment.id}": enrollment for enrollment in enrollments}
    assigned_values = {
        cell["selected"]
        for row in rows
        for cell in row["cells"]
        if str(cell["selected"]).startswith("enrollment:")
    }
    waiting_values = []
    for row in rows:
        for cell in row["cells"]:
            waiting_values.extend(cell.get("waiting_values", []))
    waiting_values.extend(
        value for value in enrollment_by_value if value not in assigned_values
    )

    waitinglist = []
    seen = set()
    for value in waiting_values:
        if value in seen:
            continue
        seen.add(value)
        enrollment = enrollment_by_value.get(value)
        if enrollment is None:
            continue
        waitinglist.append(
            {
                "value": value,
                "label": f"{enrollment.student.name if enrollment.student else 'Siswa'} - {enrollment.subject.name if enrollment.subject else 'Mapel'}",
                "student_name": enrollment.student.name if enrollment.student else "Siswa",
                "subject_name": enrollment.subject.name if enrollment.subject else "Mapel",
            }
        )
    return waitinglist


def _schedule_editor_enrollments(tutor_id, rows):
    option_ids = {
        enrollment.id for enrollment in _active_tutor_enrollments(tutor_id)
    }
    for row in rows:
        for cell in row["cells"]:
            values = [cell["selected"], *cell.get("waiting_values", [])]
            for value in values:
                if not str(value).startswith("enrollment:"):
                    continue
                try:
                    option_ids.add(int(str(value).split(":", 1)[1]))
                except ValueError:
                    continue
    if not option_ids:
        return []
    return (
        Enrollment.query.filter(Enrollment.id.in_(option_ids))
        .order_by(Enrollment.status.asc(), Enrollment.id.asc())
        .all()
    )


def _build_schedule_change_payload(tutor, form):
    enrollments = Enrollment.query.all()
    enrollment_by_id = {enrollment.id: enrollment for enrollment in enrollments}
    slots = []
    assigned_count = 0
    available_count = 0
    unavailable_count = 0

    for weekday in range(7):
        for hour in SCHEDULE_HOUR_SLOTS:
            field_name = f"slot_{weekday}_{hour}"
            raw_values = (
                form.getlist(field_name)
                if hasattr(form, "getlist")
                else [form.get(field_name, "unavailable")]
            )
            values = [
                value
                for value in raw_values
                if value in {"available", "unavailable"} or value.startswith("enrollment:")
            ]
            if not values:
                values = ["unavailable"]
            enrollment_values = []
            seen_enrollments = set()
            for value in values:
                if not value.startswith("enrollment:"):
                    continue
                if value in seen_enrollments:
                    continue
                seen_enrollments.add(value)
                enrollment_values.append(value)
            if enrollment_values:
                values = enrollment_values
            else:
                values = [values[0]]

            for value in values:
                slot = {
                    "weekday": weekday,
                    "day_name": WEEKDAY_NAMES[weekday],
                    "hour": hour,
                    "start_time": f"{hour:02d}:00",
                    "end_time": f"{hour + 1:02d}:00",
                }
                if value == "available":
                    slot["state"] = "available"
                    available_count += 1
                elif value == "unavailable":
                    slot["state"] = "unavailable"
                    unavailable_count += 1
                elif value.startswith("enrollment:"):
                    try:
                        enrollment_id = int(value.split(":", 1)[1])
                    except ValueError:
                        raise ValueError("Pilihan jadwal tidak valid.") from None
                    enrollment = enrollment_by_id.get(enrollment_id)
                    if enrollment is None:
                        raise ValueError("Ada siswa yang tidak sesuai dengan tutor ini.")
                    slot.update(
                        {
                            "state": "enrollment",
                            "enrollment_id": enrollment.id,
                            "student_name": enrollment.student.name if enrollment.student else "",
                            "subject_name": enrollment.subject.name if enrollment.subject else "",
                        }
                    )
                    assigned_count += 1
                else:
                    raise ValueError("Pilihan jadwal tidak valid.")
                slots.append(slot)

    return {
        "mode": "weekly_grid",
        "weekday_names": WEEKDAY_NAMES,
        "hour_slots": SCHEDULE_HOUR_SLOTS,
        "slots": slots,
        "summary": {
            "assigned_count": assigned_count,
            "available_count": available_count,
            "unavailable_count": unavailable_count,
        },
    }


def _apply_weekly_schedule_grid_request(portal_request, payload):
    tutor_id = portal_request.tutor_id
    enrollment_ids = {
        int(slot["enrollment_id"])
        for slot in payload.get("slots", [])
        if slot.get("state") == "enrollment" and slot.get("enrollment_id")
    }
    enrollments_by_id = {
        enrollment.id: enrollment
        for enrollment in Enrollment.query.filter(Enrollment.id.in_(enrollment_ids)).all()
    }
    if enrollment_ids and set(enrollments_by_id) != enrollment_ids:
        raise ValueError("Payload jadwal berisi siswa yang tidak ditemukan.")

    active_schedules = (
        EnrollmentSchedule.query.join(Enrollment)
        .filter(
            Enrollment.tutor_id == tutor_id,
            EnrollmentSchedule.is_active.is_(True),
        )
        .all()
    )
    for schedule in active_schedules:
        schedule.is_active = False
        schedule.updated_at = datetime.utcnow()

    for slot in payload.get("slots", []):
        if slot.get("state") != "enrollment":
            continue
        weekday = int(slot["weekday"])
        hour = int(slot["hour"])
        if weekday not in range(7) or hour not in SCHEDULE_HOUR_SLOTS:
            continue
        enrollment = enrollments_by_id.get(int(slot["enrollment_id"]))
        if enrollment is not None and enrollment.tutor_id != tutor_id:
            enrollment.tutor_id = tutor_id
            enrollment.updated_at = datetime.utcnow()
        schedule = EnrollmentSchedule(
            enrollment_id=int(slot["enrollment_id"]),
            day_of_week=weekday,
            day_name=EnrollmentSchedule.get_day_name(weekday),
            start_time=time(hour, 0),
            end_time=time(hour + 1, 0),
            is_active=True,
        )
        db.session.add(schedule)


@tutor_portal_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        tutor = Tutor.query.filter(db.func.lower(Tutor.portal_username) == username).first()
        if tutor and _ensure_tutor_portal_credentials(tutor):
            db.session.commit()
        if not tutor or not tutor.is_active or not tutor.check_portal_password(password):
            flash("Username atau password tutor tidak cocok.", "danger")
            return redirect(url_for("tutor_portal.login"))

        session["tutor_portal_tutor_id"] = tutor.id
        session.permanent = True
        if _tutor_needs_onboarding(tutor):
            flash("Login pertama wajib ganti password dan verifikasi Gmail.", "warning")
            return redirect(url_for("tutor_portal.onboarding"))
        flash("Berhasil masuk ke Dashboard Tutor.", "success")
        return redirect(url_for("tutor_portal.dashboard"))

    return render_template("tutor_portal/login.html")


@tutor_portal_bp.route("/verify/<token>")
def verify(token):
    try:
        payload = _token_serializer().loads(token, max_age=1800)
    except SignatureExpired:
        flash("Link login sudah kedaluwarsa. Silakan minta link baru.", "warning")
        return redirect(url_for("tutor_portal.login"))
    except BadSignature:
        flash("Link login tidak valid.", "danger")
        return redirect(url_for("tutor_portal.login"))

    tutor = Tutor.query.get(payload.get("tutor_id"))
    if not tutor or _normalize_email(tutor.email) != payload.get("email"):
        flash("Data tutor tidak cocok dengan link verifikasi.", "danger")
        return redirect(url_for("tutor_portal.login"))

    session["tutor_portal_tutor_id"] = tutor.id
    session.permanent = True
    flash("Berhasil masuk ke Dashboard Tutor.", "success")
    return redirect(url_for("tutor_portal.dashboard"))


@tutor_portal_bp.route("/verify-email/<token>")
def verify_email(token):
    try:
        payload = _token_serializer().loads(token, max_age=86400)
    except SignatureExpired:
        flash("Link verifikasi Gmail sudah kedaluwarsa. Silakan kirim ulang.", "warning")
        return redirect(url_for("tutor_portal.onboarding"))
    except BadSignature:
        flash("Link verifikasi Gmail tidak valid.", "danger")
        return redirect(url_for("tutor_portal.login"))

    tutor = Tutor.query.get(payload.get("tutor_id"))
    if (
        not tutor
        or payload.get("purpose") != "verify_email"
        or _normalize_email(tutor.email) != payload.get("email")
    ):
        flash("Data verifikasi Gmail tidak cocok.", "danger")
        return redirect(url_for("tutor_portal.login"))

    session["tutor_portal_tutor_id"] = tutor.id
    tutor.portal_email_verified = True
    tutor.portal_email_verified_at = datetime.utcnow()
    db.session.commit()
    flash("Gmail tutor berhasil diverifikasi.", "success")
    return redirect(url_for("tutor_portal.dashboard"))


@tutor_portal_bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    tutor = _current_tutor()
    if not tutor:
        flash("Silakan login dengan username tutor terlebih dahulu.", "warning")
        return redirect(url_for("tutor_portal.login"))

    if not _tutor_needs_onboarding(tutor):
        return redirect(url_for("tutor_portal.dashboard"))

    if request.method == "POST":
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        email = _normalize_email(request.form.get("email"))
        if len(new_password) < 8:
            flash("Password baru minimal 8 karakter.", "danger")
            return redirect(url_for("tutor_portal.onboarding"))
        if new_password != confirm_password:
            flash("Konfirmasi password tidak cocok.", "danger")
            return redirect(url_for("tutor_portal.onboarding"))
        if not email.endswith("@gmail.com"):
            flash("Email tutor wajib menggunakan Gmail.", "danger")
            return redirect(url_for("tutor_portal.onboarding"))

        existing = Tutor.query.filter(
            db.func.lower(Tutor.email) == email,
            Tutor.id != tutor.id,
        ).first()
        if existing:
            flash("Gmail sudah dipakai tutor lain.", "danger")
            return redirect(url_for("tutor_portal.onboarding"))

        tutor.set_portal_password(new_password)
        tutor.portal_must_change_password = False
        tutor.email = email
        tutor.portal_email_verified = False
        tutor.portal_email_verified_at = None
        tutor.updated_at = datetime.utcnow()
        db.session.commit()

        try:
            sent = _send_verification_email(tutor)
        except Exception as exc:
            current_app.logger.warning("Failed to send tutor verification email: %s", exc)
            sent = False
        if sent:
            flash("Password baru dan Gmail sudah disimpan. Link verifikasi Gmail sudah dikirim.", "success")
        elif current_app.config.get("MAIL_SERVER"):
            flash(
                "Password baru dan Gmail sudah disimpan, tetapi email verifikasi belum terkirim. Admin perlu cek koneksi SMTP.",
                "warning",
            )
        else:
            flash("Password baru dan Gmail sudah disimpan. MAIL_SERVER belum aktif, link verifikasi dicatat di log server.", "warning")
        return redirect(url_for("tutor_portal.onboarding"))

    return render_template("tutor_portal/onboarding.html", tutor=tutor)


@tutor_portal_bp.route("/logout")
def logout():
    session.pop("tutor_portal_tutor_id", None)
    session.pop("tutor_portal_admin_tutor_id", None)
    flash("Anda sudah keluar dari Dashboard Tutor.", "info")
    return redirect(url_for("tutor_portal.login"))


@tutor_portal_bp.route("/admin/dashboard-select", methods=["GET", "POST"])
@login_required
def admin_dashboard_select():
    if not _current_user_can_view_tutor_dashboard():
        abort(403)
    if request.method == "POST":
        tutor_ref = request.form.get("tutor_ref") or ""
        try:
            tutor_id = decode_public_id(tutor_ref, "tutor")
        except ValueError:
            abort(404)
        tutor = Tutor.query.get_or_404(tutor_id)
        if not tutor.is_active:
            flash("Tutor yang dipilih tidak aktif.", "warning")
            return redirect(url_for("tutor_portal.admin_dashboard_select"))
        session["tutor_portal_admin_tutor_id"] = tutor.id
        flash(f"Dashboard tutor {tutor.name} ditampilkan.", "success")
        return redirect(url_for("tutor_portal.dashboard"))

    tutors = Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc(), Tutor.id.asc()).all()
    return render_template("tutor_portal/admin_dashboard_select.html", tutors=tutors)


@tutor_portal_bp.route("/uploads/<path:filename>")
@tutor_login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@tutor_portal_bp.route("/")
@tutor_login_required
def dashboard():
    tutor = _current_tutor()
    admin_tutor_dashboard = _is_admin_tutor_dashboard_view()
    admin_tutor_options = (
        Tutor.query.filter_by(is_active=True).order_by(Tutor.name.asc(), Tutor.id.asc()).all()
        if admin_tutor_dashboard
        else []
    )
    min_date = _parse_portal_min_date()
    calendar_month = request.args.get("month", type=int)
    calendar_year = request.args.get("year", type=int)
    attendance_page = request.args.get("page", 1, type=int)
    attendance_month, attendance_year = _normalize_portal_attendance_period(
        calendar_month,
        calendar_year,
        min_date,
    )
    attendance_period_start, attendance_period_end = _month_bounds(
        attendance_month,
        attendance_year,
    )
    enrollments = (
        Enrollment.query.filter_by(tutor_id=tutor.id)
        .order_by(Enrollment.status.asc(), Enrollment.updated_at.desc())
        .all()
    )
    schedules = (
        EnrollmentSchedule.query.join(Enrollment)
        .filter(Enrollment.tutor_id == tutor.id, EnrollmentSchedule.is_active.is_(True))
        .order_by(EnrollmentSchedule.day_of_week.asc(), EnrollmentSchedule.start_time.asc())
        .all()
    )
    schedule_grid = _build_tutor_weekly_schedule_grid(tutor.id)
    attendance_sessions, validation_map = _validated_tutor_attendance_sessions(
        tutor.id,
        attendance_period_start,
        attendance_period_end,
    )
    attendance_pagination = _ListPagination(
        attendance_sessions,
        attendance_page,
        ATTENDANCE_TABLE_PER_PAGE,
    )
    attendance_sessions = attendance_pagination.items
    attendance_calendar = _build_tutor_attendance_calendar(
        tutor.id,
        month=attendance_month,
        year=attendance_year,
        min_date=min_date,
    )
    validated_fee_total = sum(
        Decimal(s.tutor_fee_amount or 0)
        for s in attendance_sessions
    )
    payouts = (
        TutorPayout.query.filter(
            TutorPayout.tutor_id == tutor.id,
            TutorPayout.payout_date >= datetime.combine(min_date, time.min),
        )
        .order_by(TutorPayout.payout_date.desc(), TutorPayout.id.desc())
        .limit(12)
        .all()
    )
    requests = (
        TutorPortalRequest.query.filter_by(tutor_id=tutor.id)
        .order_by(TutorPortalRequest.requested_at.desc(), TutorPortalRequest.id.desc())
        .limit(12)
        .all()
    )
    return render_template(
        "tutor_portal/dashboard.html",
        tutor=tutor,
        admin_tutor_dashboard=admin_tutor_dashboard,
        admin_tutor_options=admin_tutor_options,
        enrollments=enrollments,
        schedules=schedules,
        schedule_grid=schedule_grid,
        attendance_sessions=attendance_sessions,
        attendance_pagination=attendance_pagination,
        validation_map=validation_map,
        attendance_calendar=attendance_calendar,
        validated_fee_total=validated_fee_total,
        payouts=payouts,
        requests=requests,
        request_type_labels=REQUEST_TYPES,
        min_date=min_date,
        attendance_period_start=attendance_period_start,
        attendance_period_end=attendance_period_end,
    )


@tutor_portal_bp.route("/schedule-change", methods=["GET", "POST"])
@tutor_login_required
def request_schedule_change():
    tutor = _current_tutor()
    enrollments = _active_tutor_enrollments(tutor.id)
    if request.method == "GET":
        rows = _build_schedule_change_rows(tutor.id)
        enrollments = _schedule_editor_enrollments(tutor.id, rows)
        return render_template(
            "tutor_portal/schedule_change.html",
            tutor=tutor,
            enrollments=enrollments,
            rows=rows,
            waitinglist=_schedule_editor_waitinglist(enrollments, rows),
            weekday_names=WEEKDAY_NAMES,
        )

    try:
        payload = _build_schedule_change_payload(tutor, request.form)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("tutor_portal.request_schedule_change"))

    db.session.add(
        TutorPortalRequest(
            tutor_id=tutor.id,
            request_type="schedule_change",
            payload_json=payload,
            notes=request.form.get("notes"),
        )
    )
    db.session.commit()
    flash("Pengajuan perubahan jadwal dikirim dan menunggu persetujuan admin.", "success")
    return redirect(url_for("tutor_portal.dashboard"))


@tutor_portal_bp.route("/availability", methods=["POST"])
@tutor_login_required
def request_availability():
    tutor = _current_tutor()
    color = request.form.get("color")
    if color not in {"red", "green"}:
        flash("Pilih status jadwal merah atau hijau.", "danger")
        return redirect(url_for("tutor_portal.dashboard"))
    db.session.add(
        TutorPortalRequest(
            tutor_id=tutor.id,
            request_type="availability",
            payload_json={
                "color": color,
                "date": request.form.get("date"),
                "start_time": request.form.get("start_time"),
                "end_time": request.form.get("end_time"),
            },
            notes=request.form.get("notes"),
        )
    )
    db.session.commit()
    flash("Pengajuan jadwal merah/hijau dikirim dan menunggu persetujuan admin.", "success")
    return redirect(url_for("tutor_portal.dashboard"))


@tutor_portal_bp.route("/profile-request", methods=["POST"])
@tutor_login_required
def request_profile_update():
    tutor = _current_tutor()
    try:
        profile_photo = _save_tutor_upload(
            request.files.get("profile_photo"),
            tutor,
            "profile_photos",
            {"png", "jpg", "jpeg", "webp"},
        )
        cv_file = _save_tutor_upload(
            request.files.get("cv_file"),
            tutor,
            "cv",
            {"pdf", "doc", "docx"},
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("tutor_portal.dashboard"))

    payload = {
        "phone": request.form.get("phone"),
        "address": request.form.get("address"),
        "bank_name": request.form.get("bank_name"),
        "bank_account_number": request.form.get("bank_account_number"),
        "account_holder_name": request.form.get("account_holder_name"),
        "profile_photo_path": profile_photo,
        "cv_file_path": cv_file,
    }
    db.session.add(
        TutorPortalRequest(
            tutor_id=tutor.id,
            request_type="profile_update",
            payload_json={k: v for k, v in payload.items() if v},
            notes=request.form.get("notes"),
        )
    )
    db.session.commit()
    flash("Pengajuan perbaikan data diri dikirim dan menunggu persetujuan admin.", "success")
    return redirect(url_for("tutor_portal.dashboard"))


@tutor_portal_bp.route("/admin/requests")
@login_required
def admin_requests():
    status = request.args.get("status", "pending")
    query = TutorPortalRequest.query
    if status != "all":
        query = query.filter_by(status=status)
    requests = query.order_by(
        TutorPortalRequest.requested_at.desc(), TutorPortalRequest.id.desc()
    ).all()
    return render_template(
        "tutor_portal/admin_requests.html",
        requests=requests,
        status=status,
        request_type_labels=REQUEST_TYPES,
    )


@tutor_portal_bp.route("/admin/credentials")
@login_required
def admin_credentials():
    tutors = _ensure_all_tutor_portal_credentials()
    credential_rows = [
        {
            "tutor": tutor,
            "username": tutor.portal_username,
            "whatsapp_phone": _normalize_whatsapp_phone(tutor.phone),
            "initial_password": (
                _initial_portal_password(tutor)
                if tutor.portal_must_change_password
                else None
            ),
            "must_change_password": tutor.portal_must_change_password,
            "email_verified": tutor.portal_email_verified,
        }
        for tutor in tutors
    ]
    return render_template(
        "tutor_portal/admin_credentials.html",
        credential_rows=credential_rows,
        whatsapp_message_template=_build_tutor_credential_whatsapp_template(),
    )


@tutor_portal_bp.route(
    "/admin/credentials/<string:tutor_ref>/send-whatsapp", methods=["POST"]
)
@login_required
def admin_send_credential_whatsapp(tutor_ref):
    try:
        tutor_id = decode_public_id(tutor_ref, "tutor")
    except ValueError:
        abort(404)
    tutor = Tutor.query.get_or_404(tutor_id)
    if _ensure_tutor_portal_credentials(tutor):
        db.session.commit()

    contact_id = _normalize_whatsapp_phone(tutor.phone)
    if not contact_id:
        flash(f"Nomor WhatsApp {tutor.name} belum tersedia di data tutor.", "warning")
        return redirect(url_for("tutor_portal.admin_credentials"))

    session_status = _get_whatsapp_session_status()
    if not session_status["ready"]:
        flash("WhatsApp bot belum ready. Silakan login/scan QR terlebih dahulu.", "warning")
        return redirect(url_for("whatsapp_bot.management"))

    initial_password = (
        _initial_portal_password(tutor) if tutor.portal_must_change_password else None
    )
    message_template = (
        request.form.get("message_template") or _build_tutor_credential_whatsapp_template()
    )
    message = _render_tutor_credential_whatsapp_message(
        tutor, initial_password, message_template
    ).strip()
    if not message:
        flash("Isi pesan WhatsApp tidak boleh kosong.", "warning")
        return redirect(url_for("tutor_portal.admin_credentials"))
    payload, status_code = _bot_request(
        "POST",
        "/messages/send",
        {"to": contact_id, "message": message},
        timeout=30,
    )
    if status_code == 200 and payload.get("ok"):
        flash(f"Link dashboard dan credential berhasil dikirim ke WhatsApp {tutor.name}.", "success")
    else:
        flash(f"Kirim WhatsApp gagal: {payload.get('error') or 'Bot error'}", "danger")
    return redirect(url_for("tutor_portal.admin_credentials"))


@tutor_portal_bp.route("/admin/requests/<string:request_ref>/<action>", methods=["POST"])
@login_required
def review_request(request_ref, action):
    if action not in {"approve", "reject"}:
        abort(404)
    try:
        request_id = decode_public_id(request_ref, "tutor_portal_request")
    except ValueError:
        abort(404)
    portal_request = TutorPortalRequest.query.get_or_404(request_id)
    if portal_request.status != "pending":
        flash("Pengajuan ini sudah diproses.", "warning")
        return redirect(url_for("tutor_portal.admin_requests"))

    portal_request.status = "approved" if action == "approve" else "rejected"
    portal_request.reviewed_at = datetime.utcnow()
    portal_request.reviewed_by = current_user.id
    portal_request.admin_notes = request.form.get("admin_notes")
    if action == "approve":
        try:
            _apply_approved_request(portal_request)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("tutor_portal.admin_requests"))
    db.session.commit()
    flash("Pengajuan tutor berhasil diproses.", "success")
    return redirect(url_for("tutor_portal.admin_requests"))


def _apply_approved_request(portal_request):
    payload = portal_request.payload_json or {}
    if portal_request.request_type == "schedule_change":
        if payload.get("mode") == "weekly_grid":
            _apply_weekly_schedule_grid_request(portal_request, payload)
            return
        schedule = EnrollmentSchedule.query.get(payload.get("schedule_id"))
        if schedule:
            day_map = {EnrollmentSchedule.get_day_name(i): i for i in range(7)}
            if payload.get("requested_day") in day_map:
                schedule.day_of_week = day_map[payload["requested_day"]]
                schedule.day_name = payload["requested_day"]
            if payload.get("requested_start_time"):
                schedule.start_time = datetime.strptime(
                    payload["requested_start_time"], "%H:%M"
                ).time()
            if payload.get("requested_end_time"):
                schedule.end_time = datetime.strptime(
                    payload["requested_end_time"], "%H:%M"
                ).time()
            schedule.updated_at = datetime.utcnow()
    elif portal_request.request_type == "profile_update":
        tutor = portal_request.tutor
        for field in (
            "phone",
            "address",
            "bank_name",
            "bank_account_number",
            "account_holder_name",
            "profile_photo_path",
            "cv_file_path",
        ):
            if payload.get(field):
                setattr(tutor, field, payload[field])
        tutor.updated_at = datetime.utcnow()
