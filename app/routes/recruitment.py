"""Recruitment form and CRM workflow."""

import json
import os
import smtplib
import html
from datetime import datetime
from email.message import EmailMessage
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
    Response,
)
from flask_login import login_required
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Curriculum,
    Level,
    PricingRule,
    RecruitmentCandidate,
    Subject,
    Tutor,
)
from app.routes.tutor_portal import (
    SCHEDULE_HOUR_SLOTS,
    WEEKDAY_NAMES,
    _bot_request,
    _ensure_tutor_portal_credentials,
    _get_whatsapp_session_status,
    _normalize_email,
    _normalize_whatsapp_phone,
)
from app.utils import decode_public_id


recruitment_bp = Blueprint("recruitment", __name__, url_prefix="/recruitment")

RECRUITMENT_STATUSES = {
    "draft": "Draft",
    "submitted": "Pelamar",
    "selected": "Pelamar Terpilih",
    "interview": "Interview",
    "contract_sent": "Kontrak Dikirim",
    "signed": "Kontrak Ditandatangani",
}
CONTRACT_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
MAX_SIGNATURE_DATA_URL_LENGTH = 500_000
LAST_EDUCATION_LEVELS = ["Vokasi", "S1", "S2", "S3"]
GENDER_OPTIONS = [("male", "Laki-laki"), ("female", "Perempuan")]
UNIVERSITY_OPTIONS = list(dict.fromkeys([
    "IAIN Kediri",
    "IAIN Kudus",
    "IAIN Metro",
    "IAIN Palangka Raya",
    "IAIN Parepare",
    "IAIN Ponorogo",
    "IAIN Salatiga",
    "IAIN Syekh Nurjati Cirebon",
    "Institut Agama Islam Negeri Tulungagung",
    "Institut Bisnis dan Informatika Kwik Kian Gie",
    "Institut Bisnis Nusantara",
    "Institut Informatika dan Bisnis Darmajaya",
    "Institut Kesenian Jakarta",
    "Institut Pertanian Bogor",
    "Institut Seni Indonesia Denpasar",
    "Institut Seni Indonesia Surakarta",
    "Institut Seni Indonesia Yogyakarta",
    "Institut Teknologi Adhi Tama Surabaya",
    "Institut Teknologi Bandung",
    "Institut Teknologi Del",
    "Institut Teknologi Kalimantan",
    "Institut Teknologi Nasional Bandung",
    "Institut Teknologi Nasional",
    "Institut Teknologi PLN",
    "Institut Teknologi Sumatera",
    "Institut Teknologi Sepuluh Nopember",
    "Politeknik Caltex Riau",
    "Politeknik Elektronika Negeri Surabaya",
    "Politeknik Manufaktur Bandung",
    "Politeknik Negeri Bali",
    "Politeknik Negeri Bandung",
    "Politeknik Negeri Batam",
    "Politeknik Negeri Banjarmasin",
    "Politeknik Negeri Banyuwangi",
    "Politeknik Negeri Jember",
    "Politeknik Elektronika Negeri Surabaya",
    "Politeknik Negeri Jakarta",
    "Politeknik Negeri Kupang",
    "Politeknik Negeri Lampung",
    "Politeknik Negeri Malang",
    "Politeknik Negeri Medan",
    "Politeknik Negeri Padang",
    "Politeknik Negeri Pontianak",
    "Politeknik Negeri Samarinda",
    "Politeknik Negeri Semarang",
    "Politeknik Negeri Sriwijaya",
    "Politeknik Negeri Surabaya",
    "President University",
    "STIE Indonesia Surabaya",
    "STIKOM Bali",
    "STMIK AMIKOM Surakarta",
    "STMIK LIKMI",
    "Telkom University",
    "UIN Alauddin Makassar",
    "UIN Ar-Raniry Banda Aceh",
    "UIN Imam Bonjol Padang",
    "UIN Mataram",
    "UIN Maulana Malik Ibrahim Malang",
    "UIN Raden Fatah Palembang",
    "UIN Raden Intan Lampung",
    "UIN Sjech M. Djamil Djambek Bukittinggi",
    "UIN Sultan Aji Muhammad Idris Samarinda",
    "UIN Sultan Maulana Hasanuddin Banten",
    "UIN Sultan Syarif Kasim Riau",
    "UIN Sunan Ampel Surabaya",
    "UIN Sunan Gunung Djati Bandung",
    "UIN Sunan Kalijaga Yogyakarta",
    "UIN Syarif Hidayatullah Jakarta",
    "UIN Walisongo Semarang",
    "Universitas 17 Agustus 1945 Surabaya",
    "Universitas Advent Indonesia",
    "Universitas Ahmad Dahlan",
    "Universitas Airlangga",
    "Universitas Al Azhar Indonesia",
    "Universitas Al-Azhar Medan",
    "Universitas Alma Ata",
    "Universitas Amikom Yogyakarta",
    "Universitas Andalas",
    "Universitas Atma Jaya Makassar",
    "Universitas Atma Jaya Yogyakarta",
    "Universitas Bakrie",
    "Universitas Balikpapan",
    "Universitas Bandar Lampung",
    "Universitas Bangka Belitung",
    "Universitas Batam",
    "Universitas Bengkulu",
    "Universitas Bina Nusantara",
    "Universitas Borobudur",
    "Universitas Brawijaya",
    "Universitas Budi Luhur",
    "Universitas Bunda Mulia",
    "Universitas Bung Hatta",
    "Universitas Cenderawasih",
    "Universitas Ciputra",
    "Universitas Darma Persada",
    "Universitas Darussalam Gontor",
    "Universitas Dehasen Bengkulu",
    "Universitas Dian Nuswantoro",
    "Universitas Diponegoro",
    "Universitas Dr. Soetomo",
    "Universitas Esa Unggul",
    "Universitas Gadjah Mada",
    "Universitas Galuh",
    "Universitas Garut",
    "Universitas Halu Oleo",
    "Universitas Gunadarma",
    "Universitas Hasanuddin",
    "Universitas Hayam Wuruk Perbanas",
    "Universitas Indonesia",
    "Universitas Internasional Batam",
    "Universitas Islam Bandung",
    "Universitas Islam Indonesia",
    "Universitas Islam Jakarta",
    "Universitas Islam Kadiri",
    "Universitas Islam Kalimantan Muhammad Arsyad Al Banjari",
    "Universitas Islam Lamongan",
    "Universitas Islam Malang",
    "Universitas Islam Negeri Alauddin Makassar",
    "Universitas Islam Negeri Ar-Raniry Banda Aceh",
    "Universitas Islam Negeri Imam Bonjol Padang",
    "Universitas Islam Indonesia",
    "Universitas Islam Negeri Maulana Malik Ibrahim Malang",
    "Universitas Islam Negeri Raden Fatah Palembang",
    "Universitas Islam Negeri Raden Intan Lampung",
    "Universitas Islam Negeri Sunan Ampel Surabaya",
    "Universitas Islam Negeri Sunan Gunung Djati Bandung",
    "Universitas Islam Negeri Sunan Kalijaga Yogyakarta",
    "Universitas Islam Negeri Syarif Hidayatullah Jakarta",
    "Universitas Islam Negeri Walisongo Semarang",
    "Universitas Islam Riau",
    "Universitas Islam Sultan Agung",
    "Universitas Islam Syekh Yusuf",
    "Universitas Jambi",
    "Universitas Jember",
    "Universitas Jenderal Achmad Yani",
    "Universitas Jenderal Soedirman",
    "Universitas Kanjuruhan Malang",
    "Universitas Karimun",
    "Universitas Katolik Parahyangan",
    "Universitas Katolik Soegijapranata",
    "Universitas Katolik Widya Mandala Surabaya",
    "Universitas Klabat",
    "Universitas Komputer Indonesia",
    "Universitas Kristen Petra",
    "Universitas Kristen Satya Wacana",
    "Universitas Kristen Duta Wacana",
    "Universitas Kristen Indonesia",
    "Universitas Kristen Krida Wacana",
    "Universitas Kristen Maranatha",
    "Universitas Kuningan",
    "Universitas Kutai Kartanegara",
    "Universitas Lambung Mangkurat",
    "Universitas Lampung",
    "Universitas Lancang Kuning",
    "Universitas Ma Chung",
    "Universitas Madura",
    "Universitas Mahasaraswati Denpasar",
    "Universitas Malikussaleh",
    "Universitas Maritim Raja Ali Haji",
    "Universitas Mercu Buana",
    "Universitas Merdeka Malang",
    "Universitas Mataram",
    "Universitas Mpu Tantular",
    "Universitas Muhammadiyah Aceh",
    "Universitas Muhammadiyah Gresik",
    "Universitas Muhammadiyah Jakarta",
    "Universitas Muhammadiyah Jember",
    "Universitas Muhammadiyah Malang",
    "Universitas Muhammadiyah Makassar",
    "Universitas Muhammadiyah Ponorogo",
    "Universitas Muhammadiyah Purwokerto",
    "Universitas Muhammadiyah Sidoarjo",
    "Universitas Muhammadiyah Surabaya",
    "Universitas Muhammadiyah Surakarta",
    "Universitas Muhammadiyah Tangerang",
    "Universitas Muhammadiyah Tasikmalaya",
    "Universitas Muhammadiyah Yogyakarta",
    "Universitas Multimedia Nusantara",
    "Universitas Muria Kudus",
    "Universitas Musamus Merauke",
    "Universitas Muslim Indonesia",
    "Universitas Nahdlatul Ulama Surabaya",
    "Universitas Nasional",
    "Universitas Narotama",
    "Universitas Negeri Gorontalo",
    "Universitas Negeri Jakarta",
    "Universitas Negeri Makassar",
    "Universitas Negeri Malang",
    "Universitas Negeri Medan",
    "Universitas Negeri Padang",
    "Universitas Negeri Semarang",
    "Universitas Negeri Surabaya",
    "Universitas Negeri Yogyakarta",
    "Universitas Nusa Cendana",
    "Universitas Padjadjaran",
    "Universitas Pakuan",
    "Universitas Palangka Raya",
    "Universitas Pamulang",
    "Universitas Pasundan",
    "Universitas Pattimura",
    "Universitas Pelita Bangsa",
    "Universitas Pelita Harapan",
    "Universitas Pembangunan Nasional Veteran Jawa Timur",
    "Universitas Pembangunan Nasional Veteran Jakarta",
    "Universitas Pembangunan Nasional Veteran Yogyakarta",
    "Universitas Pendidikan Ganesha",
    "Universitas Pendidikan Indonesia",
    "Universitas Persada Indonesia YAI",
    "Universitas Pertamina",
    "Universitas PGRI Adi Buana Surabaya",
    "Universitas PGRI Madiun",
    "Universitas PGRI Semarang",
    "Universitas PGRI Yogyakarta",
    "Universitas Prima Indonesia",
    "Universitas Prof. Dr. Moestopo",
    "Universitas Putra Indonesia YPTK Padang",
    "Universitas Riau Kepulauan",
    "Universitas Riau",
    "Universitas Sahid",
    "Universitas Sam Ratulangi",
    "Universitas Samudra",
    "Universitas Sam Ratulangi",
    "Universitas Sanata Dharma",
    "Universitas Sarjanawiyata Tamansiswa",
    "Universitas Sari Mutiara Indonesia",
    "Universitas Semarang",
    "Universitas Sebelas Maret",
    "Universitas Singaperbangsa Karawang",
    "Universitas Siliwangi",
    "Universitas Simalungun",
    "Universitas Sisingamangaraja XII Tapanuli",
    "Universitas Sriwijaya",
    "Universitas Stikubank",
    "Universitas Sriwijaya",
    "Universitas Sumatera Utara",
    "Universitas Sultan Ageng Tirtayasa",
    "Universitas Sulawesi Barat",
    "Universitas Surakarta",
    "Universitas Surabaya",
    "Universitas Swadaya Gunung Jati",
    "Universitas Swiss German",
    "Universitas Syiah Kuala",
    "Universitas Tadulako",
    "Universitas Tanjungpura",
    "Universitas Tarumanagara",
    "Universitas Teknokrat Indonesia",
    "Universitas Teknologi Yogyakarta",
    "Universitas Telkom",
    "Universitas Terbuka",
    "Universitas Tidar",
    "Universitas Tjut Nyak Dhien",
    "Universitas Trunojoyo Madura",
    "Universitas Udayana",
    "Universitas Wahid Hasyim",
    "Universitas Warmadewa",
    "Universitas Wijaya Kusuma Surabaya",
    "Universitas Widyatama",
    "Universitas Yarsi",
]))


def _token_serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="lbb-recruitment"
    )


def _build_google_callback_url():
    base_url = (current_app.config.get("RECRUITMENT_BASE_URL") or "").rstrip("/")
    path = url_for("recruitment.google_callback")
    return f"{base_url}{path}" if base_url else url_for(
        "recruitment.google_callback", _external=True
    )


def _fetch_google_userinfo(access_token):
    req = urllib_request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib_request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _tutor_for_email(email):
    email = _normalize_email(email)
    if not email:
        return None
    return Tutor.query.filter(db.func.lower(Tutor.email) == email).first()


def _candidate_has_submitted_form(candidate):
    return bool(
        candidate and getattr(candidate, "status", "draft") and candidate.status != "draft"
    )


def _sync_candidate_from_tutor(candidate, tutor):
    if not candidate or not tutor:
        return
    candidate.tutor_id = candidate.tutor_id or tutor.id
    candidate.email_verified = True
    candidate.name = candidate.name or tutor.name
    candidate.phone = candidate.phone or tutor.phone
    candidate.address = candidate.address or tutor.address
    candidate.cv_file_path = candidate.cv_file_path or tutor.cv_file_path
    candidate.photo_file_path = candidate.photo_file_path or tutor.profile_photo_path
    if candidate.status == "draft":
        candidate.status = "submitted"
    candidate.updated_at = datetime.utcnow()


def _candidate_has_dashboard_access(candidate):
    if not candidate:
        return False
    if _candidate_has_submitted_form(candidate):
        return True
    if getattr(candidate, "tutor_id", None):
        return True
    return _tutor_for_email(getattr(candidate, "google_email", "")) is not None


def _bypass_tutor_for_candidate(candidate):
    if not candidate:
        return None
    if candidate.tutor_id:
        return db.session.get(Tutor, candidate.tutor_id)
    return _tutor_for_email(getattr(candidate, "google_email", ""))


def _is_bypass_tutor_candidate(candidate):
    return bool(
        candidate
        and candidate.status != "signed"
        and getattr(candidate, "tutor_id", None)
    )


def _candidate_profile_complete(candidate):
    return bool(
        candidate
        and candidate.name
        and candidate.phone
        and candidate.address
        and candidate.age
        and candidate.gender
        and candidate.last_education_level
        and candidate.university_name
        and candidate.teaching_preferences
        and candidate.availability_slots
        and candidate.cv_file_path
        and candidate.photo_file_path
    )


def _sync_bypass_profile_to_tutor(candidate, tutor):
    if not candidate or not tutor:
        return
    tutor.name = candidate.name or tutor.name
    tutor.phone = candidate.phone or tutor.phone
    tutor.email = _normalize_email(candidate.google_email) or tutor.email
    tutor.address = candidate.address or tutor.address
    tutor.profile_photo_path = candidate.photo_file_path or tutor.profile_photo_path
    tutor.cv_file_path = candidate.cv_file_path or tutor.cv_file_path
    tutor.status = "active"
    tutor.is_active = True
    tutor.portal_email_verified = True
    tutor.portal_email_verified_at = tutor.portal_email_verified_at or datetime.utcnow()
    tutor.updated_at = datetime.utcnow()
    candidate.tutor_id = tutor.id


def _candidate_applications(candidate):
    if not candidate or not candidate.google_email:
        return []
    return (
        RecruitmentCandidate.query.filter(
            db.func.lower(RecruitmentCandidate.google_email)
            == _normalize_email(candidate.google_email)
        )
        .order_by(RecruitmentCandidate.created_at.desc(), RecruitmentCandidate.id.desc())
        .all()
    )


def _application_kind(candidate):
    if candidate.tutor_id:
        return "Tutor aktif"
    if candidate.status in {"contract_sent", "signed"}:
        return "Offering tutor"
    return "Lamaran tutor"


def _candidate_file_flags(candidate):
    upload_root = current_app.config["UPLOAD_FOLDER"]

    def exists(relative_path):
        if not relative_path:
            return False
        target = os.path.abspath(os.path.join(upload_root, relative_path))
        root = os.path.abspath(upload_root)
        return target.startswith(root + os.sep) and os.path.isfile(target)

    return {
        "cv_exists": exists(candidate.cv_file_path),
        "photo_exists": exists(candidate.photo_file_path),
    }


def _dashboard_document_response(title, content):
    escaped_title = html.escape(title)
    escaped_content = html.escape(content or "-")
    document = f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      color: #111827;
      font-family: Arial, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      margin: 0;
      padding: 24px;
      background: #ffffff;
    }}
    h1 {{
      font-size: 18px;
      margin: 0 0 16px;
    }}
    pre {{
      font-family: Arial, sans-serif;
      margin: 0;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
  <h1>{escaped_title}</h1>
  <pre>{escaped_content}</pre>
</body>
</html>"""
    return Response(document, mimetype="text/html")


def _current_candidate():
    candidate_id = session.get("recruitment_candidate_id")
    if not candidate_id:
        return None
    return RecruitmentCandidate.query.get(candidate_id)


def _allowed_upload(filename, extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions


def _save_candidate_upload(file_storage, candidate, folder, extensions):
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_upload(file_storage.filename, extensions):
        raise ValueError("Format file tidak didukung.")
    filename = secure_filename(file_storage.filename)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    relative_dir = os.path.join("recruitment", folder)
    target_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_dir)
    os.makedirs(target_dir, exist_ok=True)
    relative_path = os.path.join(
        relative_dir, f"candidate-{candidate.id}-{stamp}-{filename}"
    )
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path))
    return relative_path


def _candidate_from_ref(candidate_ref):
    try:
        candidate_id = decode_public_id(candidate_ref, "recruitment_candidate")
    except ValueError:
        abort(404)
    return RecruitmentCandidate.query.get_or_404(candidate_id)


def _contract_token(candidate):
    return _token_serializer().dumps(
        {
            "candidate_id": candidate.id,
            "purpose": "recruitment_contract",
        }
    )


def _candidate_from_contract_token(token):
    try:
        payload = _token_serializer().loads(
            token,
            max_age=CONTRACT_TOKEN_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        flash("Link kontrak sudah kedaluwarsa. Hubungi admin untuk dikirim ulang.", "warning")
        return None
    except BadSignature:
        flash("Link kontrak tidak valid.", "danger")
        return None
    if payload.get("purpose") != "recruitment_contract":
        flash("Link kontrak tidak valid.", "danger")
        return None
    return RecruitmentCandidate.query.get(payload.get("candidate_id"))


def _contract_url(candidate, external=False):
    path = url_for(
        "recruitment.contract",
        token=_contract_token(candidate),
    )
    if external:
        recruitment_base_url = (
            current_app.config.get("RECRUITMENT_BASE_URL") or ""
        ).rstrip("/")
        if recruitment_base_url:
            return f"{recruitment_base_url}{path}"
        return url_for("recruitment.contract", token=_contract_token(candidate), _external=True)
    return path


def _send_recruitment_verification_email(candidate):
    token = _token_serializer().dumps(
        {
            "candidate_id": candidate.id,
            "email": _normalize_email(candidate.google_email),
            "purpose": "recruitment_verify_email",
        }
    )
    verify_path = url_for("recruitment.verify_email", token=token)
    recruitment_base_url = (current_app.config.get("RECRUITMENT_BASE_URL") or "").rstrip("/")
    verify_url = (
        f"{recruitment_base_url}{verify_path}"
        if recruitment_base_url
        else url_for("recruitment.verify_email", token=token, _external=True)
    )
    if not current_app.config.get("MAIL_SERVER"):
        current_app.logger.warning("Recruitment verification link: %s", verify_url)
        return False

    msg = EmailMessage()
    msg["Subject"] = "Verifikasi Email Recruitment LBB Super Smart"
    msg["From"] = current_app.config.get("MAIL_DEFAULT_SENDER")
    msg["To"] = candidate.google_email
    msg.set_content(
        "Klik link berikut untuk melanjutkan form recruitment LBB Super Smart:\n\n"
        f"{verify_url}\n\nLink berlaku 24 jam."
    )
    with smtplib.SMTP(
        current_app.config["MAIL_SERVER"], int(current_app.config.get("MAIL_PORT", 587))
    ) as smtp:
        if current_app.config.get("MAIL_USE_TLS"):
            smtp.starttls()
        username = current_app.config.get("MAIL_USERNAME")
        password = current_app.config.get("MAIL_PASSWORD")
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)
    return True


def _current_offering_amount():
    rule = (
        PricingRule.query.filter_by(is_active=True)
        .order_by(PricingRule.tutor_rate_per_meeting.desc(), PricingRule.id.desc())
        .first()
    )
    return float(rule.tutor_rate_per_meeting) if rule else 0


def _teaching_option_choices():
    def add_label(collection, label):
        key = label.lower()
        if key not in seen:
            collection.append(label)
            seen.add(key)

    def add_teaching_labels(collection, subject_name, level_name, curriculum_name):
        add_label(collection, f"{subject_name} {level_name} {curriculum_name}")
        if curriculum_name.lower().startswith("internasional"):
            add_label(
                collection,
                f"{subject_name} {level_name} {curriculum_name.replace('Internasional', 'Cambridge', 1)}",
            )

    rules = (
        PricingRule.query.filter_by(is_active=True)
        .join(PricingRule.subject, isouter=True)
        .join(PricingRule.level, isouter=True)
        .join(PricingRule.curriculum, isouter=True)
        .order_by(Subject.name.asc(), Level.name.asc(), Curriculum.name.asc())
        .all()
    )
    labels = []
    seen = set()
    for rule in rules:
        if not rule.subject or not rule.level or not rule.curriculum:
            continue
        add_teaching_labels(
            labels,
            rule.subject.name,
            rule.level.name,
            rule.curriculum.name,
        )

    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.name.asc()).all()
    levels = Level.query.filter_by(is_active=True).order_by(Level.name.asc()).all()
    curriculums = (
        Curriculum.query.filter_by(is_active=True).order_by(Curriculum.name.asc()).all()
    )
    for subject in subjects:
        for level in levels:
            for curriculum in curriculums:
                add_teaching_labels(labels, subject.name, level.name, curriculum.name)
    return labels


def _candidate_summary_items(candidate):
    items = candidate.teaching_preferences
    if items:
        return items
    return [candidate.subject_interest] if candidate.subject_interest else []


def _build_contract_text(candidate):
    teaching_items = "\n".join(
        f"- {item}" for item in _candidate_summary_items(candidate)
    ) or "-"
    return (
        f"KONTRAK DIGITAL TUTOR LBB SUPER SMART\n\n"
        f"Nama: {candidate.name}\n"
        f"Email: {candidate.google_email}\n"
        f"No. WhatsApp: {candidate.phone}\n"
        f"Usia: {candidate.age or '-'}\n"
        f"Jenis Kelamin: {dict(GENDER_OPTIONS).get(candidate.gender, candidate.gender or '-')}\n"
        f"Pendidikan Terakhir: {candidate.last_education_level or '-'}\n"
        f"Universitas: {candidate.university_name or '-'}\n"
        f"Alamat: {candidate.address or '-'}\n"
        f"Bidang/Mapel:\n{teaching_items}\n\n"
        "Kandidat menyatakan bersedia menjadi tutor LBB Super Smart, menjaga "
        "profesionalitas pembelajaran, mengikuti jadwal yang disetujui admin, "
        "dan mematuhi ketentuan operasional lembaga."
    )


def _build_offering_text(candidate):
    amount = _current_offering_amount()
    amount_text = (
        f"Rp {amount:,.0f}".replace(",", ".")
        if amount
        else "mengikuti database fee aktif"
    )
    return (
        f"OFFERING DIGITAL TUTOR\n\n"
        f"Halo {candidate.name},\n"
        f"Offering fee tutor per sesi saat ini: {amount_text}.\n"
        "Nominal final mengikuti aturan tarif aktif, mata pelajaran, jenjang, "
        "dan enrollment yang ditetapkan admin."
    )


def _send_candidate_whatsapp(candidate, message):
    contact_id = _normalize_whatsapp_phone(candidate.phone)
    if not contact_id:
        return False, "Nomor WhatsApp kandidat belum tersedia."
    payload, status_code = _bot_request(
        "POST",
        "/messages/send",
        {"to": contact_id, "message": message},
        timeout=30,
    )
    if status_code == 200 and payload.get("ok"):
        return True, ""
    return False, payload.get("error") or "Bot error"


def _next_tutor_code():
    prefix = "TTR-REC"
    count = Tutor.query.filter(Tutor.tutor_code.like(f"{prefix}%")).count() + 1
    while True:
        code = f"{prefix}-{count:04d}"
        if not Tutor.query.filter_by(tutor_code=code).first():
            return code
        count += 1


def _create_tutor_from_candidate(candidate):
    if candidate.tutor:
        return candidate.tutor
    tutor = Tutor(
        tutor_code=_next_tutor_code(),
        name=candidate.name,
        phone=candidate.phone,
        email=_normalize_email(candidate.google_email),
        address=candidate.address,
        profile_photo_path=candidate.photo_file_path,
        cv_file_path=candidate.cv_file_path,
        status="active",
        is_active=True,
        portal_email_verified=True,
        portal_email_verified_at=datetime.utcnow(),
        portal_must_change_password=True,
    )
    db.session.add(tutor)
    db.session.flush()
    _ensure_tutor_portal_credentials(tutor)
    candidate.tutor_id = tutor.id
    return tutor


def _availability_by_slot(candidate):
    values = {}
    for slot in candidate.availability_slots:
        try:
            weekday = int(slot.get("weekday"))
            hour = int(slot.get("hour"))
        except (TypeError, ValueError, AttributeError):
            continue
        state = slot.get("state")
        if weekday in range(7) and hour in SCHEDULE_HOUR_SLOTS and state in {
            "available",
            "unavailable",
        }:
            values[(weekday, hour)] = state
    return values


def _build_candidate_availability_rows(candidate):
    selected_by_slot = _availability_by_slot(candidate)
    rows = []
    available_count = 0
    unavailable_count = 0
    for hour in SCHEDULE_HOUR_SLOTS:
        cells = []
        for weekday in range(7):
            state = selected_by_slot.get((weekday, hour), "unavailable")
            if state == "available":
                available_count += 1
            else:
                unavailable_count += 1
            cells.append(
                {
                    "weekday": weekday,
                    "day_name": WEEKDAY_NAMES[weekday],
                    "hour": hour,
                    "field_name": f"availability_{weekday}_{hour}",
                    "state": state,
                    "label": "Luang" if state == "available" else "Tidak Bisa",
                }
            )
        rows.append({"hour": hour, "cells": cells})
    return {
        "weekday_names": WEEKDAY_NAMES,
        "hour_slots": SCHEDULE_HOUR_SLOTS,
        "rows": rows,
        "summary": {
            "available_count": available_count,
            "unavailable_count": unavailable_count,
        },
    }


def _candidate_availability_slots_from_form(form):
    slots = []
    available_count = 0
    unavailable_count = 0
    for weekday in range(7):
        for hour in SCHEDULE_HOUR_SLOTS:
            field_name = f"availability_{weekday}_{hour}"
            state = form.get(field_name, "unavailable")
            if state not in {"available", "unavailable"}:
                state = "unavailable"
            if state == "available":
                available_count += 1
            else:
                unavailable_count += 1
            slots.append(
                {
                    "weekday": weekday,
                    "day_name": WEEKDAY_NAMES[weekday],
                    "hour": hour,
                    "start_time": f"{hour:02d}:00",
                    "end_time": f"{hour + 1:02d}:00",
                    "state": state,
                }
            )
    if available_count == 0:
        raise ValueError("Pilih minimal satu waktu luang berwarna hijau.")
    return slots


def _sign_candidate_contract(candidate, signature):
    if candidate.status == "signed":
        flash("Kontrak sudah pernah ditandatangani.", "warning")
        return False
    if candidate.status != "contract_sent":
        flash("Kontrak belum siap ditandatangani. Tunggu undangan dari admin.", "warning")
        return False
    if not signature.startswith("data:image/"):
        flash("Tanda tangan digital wajib diisi.", "danger")
        return False
    if len(signature) > MAX_SIGNATURE_DATA_URL_LENGTH:
        flash("Ukuran tanda tangan terlalu besar. Hapus dan tanda tangani ulang.", "danger")
        return False
    candidate.signature_data_url = signature
    candidate.signed_at = datetime.utcnow()
    candidate.status = "signed"
    tutor = _create_tutor_from_candidate(candidate)
    db.session.commit()
    session["tutor_portal_tutor_id"] = tutor.id
    flash("Kontrak ditandatangani. Dashboard tutor sudah aktif.", "success")
    return True


@recruitment_bp.route("/", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        email = _normalize_email(request.form.get("google_email"))
        if not email.endswith("@gmail.com"):
            flash("Gunakan akun Gmail/Google aktif untuk recruitment.", "danger")
            return redirect(url_for("recruitment.start"))
        if request.form.get("action") == "login":
            password = request.form.get("password") or ""
            candidate = RecruitmentCandidate.query.filter(
                db.func.lower(RecruitmentCandidate.google_email) == email
            ).first()
            if not candidate or not candidate.check_password(password):
                flash("Email atau password dashboard recruitment tidak sesuai.", "danger")
                return redirect(url_for("recruitment.start"))
            session["recruitment_candidate_id"] = candidate.id
            candidate.updated_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("recruitment.dashboard"))
        candidate = RecruitmentCandidate.query.filter(
            db.func.lower(RecruitmentCandidate.google_email) == email
        ).first()
        if not candidate:
            candidate = RecruitmentCandidate(google_email=email)
            db.session.add(candidate)
            db.session.flush()
        candidate.google_email = email
        candidate.updated_at = datetime.utcnow()
        db.session.commit()
        sent = _send_recruitment_verification_email(candidate)
        session["recruitment_candidate_id"] = candidate.id
        if sent:
            flash("Link verifikasi sudah dikirim ke Gmail.", "success")
        else:
            flash(
                "Email disimpan. Link verifikasi dicatat di log server karena SMTP belum aktif.",
                "warning",
            )
        return redirect(url_for("recruitment.form"))
    return render_template("recruitment/start.html")


@recruitment_bp.route("/daftar", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = _normalize_email(request.form.get("google_email"))
        if not email.endswith("@gmail.com"):
            flash("Gunakan akun Gmail/Google aktif untuk recruitment.", "danger")
            return render_template("recruitment/register.html", google_email=email)
        candidate = RecruitmentCandidate.query.filter(
            db.func.lower(RecruitmentCandidate.google_email) == email
        ).first()
        if not candidate:
            candidate = RecruitmentCandidate(google_email=email)
            db.session.add(candidate)
            db.session.flush()
        candidate.google_email = email
        candidate.updated_at = datetime.utcnow()
        db.session.commit()
        sent = _send_recruitment_verification_email(candidate)
        session["recruitment_candidate_id"] = candidate.id
        if sent:
            flash("Link verifikasi sudah dikirim ke Gmail.", "success")
        else:
            flash(
                "Email disimpan. Link verifikasi dicatat di log server karena SMTP belum aktif.",
                "warning",
            )
        return redirect(url_for("recruitment.form"))
    return render_template("recruitment/register.html", google_email="")


@recruitment_bp.route("/google/login", methods=["GET"])
def google_login():
    client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        flash("Login Google recruitment belum dikonfigurasi. Daftar memakai Gmail aktif.", "warning")
        return redirect(url_for("recruitment.register"))

    state = _token_serializer().dumps({"purpose": "recruitment_google_login"})
    params = urllib_parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _build_google_callback_url(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@recruitment_bp.route("/google/callback", methods=["GET"])
def google_callback():
    if request.args.get("error"):
        flash("Login Google dibatalkan atau ditolak.", "warning")
        return redirect(url_for("recruitment.start"))

    try:
        payload = _token_serializer().loads(request.args.get("state", ""), max_age=600)
    except (SignatureExpired, BadSignature):
        flash("Sesi Login Google tidak valid. Silakan coba lagi.", "danger")
        return redirect(url_for("recruitment.start"))
    if payload.get("purpose") != "recruitment_google_login":
        flash("Sesi Login Google tidak valid. Silakan coba lagi.", "danger")
        return redirect(url_for("recruitment.start"))

    code = request.args.get("code")
    if not code:
        flash("Kode Login Google tidak ditemukan.", "danger")
        return redirect(url_for("recruitment.start"))

    token_payload = urllib_parse.urlencode(
        {
            "code": code,
            "client_id": current_app.config.get("GOOGLE_OAUTH_CLIENT_ID"),
            "client_secret": current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"),
            "redirect_uri": _build_google_callback_url(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    try:
        token_req = urllib_request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib_request.urlopen(token_req, timeout=15) as response:
            token_data = json.loads(response.read().decode("utf-8"))
        userinfo = _fetch_google_userinfo(token_data.get("access_token"))
    except (urllib_error.URLError, ValueError, KeyError, TypeError) as exc:
        current_app.logger.warning("Recruitment Google login failed: %s", exc)
        flash("Login Google gagal. Silakan coba lagi atau daftar memakai Gmail.", "danger")
        return redirect(url_for("recruitment.start"))

    email = _normalize_email(userinfo.get("email"))
    if not email or not userinfo.get("email_verified"):
        flash("Gmail belum terverifikasi oleh Google.", "danger")
        return redirect(url_for("recruitment.start"))

    candidate = RecruitmentCandidate.query.filter(
        db.func.lower(RecruitmentCandidate.google_email) == email
    ).first()
    tutor = _tutor_for_email(email)
    if not candidate:
        candidate = RecruitmentCandidate(google_email=email)
        db.session.add(candidate)
        db.session.flush()
    candidate.google_email = email
    candidate.email_verified = True
    _sync_candidate_from_tutor(candidate, tutor)
    candidate.updated_at = datetime.utcnow()
    db.session.commit()
    session["recruitment_candidate_id"] = candidate.id
    if tutor and not _candidate_profile_complete(candidate):
        return redirect(url_for("recruitment.form"))
    if _candidate_has_dashboard_access(candidate):
        return redirect(url_for("recruitment.dashboard"))
    return redirect(url_for("recruitment.form"))


@recruitment_bp.route("/verify/<token>")
def verify_email(token):
    try:
        payload = _token_serializer().loads(token, max_age=86400)
    except SignatureExpired:
        flash("Link verifikasi sudah kedaluwarsa.", "warning")
        return redirect(url_for("recruitment.start"))
    except BadSignature:
        flash("Link verifikasi tidak valid.", "danger")
        return redirect(url_for("recruitment.start"))

    candidate = RecruitmentCandidate.query.get(payload.get("candidate_id"))
    if (
        not candidate
        or payload.get("purpose") != "recruitment_verify_email"
        or _normalize_email(candidate.google_email) != payload.get("email")
    ):
        flash("Data verifikasi tidak cocok.", "danger")
        return redirect(url_for("recruitment.start"))

    candidate.email_verified = True
    candidate.updated_at = datetime.utcnow()
    session["recruitment_candidate_id"] = candidate.id
    db.session.commit()
    flash("Email berhasil diverifikasi. Lengkapi data recruitment.", "success")
    return redirect(url_for("recruitment.form"))


@recruitment_bp.route("/form", methods=["GET", "POST"])
def form():
    candidate = _current_candidate()
    if not candidate:
        flash("Mulai dari login Google/Gmail terlebih dahulu.", "warning")
        return redirect(url_for("recruitment.start"))
    is_bypass_profile = _is_bypass_tutor_candidate(candidate)
    if request.method == "GET":
        tutor = _tutor_for_email(getattr(candidate, "google_email", ""))
        if tutor and not getattr(candidate, "tutor_id", None):
            _sync_candidate_from_tutor(candidate, tutor)
            db.session.commit()
        is_bypass_profile = _is_bypass_tutor_candidate(candidate)
        needs_bypass_profile = (
            is_bypass_profile and not _candidate_profile_complete(candidate)
        )
        if (
            request.args.get("edit") != "1"
            and _candidate_has_dashboard_access(candidate)
            and not needs_bypass_profile
        ):
            return redirect(url_for("recruitment.dashboard"))
    if request.method == "POST":
        if not candidate.email_verified:
            flash("Verifikasi email Google/Gmail terlebih dahulu sebelum mengirim data.", "warning")
            return redirect(url_for("recruitment.form"))
        candidate.name = (request.form.get("name") or "").strip()
        candidate.phone = (request.form.get("phone") or "").strip()
        candidate.address = (request.form.get("address") or "").strip()
        candidate.gender = (request.form.get("gender") or "").strip()
        candidate.last_education_level = (
            request.form.get("last_education_level") or ""
        ).strip()
        candidate.university_name = (request.form.get("university_name") or "").strip()
        teaching_preferences = request.form.getlist("teaching_preferences")
        valid_teaching_options = set(_teaching_option_choices())
        valid_universities = set(UNIVERSITY_OPTIONS)
        age_raw = (request.form.get("age") or "").strip()
        try:
            candidate.age = int(age_raw) if age_raw else None
        except ValueError:
            candidate.age = None
        candidate.teaching_preferences = teaching_preferences
        if not candidate.name or not candidate.phone or not candidate.address:
            flash("Nama, nomor WhatsApp aktif, dan alamat wajib diisi.", "danger")
            return redirect(url_for("recruitment.form"))
        if (
            not candidate.age
            or candidate.age < 17
            or candidate.age > 80
            or candidate.gender not in {key for key, _ in GENDER_OPTIONS}
            or candidate.last_education_level not in LAST_EDUCATION_LEVELS
            or not candidate.university_name
            or not candidate.teaching_preferences
        ):
            flash(
                "Lengkapi usia, jenis kelamin, pendidikan terakhir, universitas, dan minimal satu pilihan mapel.",
                "danger",
            )
            return redirect(url_for("recruitment.form"))
        if any(item not in valid_teaching_options for item in candidate.teaching_preferences):
            flash("Pilih mapel dari daftar dropdown yang tersedia.", "danger")
            return redirect(url_for("recruitment.form"))
        if candidate.university_name not in valid_universities:
            flash("Pilih universitas dari daftar dropdown yang tersedia.", "danger")
            return redirect(url_for("recruitment.form"))
        try:
            candidate.availability_slots = _candidate_availability_slots_from_form(
                request.form
            )
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("recruitment.form"))
        password = request.form.get("password") or ""
        password_confirm = request.form.get("password_confirm") or ""
        if (
            not is_bypass_profile
            and (not candidate.password_hash or password or password_confirm)
        ) or (is_bypass_profile and (password or password_confirm)):
            if len(password) < 8:
                flash("Password dashboard minimal 8 karakter.", "danger")
                return redirect(url_for("recruitment.form"))
            if password != password_confirm:
                flash("Konfirmasi password dashboard tidak sama.", "danger")
                return redirect(url_for("recruitment.form"))
            candidate.set_password(password)
        try:
            cv_path = _save_candidate_upload(
                request.files.get("cv_file"), candidate, "cv", {"pdf", "doc", "docx"}
            )
            photo_path = _save_candidate_upload(
                request.files.get("photo_file"), candidate, "photos", {"png", "jpg", "jpeg", "webp"}
            )
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("recruitment.form"))
        if cv_path:
            candidate.cv_file_path = cv_path
        if photo_path:
            candidate.photo_file_path = photo_path
        if not candidate.cv_file_path or not candidate.photo_file_path:
            flash("CV dan foto wajib diunggah.", "danger")
            return redirect(url_for("recruitment.form"))
        bypass_tutor = _bypass_tutor_for_candidate(candidate)
        if bypass_tutor:
            _sync_bypass_profile_to_tutor(candidate, bypass_tutor)
            if candidate.status != "signed":
                candidate.status = "contract_sent"
                candidate.contract_text = _build_contract_text(candidate)
                candidate.offering_text = _build_offering_text(candidate)
                candidate.contract_sent_at = candidate.contract_sent_at or datetime.utcnow()
            candidate.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Profile pelamar berhasil dikirim. Offering dan kontrak sudah dibuat.", "success")
            return redirect(url_for("recruitment.dashboard"))

        candidate.status = "submitted"
        candidate.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Data recruitment berhasil dikirim.", "success")
        return redirect(url_for("recruitment.dashboard"))
    file_flags = _candidate_file_flags(candidate)
    form_title = "Profile Pelamar" if is_bypass_profile else (
        "Edit Data Recruitment" if request.args.get("edit") == "1" else "Form Recruitment Tutor"
    )
    submit_label = "Kirim Profile" if is_bypass_profile else (
        "Simpan Perubahan" if request.args.get("edit") == "1" else "Kirim Data Recruitment"
    )
    return render_template(
        "recruitment/form.html",
        candidate=candidate,
        is_edit=request.args.get("edit") == "1",
        is_bypass_profile=is_bypass_profile,
        form_title=form_title,
        submit_label=submit_label,
        cv_file_exists=file_flags["cv_exists"],
        photo_file_exists=file_flags["photo_exists"],
        gender_options=GENDER_OPTIONS,
        last_education_levels=LAST_EDUCATION_LEVELS,
        teaching_options=_teaching_option_choices(),
        university_options=UNIVERSITY_OPTIONS,
        availability_grid=_build_candidate_availability_rows(candidate),
    )


@recruitment_bp.route("/selesai")
def thank_you():
    if _current_candidate():
        return redirect(url_for("recruitment.dashboard"))
    return render_template("recruitment/thank_you.html")


@recruitment_bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    candidate = _current_candidate()
    if not candidate:
        flash("Masuk ke dashboard recruitment terlebih dahulu.", "warning")
        return redirect(url_for("recruitment.start"))
    if candidate.contract_text is None and candidate.status in {"contract_sent", "signed"}:
        candidate.contract_text = _build_contract_text(candidate)
    if candidate.offering_text is None and candidate.status in {"contract_sent", "signed"}:
        candidate.offering_text = _build_offering_text(candidate)
    if request.method == "POST":
        signature = request.form.get("signature_data_url") or ""
        _sign_candidate_contract(candidate, signature)
        return redirect(url_for("recruitment.dashboard"))
    return render_template(
        "recruitment/dashboard.html",
        candidate=candidate,
        status_label=RECRUITMENT_STATUSES.get(candidate.status, candidate.status),
        status_labels=RECRUITMENT_STATUSES,
        applications=_candidate_applications(candidate),
        application_kind=_application_kind,
        candidate_files=_candidate_file_flags(candidate),
        availability_grid=_build_candidate_availability_rows(candidate),
    )


@recruitment_bp.route("/dashboard/lamaran-baru", methods=["POST"])
def new_application():
    current = _current_candidate()
    if not current:
        flash("Masuk ke dashboard recruitment terlebih dahulu.", "warning")
        return redirect(url_for("recruitment.start"))
    candidate = RecruitmentCandidate(
        google_email=current.google_email,
        email_verified=True,
    )
    db.session.add(candidate)
    db.session.flush()
    tutor = _tutor_for_email(candidate.google_email)
    if tutor:
        _sync_candidate_from_tutor(candidate, tutor)
    db.session.commit()
    session["recruitment_candidate_id"] = candidate.id
    flash("Lamaran baru dibuat. Silakan lengkapi atau perbarui data.", "success")
    return redirect(url_for("recruitment.form", edit=1))


@recruitment_bp.route("/dashboard/lamaran/<candidate_ref>/buka", methods=["POST"])
def open_application(candidate_ref):
    current = _current_candidate()
    if not current:
        flash("Masuk ke dashboard recruitment terlebih dahulu.", "warning")
        return redirect(url_for("recruitment.start"))
    candidate = _candidate_from_ref(candidate_ref)
    if _normalize_email(candidate.google_email) != _normalize_email(current.google_email):
        abort(404)
    session["recruitment_candidate_id"] = candidate.id
    return redirect(url_for("recruitment.dashboard"))


@recruitment_bp.route("/dashboard/file/<kind>")
def dashboard_file(kind):
    candidate = _current_candidate()
    if not candidate:
        flash("Masuk ke dashboard recruitment terlebih dahulu.", "warning")
        return redirect(url_for("recruitment.start"))
    file_map = {
        "cv": candidate.cv_file_path,
        "photo": candidate.photo_file_path,
    }
    relative_path = file_map.get(kind)
    if not relative_path:
        abort(404)
    root = os.path.abspath(current_app.config["UPLOAD_FOLDER"])
    target = os.path.abspath(os.path.join(root, relative_path))
    if not target.startswith(root + os.sep) or not os.path.isfile(target):
        abort(404)
    return send_from_directory(root, relative_path)


@recruitment_bp.route("/dashboard/document/<kind>")
def dashboard_document(kind):
    candidate = _current_candidate()
    if not candidate:
        flash("Masuk ke dashboard recruitment terlebih dahulu.", "warning")
        return redirect(url_for("recruitment.start"))
    if candidate.status not in {"contract_sent", "signed"}:
        abort(404)
    if kind == "offering":
        if not candidate.offering_text:
            candidate.offering_text = _build_offering_text(candidate)
            db.session.commit()
        return _dashboard_document_response("Offering", candidate.offering_text)
    if kind == "contract":
        if not candidate.contract_text:
            candidate.contract_text = _build_contract_text(candidate)
            db.session.commit()
        return _dashboard_document_response(
            "Surat Kerja / Kontrak",
            candidate.contract_text,
        )
    abort(404)


@recruitment_bp.route("/dashboard/tutor")
def enter_tutor_dashboard():
    candidate = _current_candidate()
    if not candidate or not candidate.tutor_id or candidate.status != "signed":
        abort(404)
    tutor = db.session.get(Tutor, candidate.tutor_id)
    if not tutor or not tutor.is_active:
        abort(404)
    _ensure_tutor_portal_credentials(tutor)
    session["tutor_portal_tutor_id"] = tutor.id
    session.pop("tutor_portal_admin_tutor_id", None)
    db.session.commit()
    return redirect(url_for("tutor_portal.dashboard"))


@recruitment_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("recruitment_candidate_id", None)
    flash("Anda sudah keluar dari dashboard recruitment.", "success")
    return redirect(url_for("recruitment.start"))


@recruitment_bp.route("/files/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@recruitment_bp.route("/crm/candidates")
@login_required
def crm_candidates():
    candidates = (
        RecruitmentCandidate.query.filter_by(status="submitted")
        .order_by(RecruitmentCandidate.created_at.desc(), RecruitmentCandidate.id.desc())
        .all()
    )
    return render_template(
        "recruitment/crm_candidates.html",
        candidates=candidates,
        title="Kandidat Pelamar",
    )


@recruitment_bp.route("/crm/selected")
@login_required
def crm_selected():
    candidates = (
        RecruitmentCandidate.query.filter_by(status="selected")
        .order_by(RecruitmentCandidate.updated_at.desc(), RecruitmentCandidate.id.desc())
        .all()
    )
    return render_template("recruitment/crm_selected.html", candidates=candidates)


@recruitment_bp.route("/crm/interview")
@login_required
def crm_interview():
    candidates = (
        RecruitmentCandidate.query.filter(
            RecruitmentCandidate.status.in_(["interview", "contract_sent", "signed"])
        )
        .order_by(RecruitmentCandidate.updated_at.desc(), RecruitmentCandidate.id.desc())
        .all()
    )
    return render_template("recruitment/crm_interview.html", candidates=candidates)


@recruitment_bp.route("/crm/candidates/<candidate_ref>/shortlist", methods=["POST"])
@login_required
def shortlist(candidate_ref):
    candidate = _candidate_from_ref(candidate_ref)
    if candidate.status != "submitted":
        flash("Hanya kandidat pelamar baru yang bisa diloloskan berkas.", "warning")
        return redirect(url_for("recruitment.crm_candidates"))
    candidate.status = "selected"
    candidate.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"{candidate.name} masuk ke Pelamar Terpilih.", "success")
    return redirect(url_for("recruitment.crm_candidates"))


@recruitment_bp.route("/crm/selected/<candidate_ref>/invite", methods=["POST"])
@login_required
def send_interview_invite(candidate_ref):
    candidate = _candidate_from_ref(candidate_ref)
    if candidate.status != "selected":
        flash("Undangan interview hanya bisa dikirim dari tahap Pelamar Terpilih.", "warning")
        return redirect(url_for("recruitment.crm_selected"))
    meet_link = (request.form.get("meet_link") or "").strip()
    if not meet_link:
        flash("Link Meet wajib diisi.", "danger")
        return redirect(url_for("recruitment.crm_selected"))
    candidate.meet_link = meet_link
    candidate.invited_at = datetime.utcnow()
    candidate.updated_at = datetime.utcnow()
    session_status = _get_whatsapp_session_status()
    if not session_status["ready"]:
        db.session.commit()
        flash("Link Meet tersimpan, tetapi WhatsApp bot belum ready.", "warning")
        return redirect(url_for("recruitment.crm_selected"))
    message = (
        f"Halo {candidate.name}, Anda lolos seleksi berkas LBB Super Smart.\n\n"
        f"Undangan interview:\n{meet_link}\n\n"
        "Mohon konfirmasi kehadiran Anda."
    )
    ok, error_message = _send_candidate_whatsapp(candidate, message)
    db.session.commit()
    flash(
        "Undangan interview terkirim ke WhatsApp."
        if ok
        else f"WA gagal: {error_message}",
        "success" if ok else "warning",
    )
    return redirect(url_for("recruitment.crm_selected"))


@recruitment_bp.route("/crm/selected/<candidate_ref>/agree", methods=["POST"])
@login_required
def agree_interview(candidate_ref):
    candidate = _candidate_from_ref(candidate_ref)
    if candidate.status != "selected":
        flash("Hanya pelamar terpilih yang bisa dipindahkan ke tahap interview.", "warning")
        return redirect(url_for("recruitment.crm_selected"))
    candidate.status = "interview"
    candidate.interview_agreed_at = datetime.utcnow()
    candidate.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"{candidate.name} dipindahkan ke halaman Interview.", "success")
    return redirect(url_for("recruitment.crm_selected"))


@recruitment_bp.route("/crm/interview/<candidate_ref>/send-contract", methods=["POST"])
@login_required
def send_contract(candidate_ref):
    candidate = _candidate_from_ref(candidate_ref)
    if candidate.status not in {"interview", "contract_sent"}:
        flash("Kontrak hanya bisa dikirim dari tahap interview.", "warning")
        return redirect(url_for("recruitment.crm_interview"))
    candidate.contract_text = _build_contract_text(candidate)
    candidate.offering_text = _build_offering_text(candidate)
    candidate.status = "contract_sent"
    candidate.contract_sent_at = datetime.utcnow()
    candidate.updated_at = datetime.utcnow()
    contract_url = _contract_url(candidate, external=True)
    message = (
        f"Halo {candidate.name}, berikut kontrak dan offering digital LBB Super Smart:\n"
        f"{contract_url}\n\nSilakan baca dan tanda tangani langsung di web."
    )
    session_status = _get_whatsapp_session_status()
    if session_status["ready"]:
        ok, error_message = _send_candidate_whatsapp(candidate, message)
    else:
        ok, error_message = False, "WhatsApp bot belum ready"
    db.session.commit()
    flash(
        "Kontrak dan offering terkirim ke WhatsApp."
        if ok
        else f"Kontrak dibuat, WA gagal: {error_message}",
        "success" if ok else "warning",
    )
    return redirect(url_for("recruitment.crm_interview"))


@recruitment_bp.route("/contract/<token>", methods=["GET", "POST"])
def contract(token):
    candidate = _candidate_from_contract_token(token)
    if not candidate:
        return redirect(url_for("recruitment.start"))
    session["recruitment_candidate_id"] = candidate.id
    if not candidate.contract_text:
        candidate.contract_text = _build_contract_text(candidate)
    if not candidate.offering_text:
        candidate.offering_text = _build_offering_text(candidate)
    if request.method == "POST":
        signature = request.form.get("signature_data_url") or ""
        _sign_candidate_contract(candidate, signature)
    else:
        db.session.commit()
    return redirect(url_for("recruitment.dashboard"))
