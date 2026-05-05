from pathlib import Path


def test_tutor_summary_has_name_filter_and_selected_totals():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "tutor_summary.html"
    ).read_text(encoding="utf-8")

    assert 'id="tutorNameFilter"' in template_text
    assert 'id="accountSort"' in template_text
    assert 'id="selectVisibleTutors"' in template_text
    assert "tutor-total-check" in template_text
    assert 'id="selectedBalanceTotal"' in template_text
    assert 'id="selectedPayableTotal"' in template_text
    assert "applyTutorNameFilter" in template_text
    assert "updateSelectedTotals" in template_text
    assert 'data-tutor-name="{{ tutor.name }}"' in template_text
    assert 'data-account-number="{{ tutor.bank_account_number or \'\' }}"' in template_text


def test_tutor_summary_keeps_plain_headers_and_sorts_by_account_number_control():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "tutor_summary.html"
    ).read_text(encoding="utf-8")

    assert "table-sort" not in template_text
    assert "data-sort-key" not in template_text
    assert "<th>Nama Tutor</th>" in template_text
    assert "<th>Bank</th>" in template_text
    assert "<th>No. Rekening</th>" in template_text
    assert "sortByAccountNumber" in template_text
    assert 'data-payroll-col="row-number"' in template_text
