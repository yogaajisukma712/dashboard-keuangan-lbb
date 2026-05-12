from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
    assert "CREATE TABLE IF NOT EXISTS recruitment_candidates" in entrypoint_text
    assert "@recruitment_bp.route(\"/\", methods=[\"GET\", \"POST\"])" in route_text
    assert "def verify_email" in route_text
    assert "def crm_candidates" in route_text
    assert "def crm_selected" in route_text
    assert "def crm_interview" in route_text
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
    assert "RECRUITMENT_BASE_URL" in config_text
    assert "RECRUITMENT_HOST" in config_text
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
    candidates_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_candidates.html"
    ).read_text(encoding="utf-8")
    selected_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_selected.html"
    ).read_text(encoding="utf-8")
    interview_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "crm_interview.html"
    ).read_text(encoding="utf-8")
    contract_text = (
        PROJECT_ROOT / "app" / "templates" / "recruitment" / "contract.html"
    ).read_text(encoding="utf-8")
    dashboard_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "dashboard.html"
    ).read_text(encoding="utf-8")
    base_text = (PROJECT_ROOT / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "Login dengan Google" in start_text
    assert "Upload CV" in form_text
    assert "Upload Foto" in form_text
    assert "Mapel, Jenjang, dan Kurikulum" in form_text
    assert "teaching-option-input" in form_text
    assert "teaching-option-list" in form_text
    assert "selected-teaching-options" in form_text
    assert 'id="recruitment-data-form"' in form_text
    assert 'name="address" rows="2" required' in form_text
    assert "Pilih minimal satu mapel." in form_text
    assert "Pendidikan Terakhir" in form_text
    assert "university-options" in form_text
    assert "Jenis Kelamin" in form_text
    assert "Verifikasi email Google/Gmail terlebih dahulu" in form_text
    assert "Buka CV" in candidates_text
    assert "candidate.teaching_preferences" in candidates_text
    assert "candidate.university_name" in candidates_text
    assert "Lolos Berkas" in candidates_text
    assert "Pelamar Terpilih" in selected_text
    assert "Link Google Meet" in selected_text
    assert "Setuju Interview" in selected_text
    assert "Kirim Kontrak & Offering" in interview_text
    assert "signature_data_url" in contract_text
    assert "Tandatangani & Masuk Dashboard Tutor" in contract_text
    assert "Kontrak & Offering" in dashboard_text
    assert "CRM Recruitment" in base_text
