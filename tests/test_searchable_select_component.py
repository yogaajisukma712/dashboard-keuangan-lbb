from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JS = (PROJECT_ROOT / "app" / "static" / "js" / "searchable-select.js").read_text(
    encoding="utf-8"
)
CSS = (PROJECT_ROOT / "app" / "static" / "css" / "searchable-select.css").read_text(
    encoding="utf-8"
)


def test_sort_skip_regex_is_preserved():
    assert (
        "(month|year|per_page|page_size|status|sort|method|billing_type|period|date)"
        in JS
    )
    assert 'select.dataset.sortOptions === "az"' in JS


def test_multiple_selects_are_skipped():
    assert "if (select.multiple) return;" in JS


def test_hidden_and_disabled_options_excluded():
    assert "option.disabled || option.hidden" in JS


def test_truncation_notice_and_empty_state_strings():
    assert "Menampilkan " in JS
    assert "Persempit pencarian." in JS
    assert "Tidak ada hasil" in JS


def test_keyboard_keys_are_handled():
    for key in ["ArrowDown", "ArrowUp", "Enter", "Escape", "Home", "End"]:
        assert 'case "' + key + '":' in JS


def test_aria_attributes_present():
    assert "aria-activedescendant" in JS
    assert "aria-expanded" in JS
    assert "aria-selected" in JS


def test_required_submit_guard_exists():
    assert "is-invalid" in JS
    assert "invalid-feedback" in JS
    assert 'ownerForm.addEventListener("submit"' in JS


def test_clip_escape_and_menu_layer():
    # Popper fixed strategy escapes overflow containers.
    assert 'strategy: "fixed"' in JS
    # Menu must sit above the Bootstrap modal layer (1055).
    assert "z-index: 1080" in CSS


def test_placeholder_resolution_and_clear_behavior():
    assert 'getAttribute("data-placeholder")' in JS
    assert "Pilih" in JS
    assert "select.selectedIndex = -1" in JS


def test_runtime_observer_guards_against_self_insertions():
    assert 'node.classList.contains("lbb-select")' in JS
    assert 'dataset.lbbSearchableReady === "1"' in JS
