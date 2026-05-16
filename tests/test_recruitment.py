from pathlib import Path
from types import SimpleNamespace

from flask import get_flashed_messages

from app import create_app
from app.routes import recruitment


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _make_app():
    app = create_app("testing")
    app.config.update(
        SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
    )
    return app


def _valid_form_payload(**overrides):
    payload = {
        "name": "Candidate",
        "phone": "08123456789",
        "address": "Surabaya",
        "age": "25",
        "gender": "female",
        "last_education_level": "S1",
        "university_name": "Universitas Airlangga",
        "teaching_preferences": ["Matematika SD Nasional"],
        "availability_0_16": "available",
    }
    payload.update(overrides)
    return payload


def _candidate():
    return SimpleNamespace(
        google_email="candidate@gmail.com",
        email_verified=True,
        password_hash=None,
        status="draft",
        tutor_id=None,
        name="",
        phone="",
        address="",
        gender="",
        last_education_level="",
        university_name="",
        age=None,
        teaching_preferences=[],
        availability_slots=[],
        availability_json=None,
        cv_file_path=None,
        photo_file_path=None,
        contract_text=None,
        offering_text=None,
        contract_sent_at=None,
        signed_at=None,
        signature_data_url=None,
    )


def test_recruitment_form_redirects_existing_candidate_to_dashboard(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    candidate.status = "submitted"
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(recruitment, "_tutor_for_email", lambda email: None)

    with app.test_request_context(
        "/recruitment/form",
        method="GET",
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

    assert response.status_code == 302
    assert response.location.endswith("/recruitment/dashboard")


def test_recruitment_form_allows_dashboard_edit_mode(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    candidate.status = "submitted"
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(recruitment, "_tutor_for_email", lambda email: None)
    monkeypatch.setattr(recruitment, "_teaching_option_choices", lambda: [])
    monkeypatch.setattr(
        recruitment,
        "_build_candidate_availability_rows",
        lambda candidate: {"summary": {"available_count": 0, "unavailable_count": 0}},
    )
    monkeypatch.setattr(recruitment, "render_template", lambda *args, **kwargs: "FORM")

    with app.test_request_context(
        "/recruitment/form?edit=1",
        method="GET",
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

    assert response == "FORM"


def test_bypass_tutor_sees_profile_form(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    tutor = SimpleNamespace(id=7, name="Tutor Bypass")
    captured = {}
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(recruitment, "_tutor_for_email", lambda email: tutor)
    monkeypatch.setattr(
        recruitment,
        "_sync_candidate_from_tutor",
        lambda c, t: setattr(c, "tutor_id", t.id),
    )
    monkeypatch.setattr(recruitment, "_teaching_option_choices", lambda: [])
    monkeypatch.setattr(
        recruitment,
        "_build_candidate_availability_rows",
        lambda candidate: {"rows": [], "weekday_names": []},
    )

    def fake_render_template(template, **kwargs):
        captured.update(kwargs)
        return "FORM"

    monkeypatch.setattr(recruitment, "render_template", fake_render_template)

    with app.test_request_context(
        "/recruitment/form",
        method="GET",
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

    assert response == "FORM"
    assert captured["is_bypass_profile"] is True
    assert captured["form_title"] == "Profile Pelamar"
    assert captured["submit_label"] == "Kirim Profile"


def test_bypass_tutor_profile_submit_generates_contract(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    candidate.name = "Tutor Bypass"
    candidate.phone = "08123456789"
    candidate.address = "Surabaya"
    candidate.age = 25
    candidate.gender = "female"
    candidate.last_education_level = "S1"
    candidate.university_name = "Universitas Airlangga"
    candidate.cv_file_path = "existing/cv.pdf"
    candidate.photo_file_path = "existing/photo.jpg"
    candidate.tutor_id = 7
    candidate.plain_password = None
    candidate.set_password = lambda password: setattr(candidate, "plain_password", password)
    candidate.check_password = lambda password: candidate.plain_password == password
    tutor = SimpleNamespace(
        id=7,
        name="Tutor Bypass",
        phone=None,
        email="candidate@gmail.com",
        address=None,
        profile_photo_path=None,
        cv_file_path=None,
        status="active",
        is_active=True,
        portal_email_verified=True,
        portal_email_verified_at=None,
        portal_must_change_password=True,
        portal_password=None,
        updated_at=None,
    )
    tutor.set_portal_password = lambda password: setattr(tutor, "portal_password", password)
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(recruitment, "_tutor_for_email", lambda email: tutor)
    monkeypatch.setattr(recruitment, "_bypass_tutor_for_candidate", lambda candidate: tutor)
    monkeypatch.setattr(recruitment, "_build_offering_text", lambda candidate: "OFFERING")
    monkeypatch.setattr(recruitment.db.session, "commit", lambda: None)
    monkeypatch.setattr(
        recruitment, "_teaching_option_choices", lambda: ["Matematika SD Nasional"]
    )
    monkeypatch.setattr(
        recruitment,
        "_candidate_availability_slots_from_form",
        lambda form: [{"day": 0, "hour": 16}],
    )
    monkeypatch.setattr(recruitment, "_save_candidate_upload", lambda *args: None)

    with app.test_request_context(
        "/recruitment/form",
        method="POST",
        data=_valid_form_payload(
            password="password123",
            password_confirm="password123",
        ),
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

    assert response.status_code == 302
    assert response.location.endswith("/recruitment/dashboard")
    assert candidate.status == "contract_sent"
    assert candidate.contract_text
    assert candidate.offering_text
    assert candidate.contract_sent_at
    assert candidate.tutor_id == tutor.id
    assert candidate.check_password("password123")
    assert tutor.portal_password == "password123"
    assert tutor.portal_must_change_password is False


def test_dashboard_document_response_renders_html_document():
    app = _make_app()

    with app.app_context():
        response = recruitment._dashboard_document_response(
            "Surat Kerja / Kontrak",
            '<section class="recruitment-a4-page"><h1>KONTRAK KERJA</h1></section>',
        )

    html = response.get_data(as_text=True)
    assert '<section class="recruitment-a4-page">' in html
    assert "&lt;section" not in html
    assert "<pre>" not in html


def test_default_offering_uses_left_ceo_qr_without_verify_text():
    assert "doc-ceo-qr" in recruitment.DEFAULT_OFFERING_TEMPLATE
    assert "Tanda tangan CEO" in recruitment.DEFAULT_OFFERING_TEMPLATE
    assert "Scan untuk verifikasi dokumen ini." not in recruitment.DEFAULT_OFFERING_TEMPLATE


def test_default_contract_omits_verify_text_below_qr():
    assert "QR validasi dokumen" in recruitment.DEFAULT_CONTRACT_TEMPLATE
    assert "Scan untuk verifikasi dokumen ini." not in recruitment.DEFAULT_CONTRACT_TEMPLATE


def test_recruitment_form_rejects_unlisted_university(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(
        recruitment, "_teaching_option_choices", lambda: ["Matematika SD Nasional"]
    )

    with app.test_request_context(
        "/recruitment/form",
        method="POST",
        data=_valid_form_payload(university_name="Universitas Buatan Sendiri"),
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

        assert response.status_code == 302
        assert "Pilih universitas dari daftar dropdown yang tersedia." in [
            message for _, message in get_flashed_messages(with_categories=True)
        ]


def test_recruitment_form_rejects_unlisted_teaching_preference(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(
        recruitment, "_teaching_option_choices", lambda: ["Matematika SD Nasional"]
    )

    with app.test_request_context(
        "/recruitment/form",
        method="POST",
        data=_valid_form_payload(teaching_preferences=["Mapel Buatan"]),
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

        assert response.status_code == 302
        assert "Pilih mapel dari daftar dropdown yang tersedia." in [
            message for _, message in get_flashed_messages(with_categories=True)
        ]


def test_recruitment_form_requires_dashboard_password_confirmation(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(
        recruitment, "_teaching_option_choices", lambda: ["Matematika SD Nasional"]
    )

    with app.test_request_context(
        "/recruitment/form",
        method="POST",
        data=_valid_form_payload(password="password123", password_confirm="beda"),
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

        assert response.status_code == 302
        assert "Konfirmasi password dashboard tidak sama." in [
            message for _, message in get_flashed_messages(with_categories=True)
        ]


def test_recruitment_form_requires_available_schedule_slot(monkeypatch):
    app = _make_app()
    candidate = _candidate()
    monkeypatch.setattr(recruitment, "_current_candidate", lambda: candidate)
    monkeypatch.setattr(
        recruitment, "_teaching_option_choices", lambda: ["Matematika SD Nasional"]
    )

    with app.test_request_context(
        "/recruitment/form",
        method="POST",
        data=_valid_form_payload(
            password="password123",
            password_confirm="password123",
            availability_0_16="unavailable",
        ),
        headers={"Host": "recruitment.supersmart.click"},
    ):
        response = recruitment.form()

        assert response.status_code == 302
        assert "Pilih minimal satu waktu luang berwarna hijau." in [
            message for _, message in get_flashed_messages(with_categories=True)
        ]


def test_recruitment_availability_defaults_to_unavailable():
    grid = recruitment._build_candidate_availability_rows(_candidate())

    states = [cell["state"] for row in grid["rows"] for cell in row["cells"]]
    labels = [cell["label"] for row in grid["rows"] for cell in row["cells"]]

    assert set(states) == {"unavailable"}
    assert set(labels) == {"Tidak Bisa"}
    assert grid["summary"]["available_count"] == 0
    assert grid["summary"]["unavailable_count"] == len(states)


def test_recruitment_crm_source_is_registered():
    app_text = (PROJECT_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    routes_text = (PROJECT_ROOT / "app" / "routes" / "__init__.py").read_text(
        encoding="utf-8"
    )
    models_text = (PROJECT_ROOT / "app" / "models" / "__init__.py").read_text(
        encoding="utf-8"
    )
    route_text = (PROJECT_ROOT / "app" / "routes" / "recruitment.py").read_text(
        encoding="utf-8"
    )
    model_text = (PROJECT_ROOT / "app" / "models" / "recruitment.py").read_text(
        encoding="utf-8"
    )
    entrypoint_text = (PROJECT_ROOT / "docker" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )
    config_text = (PROJECT_ROOT / "config.py").read_text(encoding="utf-8")
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "recruitment_bp" in routes_text
    assert "app.register_blueprint(recruitment_bp)" in app_text
    assert "RecruitmentCandidate" in models_text
    assert "__tablename__ = \"recruitment_candidates\"" in model_text
    assert "password_hash = db.Column(db.String(255))" in model_text
    assert "availability_json = db.Column(db.Text)" in model_text
    assert "def availability_slots" in model_text
    assert "def set_password" in model_text
    assert "def check_password" in model_text
    assert "CREATE TABLE IF NOT EXISTS recruitment_candidates" in entrypoint_text
    assert "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS password_hash" in entrypoint_text
    assert "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS availability_json" in entrypoint_text
    assert "@recruitment_bp.route(\"/\", methods=[\"GET\", \"POST\"])" in route_text
    assert "def verify_email" in route_text
    assert "@recruitment_bp.route(\"/dashboard\", methods=[\"GET\", \"POST\"])" in route_text
    assert "@recruitment_bp.route(\"/logout\", methods=[\"GET\", \"POST\"])" in route_text
    assert "_clear_portal_sessions()" in route_text
    assert "candidate.set_password(password)" in route_text
    assert "_build_candidate_availability_rows" in route_text
    assert "_candidate_availability_slots_from_form" in route_text
    assert "candidate.availability_slots" in route_text
    assert "recruitment.dashboard" in route_text
    assert '@recruitment_bp.route("/daftar", methods=["GET", "POST"])' in route_text
    assert "def register" in route_text
    assert '@recruitment_bp.route("/google/login", methods=["GET"])' in route_text
    assert '@recruitment_bp.route("/google/callback", methods=["GET"])' in route_text
    assert "_fetch_google_userinfo" in route_text
    assert "RecruitmentCandidate(google_email=email)" in route_text
    assert "return redirect(url_for(\"recruitment.form\"))" in route_text
    assert "Akun recruitment belum ditemukan" not in route_text
    assert "def crm_candidates" in route_text
    assert "def crm_selected" in route_text
    assert "def crm_interview" in route_text
    assert "def crm_rejected" in route_text
    assert "def crm_templates" in route_text
    assert "def reject_candidate" in route_text
    assert "def delete_candidate" in route_text
    assert "candidate.status = \"rejected\"" in route_text
    assert "db.session.delete(candidate)" in route_text
    assert "_read_recruitment_template" in route_text
    assert "_write_recruitment_template" in route_text
    assert "DEFAULT_CONTRACT_TEMPLATE" in route_text
    assert "DEFAULT_OFFERING_TEMPLATE" in route_text
    assert "KONTRAK KERJA" in route_text
    assert "FREELANCE PENGAJAR PRIVATE" in route_text
    assert "Surat Penawaran Kerja Pengajar Privat Online" in route_text
    assert "Penawaran Gaji" in route_text
    assert "company_qr_data_url" in route_text
    assert "document_date_text" in route_text
    assert "def send_interview_invite" in route_text
    assert "def send_contract" in route_text
    assert "def contract" in route_text
    assert "CONTRACT_TOKEN_MAX_AGE_SECONDS" in route_text
    assert "_candidate_from_contract_token" in route_text
    assert "RECRUITMENT_BASE_URL" in route_text
    assert "LAST_EDUCATION_LEVELS" in route_text
    assert "GENDER_OPTIONS" in route_text
    assert "UNIVERSITY_OPTIONS = list(dict.fromkeys([" in route_text
    assert "Universitas Terbuka" in route_text
    assert "Politeknik Negeri Bandung" in route_text
    assert "UIN Syarif Hidayatullah Jakarta" in route_text
    assert "Pilih universitas dari daftar dropdown yang tersedia." in route_text
    assert "_teaching_option_choices" in route_text
    assert "teaching_preferences = request.form.getlist" in route_text
    assert "Pilih mapel dari daftar dropdown yang tersedia." in route_text
    assert "Cambridge" in route_text
    assert "not candidate.name or not candidate.phone or not candidate.address" in route_text
    assert "CV dan foto wajib diunggah." in route_text
    assert "candidate.status != \"contract_sent\"" in route_text
    assert "not candidate.email_verified" in route_text
    assert "_create_tutor_from_candidate" in route_text
    assert "session[\"tutor_portal_tutor_id\"] = tutor.id" in route_text
    assert "TUTOR_PORTAL_BASE_URL" in route_text
    assert "def _tutor_portal_url" in route_text
    assert "def _activate_tutor_session_from_candidate" in route_text
    assert "_ensure_tutor_portal_credentials(tutor)" in route_text
    assert "tutor.portal_password_hash = candidate.password_hash" in route_text
    assert "tutor.portal_must_change_password = False" in route_text
    assert '@recruitment_bp.route("/dashboard/tutor")' in route_text
    assert "def enter_tutor_dashboard" in route_text
    assert "return redirect(url_for(\"tutor_portal.dashboard\"))" in route_text
    assert "def _is_bypass_tutor_candidate" in route_text
    assert "Profile Pelamar" in route_text
    assert "Kirim Profile" in route_text
    assert "RECRUITMENT_BASE_URL" in config_text
    assert "RECRUITMENT_HOST" in config_text
    assert "SESSION_COOKIE_DOMAIN" in config_text
    assert "GOOGLE_OAUTH_CLIENT_ID" in config_text
    assert "GOOGLE_OAUTH_CLIENT_SECRET" in config_text
    assert "teaching_preferences_json" in model_text
    assert "last_education_level" in model_text
    assert "university_name" in model_text
    assert "age = db.Column(db.Integer)" in model_text
    assert "gender = db.Column" in model_text
    assert (
        "ALTER TABLE recruitment_candidates ADD COLUMN IF NOT EXISTS teaching_preferences_json"
        in entrypoint_text
    )
    assert "recruitment_web:" in compose_text
    assert "billing_supersmart_recruitment_web" in compose_text
    assert "${RECRUITMENT_PORT:-6006}:5000" in compose_text
    assert "MAIL_SERVER" in compose_text
    assert "MAIL_DEFAULT_SENDER" in compose_text
    assert "SESSION_COOKIE_DOMAIN: ${SESSION_COOKIE_DOMAIN:-}" in compose_text
    assert "GOOGLE_OAUTH_CLIENT_ID: ${GOOGLE_OAUTH_CLIENT_ID:-}" in compose_text
    assert "GOOGLE_OAUTH_CLIENT_SECRET: ${GOOGLE_OAUTH_CLIENT_SECRET:-}" in compose_text
    assert (
        "RECRUITMENT_BASE_URL: ${RECRUITMENT_BASE_URL:-https://recruitment.supersmart.click}"
        in compose_text
    )


def test_recruitment_templates_expose_required_workflow():
    start_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "start.html"
    ).read_text(encoding="utf-8")
    form_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "form.html"
    ).read_text(encoding="utf-8")
    register_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "register.html"
    ).read_text(encoding="utf-8")
    candidates_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_candidates.html"
    ).read_text(encoding="utf-8")
    selected_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_selected.html"
    ).read_text(encoding="utf-8")
    interview_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_interview.html"
    ).read_text(encoding="utf-8")
    rejected_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_rejected.html"
    ).read_text(encoding="utf-8")
    templates_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_templates.html"
    ).read_text(encoding="utf-8")
    contract_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "contract.html"
    ).read_text(encoding="utf-8")
    recruitment_dashboard_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "dashboard.html"
    ).read_text(encoding="utf-8")
    dashboard_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "dashboard.html"
    ).read_text(encoding="utf-8")
    base_text = (PROJECT_ROOT / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "Recruitment HR Dashboard Login" in start_text
    assert "Mulai Recruitment" in start_text
    assert "HR Tech Recruitment Suite" in start_text
    assert "Candidate pipeline" in start_text
    assert "Masuk dengan Google" in start_text
    assert "recruitment.google_login" in start_text
    assert "Daftar baru menggunakan email" in start_text
    assert "Password dashboard diisi setelah Anda masuk ke form recruitment." in start_text
    assert "recruitment.register" in start_text
    assert "Mulai / Verifikasi Email" not in start_text
    assert "Daftar Akun Recruitment" in register_text
    assert "Mulai / Verifikasi Email" in register_text
    assert "Login Dashboard Recruitment" in register_text
    assert "recruitment.start" in register_text
    assert "Upload CV" in form_text
    assert "Upload Foto" in form_text
    assert "Password Dashboard Recruitment" in form_text
    assert "Password Pelamar / Dashboard Tutor" in form_text
    assert "Password ini dipakai juga untuk login Dashboard Tutor." in form_text
    assert "password_confirm" in form_text
    assert "Jadwal Waktu Luang" in form_text
    assert "Waktu luang" in form_text
    assert "Tidak bisa" in form_text
    assert "Klik kotak jadwal untuk mengganti warna hijau atau merah." in form_text
    assert "availability_grid.rows" in form_text
    assert "schedule-cell-button" in form_text
    assert "visually-hidden schedule-cell-label" in form_text
    assert "Mapel, Jenjang, dan Kurikulum" in form_text
    assert "Mapel boleh dipilih lebih dari satu." in form_text
    assert "klik Tambah, lalu ulangi untuk mapel berikutnya" in form_text
    assert "teaching-option-input" in form_text
    assert "teaching-option-list" in form_text
    assert "selected-teaching-options" in form_text
    assert "data-searchable-select" in form_text
    assert "searchable-select-search" in form_text
    assert "data-option-value" in form_text
    assert "optionValues" in form_text
    assert "<datalist" not in form_text
    assert " list=" not in form_text
    assert 'id="recruitment-data-form"' in form_text
    assert 'name="address" rows="2" required' in form_text
    assert "Pilih minimal satu mapel." in form_text
    assert "Pendidikan Terakhir" in form_text
    assert "university-options" in form_text
    assert "university-error" in form_text
    assert "Pilih universitas dari daftar." in form_text
    assert "Jenis Kelamin" in form_text
    assert "Verifikasi email Google/Gmail terlebih dahulu" in form_text
    assert "Buka CV" in candidates_text
    assert "candidate.teaching_preferences" in candidates_text
    assert "candidate.university_name" in candidates_text
    assert "Lolos Berkas" in candidates_text
    assert "recruitment.reject_candidate" in candidates_text
    assert "Tolak" in candidates_text
    assert "recruitment.delete_candidate" in candidates_text
    assert "Hapus" in candidates_text
    assert "Pelamar Tertolak" in candidates_text
    assert "Pelamar Terpilih" in selected_text
    assert "Link Google Meet" in selected_text
    assert "Setuju Interview" in selected_text
    assert "Pelamar Tertolak" in selected_text
    assert "Kirim Kontrak & Offering" in interview_text
    assert "Pelamar Tertolak" in interview_text
    assert "Pelamar Tertolak" in templates_text
    assert "Pelamar Tertolak" in rejected_text
    assert "recruitment.delete_candidate" in rejected_text
    assert "Template" in candidates_text
    assert "Template" in selected_text
    assert "Template" in interview_text
    assert "Editor Kontrak" in templates_text
    assert "Editor Offering" in templates_text
    assert "contract_template" in templates_text
    assert "offering_template" in templates_text
    assert "signature_data_url" in contract_text
    assert "Tandatangani & Masuk Dashboard Tutor" in contract_text
    assert "Dashboard Recruitment" in recruitment_dashboard_text
    assert "container-fluid" in recruitment_dashboard_text
    assert "Progress Lamaran" in recruitment_dashboard_text
    assert "recruitment.enter_tutor_dashboard" in recruitment_dashboard_text
    assert "url_for('tutor_portal.dashboard')" not in recruitment_dashboard_text
    assert "Lolos Berkas" in recruitment_dashboard_text
    assert "Interview" in recruitment_dashboard_text
    assert "Offering & Kontrak" in recruitment_dashboard_text
    assert "Data Diri" in recruitment_dashboard_text
    assert "Jadwal Waktu Luang" in recruitment_dashboard_text
    assert "availability_grid.rows" in recruitment_dashboard_text
    assert "availability-pill" in recruitment_dashboard_text
    assert "min-width: 620px" in recruitment_dashboard_text
    assert "Informasi Tahap Berikutnya" in recruitment_dashboard_text
    assert "signature_data_url" in recruitment_dashboard_text
    assert "Tandatangani" in recruitment_dashboard_text
    assert "Kontrak & Offering" in dashboard_text
    assert "CRM Recruitment" in base_text
