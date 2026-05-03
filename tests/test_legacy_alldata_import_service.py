from pathlib import Path
from datetime import datetime

from app.services.legacy_alldata_import_service import LegacyAlldataImportService


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
