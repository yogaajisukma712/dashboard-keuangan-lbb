from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(*parts):
    return (PROJECT_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_base_layouts_reference_shared_searchable_select_assets():
    base_text = _read("app", "templates", "base.html")
    tutor_text = _read("app", "templates", "tutor_portal", "base.html")

    for text in (base_text, tutor_text):
        assert "js/searchable-select.js" in text
        assert "css/searchable-select.css" in text


def test_base_inline_enhancer_is_fallback_only():
    base_text = _read("app", "templates", "base.html")

    # The inline enhancer must delegate to the shared module when present,
    # mirroring the `if (window.LbbPersistentFilters) return;` pattern.
    assert "if (window.LbbSearchableSelect)" in base_text
    assert "window.LbbSearchableSelect.enhance(select)" in base_text
    assert "window.LbbSearchableSelect.init(root)" in base_text


def test_shared_module_contract():
    js_text = _read("app", "static", "js", "searchable-select.js")

    assert 'select.form-select, select.month-form, select[data-searchable-select]' in js_text
    assert "function sortSelectOptions(select)" in js_text
    assert 'localeCompare(optionText(right), "id"' in js_text
    assert 'select.dataset.sortOptions === "none"' in js_text
    assert 'select.addEventListener("lbb:refresh-searchable"' in js_text
    assert "bootstrap.Dropdown" in js_text
    assert 'strategy: "fixed"' in js_text
    assert "autoClose" in js_text
    assert 'role", "listbox"' in js_text or 'role="listbox"' in js_text
    assert 'role", "option"' in js_text or 'role="option"' in js_text
    assert "MutationObserver" in js_text
    assert "Hapus pilihan" in js_text

def test_all_project_filter_selects_use_shared_searchable_selector():
    js_text = _read("app", "static", "js", "searchable-select.js")
    assert 'var SELECTOR = "select.form-select, select.month-form, select[data-searchable-select]";' in js_text

    reconciliation = _read("app", "templates", "dashboard", "reconciliation_dashboard.html")
    assert '<select id="reconMonthPicker" class="month-form"' in reconciliation
    assert '<select id="reconYearPicker" class="month-form"' in reconciliation

    for template in (PROJECT_ROOT / "app" / "templates").rglob("*.html"):
        for tag in re.findall(r"<select\b[^>]*>", template.read_text(encoding="utf-8"), re.I | re.S):
            assert re.search(r'class=["\'][^"\']*\b(?:form-select|month-form)\b', tag) or "data-searchable-select" in tag, (
                f"select without shared searchable enhancement: {template.relative_to(PROJECT_ROOT)}: {tag}"
            )
