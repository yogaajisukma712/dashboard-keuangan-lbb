from pathlib import Path
from datetime import datetime

from flask import Flask

from app import db
from app.models import AttendanceSession, Student, Tutor
from app.services.legacy_alldata_import_service import LegacyAlldataImportService


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_parse_period_label_handles_indonesian_month_names():
    service = LegacyAlldataImportService(session=object())

    assert str(service._parse_period_label("Februari 2025")) == "2025-02-01"
    assert str(service._parse_period_label("Agustus 2024")) == "2024-08-01"
    assert service._parse_period_label("invalid") is None


def test_discover_dataset_files_skips_duplicate_content(tmp_path: Path):
    service = LegacyAlldataImportService(session=object())
    payload = (
        "No,Tanggal,Id Siswa,Kurikulum,Jenjang,Kelas,Nama Siswa,Mata pelajaran,"
        "Jumlah pertemuan,Nominal,Hutang Gaji,Margin\n"
        "1,03/02/2025 08:40:04,S001,Nasional,SD,6,Andi,Matematika,4,Rp100.000,Rp80.000,Rp20.000\n"
    )
    (tmp_path / "Data Pembayaran Siswa.csv").write_text(payload)
    (tmp_path / "Data Pembayaran Siswacsv").write_text(payload)
    (tmp_path / "Data Presensi Tutor.csv").write_text(
        "No,Tanggal,Hari,Tutor,Siswa,Kurikulum,Jenjang,Mapel,Nominal\n"
        "1,05/08/2024,Senin,Tutor A,Siswa A,Nasional,SD,Matematika,Rp30.000\n"
    )

    discovered = service._discover_dataset_files(tmp_path)

    assert sorted(discovered) == ["attendance", "payments"]
    assert discovered["payments"].path.name == "Data Pembayaran Siswa.csv"
    assert any("isi identik" in warning for warning in service.warnings)


def test_normalized_similarity_handles_small_name_variants():
    service = LegacyAlldataImportService(session=object())

    assert service._normalized_similarity("Jiro Aray", "Jirou Aray") >= 0.84
    assert service._normalized_similarity("Bunga Alesya", "Bunga Aleeysa") >= 0.84


def test_legacy_payment_exclusion_matches_dashboard_reference_row():
    service = LegacyAlldataImportService(session=object())

    assert service._is_excluded_legacy_payment(
        datetime(2025, 4, 27),
        "2409010226012",
        "Science",
        225000,
        135000,
    )
    assert not service._is_excluded_legacy_payment(
        datetime(2025, 4, 25),
        "2409010226012",
        "Science",
        225000,
        200000,
    )


def test_import_attendance_preserves_duplicate_sessions_same_student_date(tmp_path: Path):
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
        csv_path = tmp_path / "Data Presensi Tutor.csv"
        csv_path.write_text(
            "No,Tanggal,Hari,Tutor,Siswa,Kurikulum,Jenjang,Mapel,Nominal\n"
            "1,01/03/2026 09:00,Minggu,Ms Dinda,Rafi,Nasional,SMP,Matematika,Rp50.000\n"
            "2,01/03/2026 10:00,Minggu,Ms Dinda,Rafi,Nasional,SMP,Matematika,Rp50.000\n",
            encoding="utf-8",
        )
        service = LegacyAlldataImportService(session=db.session)

        result = service._import_attendance(csv_path)
        db.session.commit()

        sessions = AttendanceSession.query.order_by(AttendanceSession.id.asc()).all()
        assert result["created"] == 2
        assert len(sessions) == 2
        assert sessions[0].session_date.isoformat() == "2026-03-01"
        assert sessions[0].notes != sessions[1].notes
