"""Tutor-facing portal routes."""

import json
import os
import re
import smtplib
from datetime import date, datetime, time
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
from app.utils import decode_public_id


tutor_portal_bp = Blueprint("tutor_portal", __name__, url_prefix="/tutor")

PORTAL_MIN_DATE = date(2026, 4, 1)
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


def _current_tutor():
    tutor_id = session.get("tutor_portal_tutor_id")
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


def _tutor_onboarding_step(tutor):
    if tutor.portal_must_change_password:
        return "password"
    if not tutor.portal_email_verified:
        return "email"
    return "complete"


def tutor_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        tutor = _current_tutor()
        if not tutor:
            flash("Silakan masuk dengan Gmail tutor terlebih dahulu.", "warning")
            return redirect(url_for("tutor_portal.login"))
        if _tutor_needs_onboarding(tutor) and request.endpoint != "tutor_portal.onboarding":
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
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    server = current_app.config.get("MAIL_SERVER")
    if not server:
        current_app.logger.warning("MAIL_SERVER is empty; tutor login link: %s", verify_url)
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
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    use_ssl = current_app.config.get("MAIL_USE_SSL")
    use_tls = current_app.config.get("MAIL_USE_TLS")

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(server, port, timeout=20) as smtp:
        if use_tls and not use_ssl:
            smtp.starttls()
        if username:
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
        "- Mengajukan jadwal merah/hijau ke admin.\n"
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


@tutor_portal_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_method = request.form.get("login_method", "username")
        if login_method == "email":
            email = _normalize_email(request.form.get("email"))
            if not email.endswith("@gmail.com"):
                flash("Gunakan alamat Gmail tutor yang terverifikasi.", "danger")
                return redirect(url_for("tutor_portal.login"))

            tutor = Tutor.query.filter(db.func.lower(Tutor.email) == email).first()
            if not tutor or not tutor.is_active or not tutor.portal_email_verified:
                flash("Gmail belum cocok atau belum terverifikasi.", "danger")
                return redirect(url_for("tutor_portal.login"))

            token = _token_serializer().dumps({"tutor_id": tutor.id, "email": email})
            verify_url = _build_login_url(token)
            try:
                sent = _send_login_email(tutor, verify_url)
            except Exception as exc:
                current_app.logger.warning("Failed to send tutor login email: %s", exc)
                sent = False
            if sent:
                flash("Link login sudah dikirim ke Gmail tutor.", "success")
            else:
                flash("MAIL_SERVER belum aktif. Link login dicatat di log server.", "warning")
            return render_template("tutor_portal/login_sent.html", tutor=tutor)

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

    step = _tutor_onboarding_step(tutor)
    if step == "complete":
        return redirect(url_for("tutor_portal.dashboard"))

    if request.method == "POST":
        if step == "password":
            new_password = request.form.get("new_password") or ""
            confirm_password = request.form.get("confirm_password") or ""
            if len(new_password) < 8:
                flash("Password baru minimal 8 karakter.", "danger")
                return redirect(url_for("tutor_portal.onboarding"))
            if new_password != confirm_password:
                flash("Konfirmasi password tidak cocok.", "danger")
                return redirect(url_for("tutor_portal.onboarding"))

            tutor.set_portal_password(new_password)
            tutor.portal_must_change_password = False
            tutor.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Password berhasil diganti. Lanjutkan dengan memasukkan Gmail tutor.", "success")
            return redirect(url_for("tutor_portal.onboarding"))

        email = _normalize_email(request.form.get("email"))
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
            flash("Gmail tutor sudah disimpan. Link verifikasi Gmail sudah dikirim.", "success")
        else:
            flash("Gmail tutor sudah disimpan. MAIL_SERVER belum aktif, link verifikasi dicatat di log server.", "warning")
        return redirect(url_for("tutor_portal.onboarding"))

    return render_template("tutor_portal/onboarding.html", tutor=tutor, step=step)


@tutor_portal_bp.route("/logout")
def logout():
    session.pop("tutor_portal_tutor_id", None)
    flash("Anda sudah keluar dari Dashboard Tutor.", "info")
    return redirect(url_for("tutor_portal.login"))


@tutor_portal_bp.route("/uploads/<path:filename>")
@tutor_login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@tutor_portal_bp.route("/")
@tutor_login_required
def dashboard():
    tutor = _current_tutor()
    min_date = _parse_portal_min_date()
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
    attendance_sessions = (
        AttendanceSession.query.filter(
            AttendanceSession.tutor_id == tutor.id,
            AttendanceSession.session_date >= min_date,
        )
        .order_by(AttendanceSession.session_date.desc(), AttendanceSession.id.desc())
        .limit(80)
        .all()
    )
    validation_map = _attendance_validation_map([s.id for s in attendance_sessions])
    validated_fee_total = sum(
        Decimal(s.tutor_fee_amount or 0)
        for s in attendance_sessions
        if validation_map.get(s.id) == "valid"
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
        enrollments=enrollments,
        schedules=schedules,
        attendance_sessions=attendance_sessions,
        validation_map=validation_map,
        validated_fee_total=validated_fee_total,
        payouts=payouts,
        requests=requests,
        request_type_labels=REQUEST_TYPES,
        min_date=min_date,
    )


@tutor_portal_bp.route("/schedule-change", methods=["POST"])
@tutor_login_required
def request_schedule_change():
    tutor = _current_tutor()
    schedule_id = request.form.get("schedule_id", type=int)
    schedule = (
        EnrollmentSchedule.query.join(Enrollment)
        .filter(EnrollmentSchedule.id == schedule_id, Enrollment.tutor_id == tutor.id)
        .first()
    )
    if not schedule:
        abort(404)
    payload = {
        "schedule_id": schedule.id,
        "student_name": schedule.enrollment.student.name if schedule.enrollment.student else "",
        "subject_name": schedule.enrollment.subject.name if schedule.enrollment.subject else "",
        "current_day": schedule.day_name,
        "current_start_time": schedule.start_time.strftime("%H:%M") if schedule.start_time else "",
        "current_end_time": schedule.end_time.strftime("%H:%M") if schedule.end_time else "",
        "requested_day": request.form.get("requested_day"),
        "requested_start_time": request.form.get("requested_start_time"),
        "requested_end_time": request.form.get("requested_end_time"),
    }
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
        _apply_approved_request(portal_request)
    db.session.commit()
    flash("Pengajuan tutor berhasil diproses.", "success")
    return redirect(url_for("tutor_portal.admin_requests"))


def _apply_approved_request(portal_request):
    payload = portal_request.payload_json or {}
    if portal_request.request_type == "schedule_change":
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
