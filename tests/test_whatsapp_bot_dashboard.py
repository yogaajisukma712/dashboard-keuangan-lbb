from pathlib import Path


def test_whatsapp_management_template_contains_qr_and_session_controls():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "whatsapp" / "management.html"
    ).read_text(encoding="utf-8")

    assert "Manajemen WhatsApp Bot" in template_text
    assert "btnInitializeSession" in template_text
    assert "btnLogoutSession" in template_text
    assert "sessionQrImage" in template_text
    assert "groupsTableBody" in template_text
    assert "contactsTableBody" in template_text
    assert "groupsPagination" in template_text
    assert "contactsPagination" in template_text
    assert "groupsPaginationSummary" in template_text
    assert "contactsPaginationSummary" in template_text
    assert "btnRefreshContacts" in template_text
    assert "groupsQuickSearch" in template_text
    assert "contactsQuickSearch" in template_text
    assert "groupsValidationFilter" in template_text
    assert "contactsValidationFilter" in template_text
    assert "btnValidateTutor" in template_text
    assert "btnValidateTutorManual" in template_text
    assert "btnValidateGroupStudent" in template_text
    assert "btnValidateGroupStudentManual" in template_text
    assert "btnScanAllGroupMessages" in template_text
    assert "syncProgressBar" in template_text
    assert "syncProgressPercentText" in template_text
    assert "syncProgressText" in template_text
    assert "syncProgressMeta" in template_text
    assert "manualTutorSelect" in template_text
    assert "manualStudentGroupSelect" in template_text
    assert "validateTutorSuggestion" in template_text
    assert "validateGroupStudentSuggestion" in template_text
    assert "scanAllGroupMessages" in template_text
    assert "renderSyncProgress" in template_text
    assert "filterByValidation" in template_text
    assert "normalizeSearchTerm" in template_text
    assert "itemMatchesQuickSearch" in template_text
    assert "startScanPolling" in template_text
    assert "stopScanPolling" in template_text
    assert "excludedGroupNames" in template_text
    assert "Pilih tutor manual" in template_text
    assert "Pilih siswa manual" in template_text
    assert "Saran Siswa" in template_text
    assert "Pesan DB" in template_text
    assert "renderPaginationControls" in template_text
    assert "btnPaginationPage" in template_text
    assert "Data group dibaca dari database" in template_text
    assert "Data kontak dibaca dari database" in template_text
    assert "Sudah divalidasi" in template_text
    assert "Belum divalidasi" in template_text
    assert "Cari nama atau ID group..." in template_text
    assert "Cari nama, nomor, atau group..." in template_text
    assert "Tidak ada group yang cocok dengan pencarian cepat." in template_text
    assert "Tidak ada kontak yang cocok dengan pencarian cepat." in template_text
    assert "Scan " in template_text
    assert "QR biasanya muncul dalam 20-30 detik" in template_text
    assert "Tidak ada duplikat untuk pesan yang sama" in template_text
    assert "Pesan yang sama di-update, bukan digandakan" in template_text
    assert "startWarmupPolling" in template_text
    assert 'groupsQuickSearch.addEventListener("input"' in template_text
    assert 'contactsQuickSearch.addEventListener("input"' in template_text


def test_whatsapp_routes_expose_management_page_and_proxy_endpoints():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (
        project_root / "app" / "routes" / "whatsapp.py"
    ).read_text(encoding="utf-8")

    assert 'Blueprint("whatsapp_bot"' in route_text
    assert '@whatsapp_bot_bp.route("/management"' in route_text
    assert '@whatsapp_bot_bp.route("/api/session"' in route_text
    assert '@whatsapp_bot_bp.route("/api/session/initialize"' in route_text
    assert '@whatsapp_bot_bp.route("/api/groups"' in route_text
    assert '@whatsapp_bot_bp.route("/api/group-directory"' in route_text
    assert '@whatsapp_bot_bp.route("/api/contact-directory"' in route_text
    assert '@whatsapp_bot_bp.route("/api/contact-directory/validate"' in route_text
    assert '@whatsapp_bot_bp.route("/api/group-directory/validate-student"' in route_text
    assert '@whatsapp_bot_bp.route("/api/sync/messages/full"' in route_text
    assert '"students": students' in route_text
    assert '"tutors": tutors' in route_text


def test_base_sidebar_links_to_whatsapp_management_page():
    project_root = Path(__file__).resolve().parents[1]
    base_template = (
        project_root / "app" / "templates" / "base.html"
    ).read_text(encoding="utf-8")

    assert "url_for('whatsapp_bot.management')" in base_template
    assert "WhatsApp Bot" in base_template
