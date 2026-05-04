from io import BytesIO

import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

from app import db
from app.models import AttendanceSession, Student, Tutor
from app.services.bulk_import_service import BulkImportService, DATASET_DEFINITIONS


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _file_storage(payload, filename="data.csv"):
    return FileStorage(stream=BytesIO(payload), filename=filename)


def test_import_dataset_rejects_unknown_dataset():
    service = BulkImportService(session=object())

    with pytest.raises(ValueError, match="Tipe dataset tidak dikenali"):
        service.import_dataset("unknown", _file_storage(b"name\nvalue\n"))


def test_import_dataset_rejects_empty_csv():
    service = BulkImportService(session=object())

    with pytest.raises(ValueError, match="CSV kosong"):
        service.import_dataset("students", _file_storage(b""))


def test_read_csv_handles_utf8_bom_and_header_cleanup():
    service = BulkImportService(session=object())
    file_storage = _file_storage(
        "\ufeff Nama Siswa , No HP \n Andi  , 08123 \n".encode("utf-8")
    )

    rows = service._read_csv(file_storage)

    assert rows == [{"nama siswa": "Andi", "no hp": "08123"}]


def test_read_csv_handles_cp1252_and_semicolon_delimiter():
    service = BulkImportService(session=object())
    payload = "Nama;Alamat\nAndré;Jalan Mawar\n".encode("cp1252")

    rows = service._read_csv(_file_storage(payload))

    assert rows == [{"nama": "André", "alamat": "Jalan Mawar"}]


@pytest.mark.parametrize("dataset_key", sorted(DATASET_DEFINITIONS))
def test_import_dataset_dispatches_every_dataset_handler(monkeypatch, dataset_key):
    service = BulkImportService(session=object())
    called = []

    def fake_read_csv(_file_storage):
        return [{"dummy": "value"}]

    def fake_handler(rows, **kwargs):
        called.append((rows, kwargs))

    monkeypatch.setattr(service, "_read_csv", fake_read_csv)
    monkeypatch.setattr(service, f"_import_{dataset_key}", fake_handler)

    result = service.import_dataset(
        dataset_key,
        _file_storage(b"dummy\nvalue\n"),
        current_user_id=99,
        service_month="2026-05",
    )

    assert result["dataset_key"] == dataset_key
    assert called == [
        (
            [{"dummy": "value"}],
            {"current_user_id": 99, "service_month": "2026-05"},
        )
    ]


def test_import_tutor_payouts_requires_service_month():
    service = BulkImportService(session=object())

    with pytest.raises(ValueError, match="Bulan layanan wajib diisi"):
        service._import_tutor_payouts([{"nama tutor": "A", "nominal": "1000"}], service_month=None)


def test_import_tutor_payouts_requires_yyyy_mm_format():
    service = BulkImportService(session=object())

    with pytest.raises(ValueError, match="Format bulan layanan harus YYYY-MM"):
        service._import_tutor_payouts(
            [{"nama tutor": "A", "nominal": "1000"}],
            service_month="05/2026",
        )


def test_import_attendance_preserves_duplicate_sessions_same_student_date():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Student(student_code="STD-RAFI", name="Rafi", grade="8"),
                Tutor(tutor_code="TTR-DINDA", name="Ms Dinda"),
            ]
        )
        db.session.commit()
        service = BulkImportService(session=db.session)
        payload = (
            "Tanggal,Tutor,Siswa,Kurikulum,Jenjang,Mapel,Nominal\n"
            "01/03/2026 09:00,Ms Dinda,Rafi,Nasional,SMP,Matematika,Rp50.000\n"
            "01/03/2026 10:00,Ms Dinda,Rafi,Nasional,SMP,Matematika,Rp50.000\n"
        ).encode("utf-8")

        result = service.import_dataset("attendance", _file_storage(payload))
        db.session.commit()

        sessions = AttendanceSession.query.order_by(AttendanceSession.id.asc()).all()
        assert result["created"] >= 2
        assert len(sessions) == 2
        assert sessions[0].session_date.isoformat() == "2026-03-01"
        assert sessions[0].notes != sessions[1].notes
