from pathlib import Path


def test_payout_revision_amount_accepts_plain_rupiah_integer():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "payout_detail.html"
    ).read_text(encoding="utf-8")

    assert 'name="amount"' in template_text
    assert 'min="0" step="1"' in template_text
    assert 'step="500"' not in template_text


def test_payout_proof_upload_accepts_clipboard_image_paste():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payroll" / "payout_detail.html"
    ).read_text(encoding="utf-8")

    assert 'id="proofPasteZone"' in template_text
    assert 'id="proofPasteStatus"' in template_text
    assert "new DataTransfer()" in template_text
    assert "bukti-transfer-clipboard." in template_text
    assert 'document.addEventListener("paste", handleProofPaste)' in template_text
