from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_shared_persistent_filter_assets_are_loaded_by_admin_and_tutor_layouts():
    admin_base = (PROJECT_ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    tutor_base = (PROJECT_ROOT / "app/templates/tutor_portal/base.html").read_text(
        encoding="utf-8"
    )

    for template in (admin_base, tutor_base):
        assert "css/persistent-filters.css" in template
        assert "js/persistent-filters.js" in template
        assert "data-lbb-filter-user" in template


def test_legacy_inline_filter_storage_is_disabled_when_shared_manager_loads():
    admin_base = (PROJECT_ROOT / "app/templates/base.html").read_text(encoding="utf-8")

    assert "if (window.LbbPersistentFilters) return;" in admin_base
    assert "processPendingFilterRestores" not in admin_base


def test_ajax_filters_reload_results_when_browser_history_changes():
    admin_base = (PROJECT_ROOT / "app/templates/base.html").read_text(encoding="utf-8")

    assert 'historyMode === "replace" ? "replaceState" : "pushState"' in admin_base
    assert 'window.addEventListener("popstate"' in admin_base
