from pathlib import Path


def test_tutor_summary_has_account_filter_and_selected_totals():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "tutor_summary.html"
    ).read_text(encoding="utf-8")

    assert 'id="accountFilter"' in template_text
    assert 'id="selectVisibleTutors"' in template_text
    assert "tutor-total-check" in template_text
    assert 'id="selectedBalanceTotal"' in template_text
    assert 'id="selectedPayableTotal"' in template_text
    assert "applyAccountFilter" in template_text
    assert "updateSelectedTotals" in template_text
    assert 'data-account-number="{{ tutor.bank_account_number or \'\' }}"' in template_text


def test_tutor_summary_headers_are_sortable():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "tutor_summary.html"
    ).read_text(encoding="utf-8")

    for sort_key in [
        "index",
        "tutorName",
        "bankName",
        "accountNumber",
        "payable",
        "paid",
        "balance",
    ]:
        assert f'data-sort-key="{sort_key}"' in template_text

    assert "sortTutorRows" in template_text
    assert "updateSortIndicators" in template_text
    assert 'data-payroll-col="row-number"' in template_text
    assert 'data-tutor-name="{{ tutor.name }}"' in template_text
    assert 'data-paid="{{ item.paid }}"' in template_text
