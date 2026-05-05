from pathlib import Path


def test_fee_slip_verify_wraps_long_identity_values_on_mobile():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "fee_slip_verify.html"
    ).read_text(encoding="utf-8")

    assert "verify-detail-table" in template_text
    assert "verify-long-text" in template_text
    assert "overflow-wrap: anywhere" in template_text
    assert "word-break: break-word" in template_text
    assert 'class="verify-value verify-long-text">{{ tutor.email or \'-\' }}</td>' in template_text
