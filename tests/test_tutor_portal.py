from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_tutor_portal_routes_and_templates_are_registered_in_source():
    init_text = (PROJECT_ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    routes_init = (PROJECT_ROOT / "app" / "routes" / "__init__.py").read_text(
        encoding="utf-8"
    )
    route_text = (PROJECT_ROOT / "app" / "routes" / "tutor_portal.py").read_text(
        encoding="utf-8"
    )
    model_text = (PROJECT_ROOT / "app" / "models" / "master.py").read_text(
        encoding="utf-8"
    )
    dashboard_text = (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "dashboard.html"
    ).read_text(encoding="utf-8")

    assert "tutor_portal_bp" in routes_init
    assert "app.register_blueprint(tutor_portal_bp)" in init_text
    assert "URLSafeTimedSerializer" in route_text
    assert "portal_username" in model_text
    assert "set_portal_password" in model_text
    assert "login_method == \"email\"" in route_text
    assert "check_portal_password" in route_text
    assert "portal_must_change_password" in route_text
    assert "def _tutor_onboarding_step" in route_text
    assert "if step == \"password\"" in route_text
    assert "Password berhasil diganti" in route_text
    assert "tutor.email = email" in route_text
    assert "Gmail tutor sudah disimpan" in route_text
    assert "verify_email" in route_text
    assert "email.endswith(\"@gmail.com\")" in route_text
    assert "TUTOR_PORTAL_MIN_DATE" in route_text
    assert "AttendanceSession.session_date >= min_date" in route_text
    assert "TutorPortalRequest" in route_text
    assert "request_schedule_change" in route_text
    assert "request_availability" in route_text
    assert "request_profile_update" in route_text
    assert "admin_credentials" in route_text
    assert "admin_send_credential_whatsapp" in route_text
    assert "\"/messages/send\"" in route_text
    assert "Cara login pertama" in route_text
    assert "Fungsi dashboard tutor" in route_text
    assert "_normalize_whatsapp_phone" in route_text
    assert "Approval Dashboard Tutor" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_requests.html"
    ).read_text(encoding="utf-8")
    assert "Credential Tutor" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Kirim WA" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "admin_credentials.html"
    ).read_text(encoding="utf-8")
    assert "Aktivasi Akun Tutor" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "onboarding.html"
    ).read_text(encoding="utf-8")
    assert "Ganti Password" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "onboarding.html"
    ).read_text(encoding="utf-8")
    assert "Simpan Gmail dan Kirim Verifikasi" in (
        PROJECT_ROOT / "app" / "templates" / "tutor_portal" / "onboarding.html"
    ).read_text(encoding="utf-8")
    assert "Presensi Tutor" in dashboard_text
    assert "Slip Gaji" in dashboard_text
    assert "Ajukan Jadwal Merah/Hijau" in dashboard_text


def test_tutor_portal_docker_service_and_mail_config_exist():
    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_path = PROJECT_ROOT / ".env.example"
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    entrypoint_text = (PROJECT_ROOT / "docker" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )

    assert "tutor_web:" in compose_text
    assert "${TUTOR_PORTAL_PORT:-6003}:5000" in compose_text
    assert "TUTOR_PORTAL_BASE_URL" in compose_text
    assert "MAIL_SERVER" in compose_text
    if env_text:
        assert "TUTOR_PORTAL_PORT=6003" in env_text
        assert "tutor.supersmart.click" in env_text
    assert "CREATE TABLE IF NOT EXISTS tutor_portal_requests" in entrypoint_text
    assert "profile_photo_path" in entrypoint_text
    assert "cv_file_path" in entrypoint_text
    assert "portal_username" in entrypoint_text
    assert "portal_password_hash" in entrypoint_text
    assert "portal_must_change_password" in entrypoint_text
    assert "portal_email_verified" in entrypoint_text
