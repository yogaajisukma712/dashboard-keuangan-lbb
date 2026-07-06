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
    assert 'id="bulkMarkPaidForm"' in template_text
    assert 'id="bulkMarkPaidButton"' in template_text
    assert 'id="bulkMarkPaidCount"' in template_text
    assert "Pending ke Lunas" in template_text
    assert "payroll.tutor_summary_mark_paid_bulk" in template_text
    assert "applyTutorNameFilter" in template_text
    assert "updateSelectedTotals" in template_text
    assert "selectedPendingPayoutChecks" in template_text
    assert "prepareBulkMarkPaidForm" in template_text
    assert 'data-tutor-name="{{ tutor.name }}"' in template_text
    assert 'data-account-number="{{ tutor.bank_account_number or \'\' }}"' in template_text
    assert (
        'data-payout-status="{{ item.latest_payout.status if item.latest_payout else \'\' }}"'
        in template_text
    )


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


def test_tutor_summary_has_shortfall_settlement_action():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "payroll.py").read_text(
        encoding="utf-8"
    )
    template_text = (
        project_root / "app" / "templates" / "payroll" / "tutor_summary.html"
    ).read_text(encoding="utf-8")

    assert '"/tutor-summary/settle-shortfall"' in route_text
    assert "def tutor_summary_settle_shortfall" in route_text
    assert "Pembayaran kekurangan lunas periode" in route_text
    assert 'status="completed"' in route_text
    assert 'TutorPayout.status == "completed"' in route_text
    assert 'TutorPayout.status == "pending"' in route_text
    assert "Konfirmasi payout pending lebih dulu" in route_text
    assert "TutorPayoutLine(" in route_text
    assert "Gagal mencatat pembayaran kekurangan lunas" in route_text
    assert "payroll.tutor_summary_settle_shortfall" in template_text
    assert "p_done and has_balance" in template_text
    assert "Kekurangan Lunas" in template_text


def test_payout_detail_keeps_previous_payment_lines_for_shortfall_payouts():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "payroll.py").read_text(
        encoding="utf-8"
    )
    template_text = (
        project_root / "app" / "templates" / "payroll" / "payout_detail.html"
    ).read_text(encoding="utf-8")

    assert "def _get_display_payout_lines" in route_text
    assert "TutorPayout.status == \"completed\"" in route_text
    assert "display_payout_lines = _get_display_payout_lines(payout)" in route_text
    assert "display_payout_total = _sum_payout_lines(display_payout_lines)" in route_text
    assert "display_payout_lines=display_payout_lines" in route_text
    assert "display_payout_total=display_payout_total" in route_text
    assert "display_payout_lines %}" in template_text
    assert "format(display_payout_total)" in template_text
    assert "sessions_total != display_payout_total | float" in template_text
