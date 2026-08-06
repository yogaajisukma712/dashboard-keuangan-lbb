"""Functional tests for period-wide transfer-proof aggregation on fee slips.

These cover the production bug where a settlement ("kekurangan lunas") payout
lost its sibling payout's transfer proofs on the fee slip, plus the scope-safety
and graceful-degradation guarantees around it.
"""

import os
from datetime import date, datetime
from pathlib import Path

import pytest
from flask import Flask

from app import db
from app.models import Tutor
from app.models.payroll import TutorPayout, TutorPayoutLine, TutorPayoutProof
from app.routes.payroll import (
    PREVIOUS_SHORTFALL_NOTE_PREFIX,
    SETTLEMENT_NOTE_PREFIX,
    _get_display_payout_proof_contexts,
    _get_period_payouts_for_display,
    payroll_bp,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def app(tmp_path):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=str(tmp_path),
        SERVER_NAME="localhost",
    )
    db.init_app(app)
    app.register_blueprint(payroll_bp)
    with app.app_context():
        db.create_all()
        with app.test_request_context():
            yield app
        db.drop_all()


def _tutor(code, name):
    tutor = Tutor(tutor_code=code, name=name, is_active=True)
    db.session.add(tutor)
    db.session.flush()
    return tutor


def _payout(tutor, *, amount, when, created=None, status="completed", notes=None):
    payout = TutorPayout(
        tutor_id=tutor.id,
        payout_date=when,
        amount=amount,
        status=status,
        notes=notes,
        created_at=created or when,
    )
    db.session.add(payout)
    db.session.flush()
    return payout


def _line(payout, *, service_month, amount, notes=None):
    line = TutorPayoutLine(
        tutor_payout_id=payout.id,
        service_month=service_month,
        amount=amount,
        notes=notes,
    )
    db.session.add(line)
    db.session.flush()
    return line


def _proof(payout, *, filename, uploaded_at, upload_folder, create_file=True):
    file_path = f"payroll_proofs/{filename}"
    proof = TutorPayoutProof(
        tutor_payout_id=payout.id,
        file_path=file_path,
        original_filename=filename,
        uploaded_at=uploaded_at,
    )
    db.session.add(proof)
    db.session.flush()
    if create_file:
        target_dir = os.path.join(upload_folder, "payroll_proofs")
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, filename), "wb") as handle:
            handle.write(b"\x89PNG\r\n")
    return proof


def test_settlement_payout_shows_sibling_original_proof(app):
    """Bug repro: settlement payout with zero own proofs still shows the
    original payout's proof via aggregation."""
    upload = app.config["UPLOAD_FOLDER"]
    tutor = _tutor("TTR-BUG", "Nadine")
    original = _payout(tutor, amount=30000, when=datetime(2026, 7, 5))
    _line(original, service_month=date(2026, 7, 1), amount=30000)
    _proof(original, filename="orig.png", uploaded_at=datetime(2026, 7, 5), upload_folder=upload)

    settlement = _payout(
        tutor,
        amount=60000,
        when=datetime(2026, 7, 20),
        notes=f"{SETTLEMENT_NOTE_PREFIX} periode Juli 2026",
    )
    _line(
        settlement,
        service_month=date(2026, 7, 1),
        amount=60000,
        notes=f"{SETTLEMENT_NOTE_PREFIX} periode Juli 2026",
    )
    db.session.commit()

    items = _get_display_payout_proof_contexts(settlement)
    filenames = [item["filename"] for item in items]
    assert filenames == ["orig.png"]
    assert items[0]["payout_id"] == original.id
    assert items[0]["is_current_payout"] is False
    assert items[0]["payment_label"] == "Pembayaran Utama"


def test_two_payouts_same_period_show_both_ordered_with_labels(app):
    upload = app.config["UPLOAD_FOLDER"]
    tutor = _tutor("TTR-TWO", "Rendi")
    original = _payout(tutor, amount=675000, when=datetime(2026, 7, 3))
    _line(original, service_month=date(2026, 7, 1), amount=675000)
    _proof(original, filename="main.png", uploaded_at=datetime(2026, 7, 3), upload_folder=upload)

    settlement = _payout(
        tutor,
        amount=30000,
        when=datetime(2026, 7, 25),
        notes=f"{SETTLEMENT_NOTE_PREFIX} periode Juli 2026",
    )
    _line(
        settlement,
        service_month=date(2026, 7, 1),
        amount=30000,
        notes=f"{SETTLEMENT_NOTE_PREFIX} periode Juli 2026",
    )
    _proof(settlement, filename="extra.png", uploaded_at=datetime(2026, 7, 25), upload_folder=upload)
    db.session.commit()

    for viewed in (original, settlement):
        items = _get_display_payout_proof_contexts(viewed)
        assert [i["filename"] for i in items] == ["main.png", "extra.png"]
        assert [i["payment_label"] for i in items] == [
            "Pembayaran Utama",
            "Pembayaran Kekurangan",
        ]
        current = {i["filename"]: i["is_current_payout"] for i in items}
        if viewed is original:
            assert current == {"main.png": True, "extra.png": False}
        else:
            assert current == {"main.png": False, "extra.png": True}


def test_no_duplicate_when_file_in_legacy_column_and_proof_table(app):
    upload = app.config["UPLOAD_FOLDER"]
    tutor = _tutor("TTR-DUP", "Dinda")
    payout = _payout(tutor, amount=50000, when=datetime(2026, 7, 8))
    _line(payout, service_month=date(2026, 7, 1), amount=50000)
    payout.proof_image = "payroll_proofs/dup.png"
    _proof(payout, filename="dup.png", uploaded_at=datetime(2026, 7, 8), upload_folder=upload)
    db.session.commit()

    items = _get_display_payout_proof_contexts(payout)
    assert [i["filename"] for i in items] == ["dup.png"]


def test_carried_previous_shortfall_payout_shows_only_own_proofs(app):
    upload = app.config["UPLOAD_FOLDER"]
    tutor = _tutor("TTR-CARRY", "Listya")

    # A normal completed payout in the same period that MUST NOT be aggregated
    # into the carried-shortfall payout's slip.
    normal = _payout(tutor, amount=40000, when=datetime(2026, 7, 2))
    _line(normal, service_month=date(2026, 7, 1), amount=40000)
    _proof(normal, filename="normal.png", uploaded_at=datetime(2026, 7, 2), upload_folder=upload)

    carried = _payout(tutor, amount=15000, when=datetime(2026, 7, 30))
    _line(
        carried,
        service_month=date(2026, 7, 1),
        amount=15000,
        notes=f"{PREVIOUS_SHORTFALL_NOTE_PREFIX} Juni 2026",
    )
    _proof(carried, filename="carried.png", uploaded_at=datetime(2026, 7, 30), upload_folder=upload)
    db.session.commit()

    assert _get_period_payouts_for_display(carried) == [carried]
    items = _get_display_payout_proof_contexts(carried)
    assert [i["filename"] for i in items] == ["carried.png"]


def test_scope_safety_other_tutor_proof_never_included(app):
    upload = app.config["UPLOAD_FOLDER"]
    tutor_a = _tutor("TTR-A", "Tutor A")
    tutor_b = _tutor("TTR-B", "Tutor B")

    payout_a = _payout(tutor_a, amount=30000, when=datetime(2026, 7, 5))
    _line(payout_a, service_month=date(2026, 7, 1), amount=30000)
    _proof(payout_a, filename="a.png", uploaded_at=datetime(2026, 7, 5), upload_folder=upload)

    payout_b = _payout(tutor_b, amount=99000, when=datetime(2026, 7, 6))
    _line(payout_b, service_month=date(2026, 7, 1), amount=99000)
    _proof(payout_b, filename="b.png", uploaded_at=datetime(2026, 7, 6), upload_folder=upload)
    db.session.commit()

    related = _get_period_payouts_for_display(payout_a)
    assert all(p.tutor_id == tutor_a.id for p in related)

    items = _get_display_payout_proof_contexts(payout_a)
    assert [i["filename"] for i in items] == ["a.png"]
    assert all(i["payout_id"] != payout_b.id for i in items)


def test_missing_file_marked_and_no_image_url(app):
    upload = app.config["UPLOAD_FOLDER"]
    tutor = _tutor("TTR-MISS", "Crysant")
    payout = _payout(tutor, amount=20000, when=datetime(2026, 7, 4))
    _line(payout, service_month=date(2026, 7, 1), amount=20000)
    _proof(
        payout,
        filename="lost.png",
        uploaded_at=datetime(2026, 7, 4),
        upload_folder=upload,
        create_file=False,
    )
    db.session.commit()

    items = _get_display_payout_proof_contexts(payout)
    assert len(items) == 1
    assert items[0]["exists"] is False
    assert items[0]["image_url"] is None
    assert items[0]["is_image"] is True  # extension still known

    # Templates must render a "tidak ditemukan" state guarded on proof.exists.
    slip = (PROJECT_ROOT / "app" / "templates" / "payroll" / "fee_slip.html").read_text(
        encoding="utf-8"
    )
    detail = (
        PROJECT_ROOT / "app" / "templates" / "payroll" / "payout_detail.html"
    ).read_text(encoding="utf-8")
    assert "Berkas bukti tidak ditemukan di server" in slip
    assert "not proof.exists" in slip
    assert "Berkas bukti tidak ditemukan di server" in detail
    assert "not proof.exists" in detail


def test_plain_single_payout_regression(app):
    upload = app.config["UPLOAD_FOLDER"]
    tutor = _tutor("TTR-SOLO", "Solo")
    payout = _payout(tutor, amount=25000, when=datetime(2026, 7, 9))
    _line(payout, service_month=date(2026, 7, 1), amount=25000)
    _proof(payout, filename="solo.png", uploaded_at=datetime(2026, 7, 9), upload_folder=upload)
    db.session.commit()

    items = _get_display_payout_proof_contexts(payout)
    assert len(items) == 1
    item = items[0]
    assert item["filename"] == "solo.png"
    assert item["exists"] is True
    assert item["image_url"]
    assert item["is_current_payout"] is True
    assert item["payment_label"] == "Pembayaran Utama"
