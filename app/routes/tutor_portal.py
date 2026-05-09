"""Tutor-facing portal routes."""

import os
import smtplib
from datetime import date, datetime, time
from decimal import Decimal
from email.message import EmailMessage
from functools import wraps

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


def tutor_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _current_tutor():
            flash("Silakan masuk dengan Gmail tutor terlebih dahulu.", "warning")
            return redirect(url_for("tutor_portal.login"))
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


def _build_login_url(token):
    base_url = current_app.config.get("TUTOR_PORTAL_BASE_URL", "").rstrip("/")
    path = url_for("tutor_portal.verify", token=token)
    return f"{base_url}{path}" if base_url else url_for(
        "tutor_portal.verify", token=token, _external=True
    )


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
        email = _normalize_email(request.form.get("email"))
        if not email.endswith("@gmail.com"):
            flash("Gunakan alamat Gmail tutor yang terdaftar.", "danger")
            return redirect(url_for("tutor_portal.login"))

        tutor = Tutor.query.filter(db.func.lower(Tutor.email) == email).first()
        if not tutor or not tutor.is_active:
            flash("Gmail belum cocok dengan data tutor aktif.", "danger")
            return redirect(url_for("tutor_portal.login"))

        token = _token_serializer().dumps({"tutor_id": tutor.id, "email": email})
        verify_url = _build_login_url(token)
        try:
            sent = _send_login_email(tutor, verify_url)
        except Exception as exc:
            current_app.logger.warning("Failed to send tutor login email: %s", exc)
            sent = False
        if sent:
            flash("Link verifikasi sudah dikirim ke Gmail tutor.", "success")
        else:
            flash("MAIL_SERVER belum aktif. Link verifikasi dicatat di log server.", "warning")
        return render_template("tutor_portal/login_sent.html", tutor=tutor)

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
