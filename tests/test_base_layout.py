from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_base_template_supports_desktop_sidebar_minimize():
    template_text = (
        PROJECT_ROOT / "app" / "templates" / "base.html"
    ).read_text(encoding="utf-8")

    assert "--sidebar-collapsed-w" in template_text
    assert "body.sidebar-collapsed #sidebar" in template_text
    assert "body.sidebar-collapsed #main-content" in template_text
    assert 'id="sidebarToggle"' in template_text
    assert 'aria-expanded="true"' in template_text
    assert 'var storageKey = "lbb:sidebar-collapsed";' in template_text
    assert 'window.localStorage.setItem(' in template_text
    assert 'sidebar.querySelectorAll(".sidebar-link")' in template_text
