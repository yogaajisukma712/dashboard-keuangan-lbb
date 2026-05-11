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
    assert "candidate.status != \"contract_sent\"" in route_text
    assert "not candidate.email_verified" in route_text
    assert "_create_tutor_from_candidate" in route_text
    assert "session[\"tutor_portal_tutor_id\"] = tutor.id" in route_text


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
    assert "Verifikasi email Google/Gmail terlebih dahulu" in form_text
    assert "Buka CV" in candidates_text
    assert "Lolos Berkas" in candidates_text
    assert "Pelamar Terpilih" in selected_text
    assert "Link Google Meet" in selected_text
    assert "Setuju Interview" in selected_text
    assert "Kirim Kontrak & Offering" in interview_text
    assert "signature_data_url" in contract_text
    assert "Tandatangani & Masuk Dashboard Tutor" in contract_text
    assert "Kontrak & Offering" in dashboard_text
    assert "CRM Recruitment" in base_text
