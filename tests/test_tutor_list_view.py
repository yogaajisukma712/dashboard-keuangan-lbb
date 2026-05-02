from pathlib import Path


def test_tutor_list_template_contains_quick_search_for_current_page():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "tutors_list.html"
    ).read_text(encoding="utf-8")

    assert 'id="quickTutorSearch"' in template_text
    assert 'id="tutorTableBody"' in template_text
    assert 'class="tutor-row"' in template_text
    assert 'data-tutor-search="' in template_text
    assert "quickTutorSearchEmptyRow" in template_text
    assert "Tidak ada tutor di halaman ini yang cocok dengan pencarian cepat." in template_text
    assert 'quickTutorSearchInput.addEventListener("input"' in template_text
