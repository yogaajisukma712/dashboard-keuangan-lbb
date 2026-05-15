from pathlib import Path


def test_base_enhances_all_bootstrap_selects_as_searchable():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (project_root / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert 'querySelectorAll("select.form-select, select[data-searchable-select]")' in template_text
    assert "function sortSelectOptions(select)" in template_text
    assert "localeCompare(optionText(right), \"id\"" in template_text
    assert "select.dataset.sortOptions === \"none\"" in template_text
    assert "input.disabled = select.disabled" in template_text
    assert 'select.addEventListener("lbb:refresh-searchable"' in template_text
