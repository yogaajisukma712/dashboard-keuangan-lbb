"""
Legacy CSV importer for the `alldata` folder.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    Expense,
    OtherIncome,
    Student,
    StudentPayment,
    StudentPaymentLine,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
)
from app.services.bulk_import_service import BulkImportService

MONTH_NAME_MAP = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}

DATASET_ALIASES = {
    "data pembayaran siswa.csv": "payments",
    "data pembayaran siswacsv": "payments",
    "data presensi tutor.csv": "attendance",
    "data presensi tutor akumulasi.csv": "tutor_payouts",
    "data pemasukan lain lain.csv": "incomes",
    "data pengeluaran lain lain.csv": "expenses",
}

LEGACY_PAYMENT_EXCLUSIONS = {
    # Rows that exist in the CSV but must be excluded from ALL months.
    # If a corresponding LEGACY_PAYMENT_REDIRECTS entry exists for the same key,
    # the row is re-imported under the corrected date instead of being skipped.
}

# Payments whose service month in the reference dashboard differs from their
# payment_date in the CSV.  Each entry re-dates the row so it lands in the
# correct month without touching the source file.
# Key  : (original_date_iso, student_code, subject_lower, nominal_int, tp_int)
# Value: corrected date to use as payment_date
LEGACY_PAYMENT_REDIRECTS: dict = {
    # Zara Abigail Lasut / Science, paid 27-Apr-2025:
    # Reference dashboard counts this as Juni 2025 service, not April.
    # → excluded from April, re-imported under Juni 2025.
    ("2025-04-27", "2409010226012", "science", 225000, 135000): date(2025, 6, 1),
    # Arfa athaya firdaus / Matematika, paid 07-Jan-2026:
    # Reference dashboard classifies as Februari 2026 (service month).
    # → payment_date in CSV is January; re-import under Februari 2026.
    ("2026-01-07", "2507010101006", "matematika", 300000, 240000): date(2026, 2, 1),
    # Wayne Nicolaet El Fatta Brilliant / Matematika, paid 15-Jan-2026:
    # Reference dashboard classifies as Februari 2026 (service month).
    # Note: Wayne’s IPA payment on the same date stays in January.
    # → re-import under Februari 2026.
    ("2026-01-15", "2411010223003", "matematika", 750000, 480000): date(2026, 2, 1),
}


@dataclass
class DatasetFile:
    dataset_key: str
    path: Path
    content_hash: str


class LegacyAlldataImportService:
    def __init__(self, session=None):
        self.session = session or db.session
        self.bulk = BulkImportService(session=self.session)
        self.bulk._result = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "warnings": [],
        }
        self.warnings = []

    def _normalized_similarity(self, left, right):
        left_key = re.sub(r"[^a-z0-9]+", "", (left or "").lower())
        right_key = re.sub(r"[^a-z0-9]+", "", (right or "").lower())
        if not left_key or not right_key:
            return 0
        return difflib.SequenceMatcher(a=left_key, b=right_key).ratio()

    def import_directory(self, directory_path, current_user_id=None):
        dataset_files = self._discover_dataset_files(directory_path)
        summaries = {}

        if "payments" in dataset_files:
            self._cleanup_legacy_february_2025_payments()
            summaries["payments"] = self._import_payments(
                dataset_files["payments"].path,
                current_user_id=current_user_id,
            )
            self.session.commit()

        if "attendance" in dataset_files:
            summaries["attendance"] = self._import_attendance(
                dataset_files["attendance"].path
            )
            self.session.commit()

        if "tutor_payouts" in dataset_files:
            self._cleanup_legacy_february_2025_payouts()
            summaries["tutor_payouts"] = self._import_tutor_payouts(
                dataset_files["tutor_payouts"].path
            )
            self.session.commit()

        if "incomes" in dataset_files:
            summaries["incomes"] = self._import_incomes(
                dataset_files["incomes"].path,
                current_user_id=current_user_id,
            )
            self.session.commit()

        if "expenses" in dataset_files:
            summaries["expenses"] = self._import_expenses(
                dataset_files["expenses"].path,
                current_user_id=current_user_id,
            )
            self.session.commit()

        return {
            "datasets": summaries,
            "warnings": self.warnings,
        }

    def _discover_dataset_files(self, directory_path):
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Folder tidak ditemukan: {directory}")

        dataset_files = {}
        seen_hashes = {}
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            dataset_key = DATASET_ALIASES.get(path.name.strip().lower())
            if not dataset_key:
                continue

            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            duplicate_of = seen_hashes.get(content_hash)
            if duplicate_of:
                self.warnings.append(
                    f"File {path.name} dilewati karena isi identik dengan {duplicate_of.name}."
                )
                continue

            seen_hashes[content_hash] = path
            chosen = dataset_files.get(dataset_key)
            if chosen:
                self.warnings.append(
                    f"Dataset {dataset_key} memakai {chosen.path.name}, file {path.name} dilewati."
                )
                continue
            dataset_files[dataset_key] = DatasetFile(
                dataset_key=dataset_key,
                path=path,
                content_hash=content_hash,
            )
        return dataset_files

    def _read_rows(self, path):
        payload = path.read_bytes()
        text = self.bulk._decode_csv_payload(payload)
        dialect = self.bulk._detect_csv_dialect(text)
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = []
        for raw_row in reader:
            row = {}
            for key, value in (raw_row or {}).items():
                clean_key = self.bulk._clean_header(key)
                if clean_key:
                    row[clean_key] = (value or "").strip()
            if any(value for value in row.values()):
                rows.append(row)
        return rows

    def _parse_period_label(self, value):
        text = self.bulk._normalize_name(value)
        if not text:
            return None
        match = re.search(r"([A-Za-z]+)\s+(\d{4})", text)
        if not match:
            return None
        month_text = match.group(1).lower()
        year = int(match.group(2))
        month = MONTH_NAME_MAP.get(month_text)
        if not month:
            return None
        return date(year, month, 1)

    def _build_occurrence_indexes(self, items, key_builder):
        counter = defaultdict(int)
        results = []
        for item in items:
            key = key_builder(item)
            counter[key] += 1
            results.append(counter[key])
        return results

    def _make_note(self, dataset_key, fingerprint):
        return f"legacy-alldata:{dataset_key}:{fingerprint}"

    def _is_excluded_legacy_payment(
        self, payment_at, student_code, subject_name, nominal_amount, tutor_payable
    ):
        if not payment_at:
            return False
        key = (
            payment_at.date().isoformat(),
            self.bulk._normalize_name(student_code),
            self.bulk._normalize_name(subject_name).lower(),
            int(nominal_amount or 0),
            int(tutor_payable or 0),
        )
        return key in LEGACY_PAYMENT_EXCLUSIONS

    def _get_legacy_payment_redirect(
        self, payment_at, student_code, subject_name, nominal_amount, tutor_payable
    ):
        """Return a corrected payment date if this row should be re-dated, else None.

        Rows in LEGACY_PAYMENT_REDIRECTS are removed from their original date
        and re-imported under the returned date, so they land in the correct
        month for dashboard calculations.
        """
        if not payment_at:
            return None
        key = (
            payment_at.date().isoformat(),
            self.bulk._normalize_name(student_code),
            self.bulk._normalize_name(subject_name).lower(),
            int(nominal_amount or 0),
            int(tutor_payable or 0),
        )
        return LEGACY_PAYMENT_REDIRECTS.get(key)

    def _cleanup_legacy_february_2025_payments(self):
        legacy_headers = StudentPayment.query.filter(
            db.extract("year", StudentPayment.payment_date) == 2025,
            db.extract("month", StudentPayment.payment_date) == 2,
            db.or_(
                StudentPayment.notes == "Import Februari 2025",
                StudentPayment.receipt_number.like("INV/FEB2025/%"),
            ),
        ).all()
        for payment in legacy_headers:
            self.session.delete(payment)
        self.session.flush()

    def _cleanup_legacy_february_2025_payouts(self):
        feb_date = date(2025, 2, 1)
        legacy_lines = TutorPayoutLine.query.filter_by(service_month=feb_date).all()
        deleted_payout_ids = set()
        for line in legacy_lines:
            payout = TutorPayout.query.get(line.tutor_payout_id)
            if not payout or payout.id in deleted_payout_ids:
                continue
            if (
                payout.notes == "Import rekap gaji Februari 2025"
                or (line.notes or "") == "Gaji Februari 2025"
            ):
                self.session.delete(payout)
                deleted_payout_ids.add(payout.id)
        self.session.flush()

    def _find_student_flexible(self, code=None, name=None):
        student = self.bulk._find_student(code=code, name=name)
        if student:
            return student
        name_key = self.bulk._normalize_name(name)
        if name_key:
            exact = (
                Student.query.filter(
                    db.func.lower(Student.name).like(f"%{name_key.lower()}%")
                )
                .order_by(Student.id.asc())
                .first()
            )
            if exact:
                return exact
            best_match = None
            best_score = 0
            for student in Student.query.all():
                score = self._normalized_similarity(student.name, name_key)
                if score > best_score:
                    best_score = score
                    best_match = student
            if best_score >= 0.84:
                return best_match
        return None

    def _find_tutor_flexible(self, code=None, name=None):
        tutor = self.bulk._find_tutor(code=code, name=name)
        if tutor:
            return tutor
        name_key = self.bulk._normalize_name(name)
        if name_key:
            exact = (
                Tutor.query.filter(
                    db.func.lower(Tutor.name).like(f"%{name_key.lower()}%")
                )
                .order_by(Tutor.id.asc())
                .first()
            )
            if exact:
                return exact
            best_match = None
            best_score = 0
            for tutor in Tutor.query.all():
                score = self._normalized_similarity(tutor.name, name_key)
                if score > best_score:
                    best_score = score
                    best_match = tutor
            if best_score >= 0.84:
                return best_match
        return None

    def _resolve_enrollment(
        self,
        student,
        tutor,
        subject,
        curriculum,
        level,
        grade,
        reference_date,
        student_rate,
        tutor_rate,
    ):
        enrollment = (
            Enrollment.query.filter_by(
                student_id=student.id,
                subject_id=subject.id,
                tutor_id=tutor.id,
                status="active",
            )
            .order_by(Enrollment.id.desc())
            .first()
        )
        if enrollment:
            return enrollment

        enrollment = (
            Enrollment.query.filter_by(
                student_id=student.id,
                subject_id=subject.id,
                status="active",
            )
            .order_by(Enrollment.id.desc())
            .first()
        )
        if enrollment:
            return enrollment

        pricing = self.bulk._match_pricing(curriculum, level, subject)
        return self.bulk._get_or_create_enrollment(
            student=student,
            subject=subject,
            tutor=tutor,
            curriculum=curriculum,
            level=level,
            grade=grade or student.grade,
            meeting_quota=pricing.default_meeting_quota if pricing else 4,
            student_rate=(
                float(pricing.student_rate_per_meeting)
                if pricing and float(pricing.student_rate_per_meeting or 0) > 0
                else student_rate
            ),
            tutor_rate=(
                float(pricing.tutor_rate_per_meeting)
                if pricing and float(pricing.tutor_rate_per_meeting or 0) > 0
                else tutor_rate
            ),
            start_date=reference_date,
            status="active",
            notes="Auto-created from legacy alldata import.",
        )

    def _import_payments(self, path, current_user_id=None):
        rows = self._read_rows(path)
        result = {"created": 0, "updated": 0, "skipped": 0, "rows": len(rows)}
        payment_cache = {}

        # Per-run tracking for duplicate payment lines.
        # When the CSV contains two identical rows (same student, date, enrollment,
        # amount), the first gets the base line_key (backward-compatible with
        # existing DB records).  Subsequent duplicates get a "|"+n suffix so they
        # are stored as separate lines instead of being silently dropped.
        _seen_line_keys: set = set()  # base keys processed this run
        _dup_counters: dict = defaultdict(int)  # how many duplicates seen so far

        for index, row in enumerate(rows, start=1):
            payment_at = self.bulk._parse_datetime(row.get("tanggal"))
            student_code = self.bulk._normalize_name(row.get("id siswa"))
            subject_name = self.bulk._normalize_name(row.get("mata pelajaran"))
            student_name = self.bulk._normalize_name(row.get("nama siswa"))
            if not payment_at or not student_code or not subject_name:
                result["skipped"] += 1
                self.warnings.append(
                    f"Pembayaran {path.name} baris {index} dilewati karena data utama kosong."
                )
                continue

            student = self._find_student_flexible(code=student_code, name=student_name)
            if not student:
                student = self.bulk._get_or_create_student(
                    student_code,
                    student_name,
                    curriculum_id=None,
                    level_id=None,
                    grade=self.bulk._normalize_name(row.get("kelas")),
                    status="active",
                    is_active=True,
                )

            subject = self.bulk._get_or_create_subject(subject_name)
            curriculum = self.bulk._get_or_create_curriculum(row.get("kurikulum"))
            level = self.bulk._get_or_create_level(row.get("jenjang"))
            enrollment = (
                Enrollment.query.filter_by(
                    student_id=student.id,
                    subject_id=subject.id,
                )
                .order_by(Enrollment.id.desc())
                .first()
            )
            if not enrollment:
                fallback_enrollment = (
                    Enrollment.query.filter_by(student_id=student.id)
                    .order_by(Enrollment.id.desc())
                    .first()
                )
                tutor_obj = fallback_enrollment.tutor if fallback_enrollment else None
                if not tutor_obj:
                    result["skipped"] += 1
                    self.warnings.append(
                        f"Pembayaran {path.name} baris {index} dilewati karena enrollment {student.name} / {subject.name} belum ada."
                    )
                    continue
                enrollment = self._resolve_enrollment(
                    student=student,
                    tutor=tutor_obj,
                    subject=subject,
                    curriculum=curriculum,
                    level=level,
                    grade=self.bulk._normalize_name(row.get("kelas")),
                    reference_date=payment_at,
                    student_rate=0,
                    tutor_rate=0,
                )

            meeting_count = self.bulk._parse_int(row.get("jumlah pertemuan"), default=0)
            nominal_amount = self.bulk._parse_currency(row.get("nominal"))
            tutor_payable = self.bulk._parse_currency(row.get("hutang gaji"))
            margin_amount = self.bulk._parse_currency(row.get("margin"))
            # ── Step 1: check for payment redirect (re-date to correct month) ──
            redirect_date = self._get_legacy_payment_redirect(
                payment_at, student_code, subject_name, nominal_amount, tutor_payable
            )
            if redirect_date is not None:
                # Save the original date so we can remove any previously imported
                # record that sits on the wrong month.
                _orig_pat = payment_at
                payment_at = datetime.combine(redirect_date, time.min)

                # Remove the old payment line (original date) if it was already
                # imported in a previous run, to avoid counting it twice.
                _old_margin = margin_amount or (nominal_amount - tutor_payable)
                _old_bk = "|".join(
                    [
                        student.student_code,
                        _orig_pat.isoformat(),
                        str(enrollment.id),
                        str(meeting_count),
                        str(int(nominal_amount)),
                        str(int(tutor_payable)),
                        str(int(_old_margin)),
                    ]
                )
                _old_line_note = self._make_note("payments-line", _old_bk)
                _old_line = StudentPaymentLine.query.filter_by(
                    notes=_old_line_note
                ).first()
                if _old_line:
                    _old_pmt_id = _old_line.student_payment_id
                    self.session.delete(_old_line)
                    self.session.flush()
                    # If the old payment header has no remaining lines, remove it too
                    _remaining = StudentPaymentLine.query.filter_by(
                        student_payment_id=_old_pmt_id
                    ).count()
                    if _remaining == 0:
                        _old_pmt = StudentPayment.query.get(_old_pmt_id)
                        if _old_pmt:
                            self.session.delete(_old_pmt)
                            # Remove stale cache entry so a new header is created
                            payment_cache.pop(
                                f"{student.student_code}|{_orig_pat.isoformat()}",
                                None,
                            )
                    self.session.flush()

            elif self._is_excluded_legacy_payment(
                payment_at,
                student_code,
                subject_name,
                nominal_amount,
                tutor_payable,
            ):
                result["skipped"] += 1
                self.warnings.append(
                    f"Pembayaran {path.name} baris {index} dilewati karena dikecualikan dari acuan dashboard."
                )
                continue
            if meeting_count <= 0:
                result["skipped"] += 1
                self.warnings.append(
                    f"Pembayaran {path.name} baris {index} dilewati karena jumlah pertemuan nol."
                )
                continue

            header_key = f"{student.student_code}|{payment_at.isoformat()}"
            payment = payment_cache.get(header_key)
            header_note = self._make_note("payments-header", header_key)
            if not payment:
                payment = StudentPayment.query.filter_by(notes=header_note).first()
                if not payment and payment_at.year == 2025 and payment_at.month == 2:
                    payment = StudentPayment.query.filter_by(
                        student_id=student.id,
                        payment_date=payment_at,
                    ).first()
                if not payment:
                    receipt_number = f"IMP-PAY-{payment_at.strftime('%Y%m%d%H%M%S')}-{student.student_code[-6:]}"
                    suffix = 1
                    candidate = receipt_number
                    while StudentPayment.query.filter_by(
                        receipt_number=candidate
                    ).first():
                        suffix += 1
                        candidate = f"{receipt_number}-{suffix}"
                    payment = StudentPayment(
                        student_id=student.id,
                        payment_date=payment_at,
                        receipt_number=candidate,
                        payment_method="bank_transfer",
                        total_amount=0,
                        notes=header_note,
                        is_verified=True,
                        verified_by=current_user_id,
                        verified_at=datetime.utcnow(),
                    )
                    self.session.add(payment)
                    self.session.flush()
                    result["created"] += 1
                else:
                    payment.notes = header_note
                    payment.total_amount = 0
                    result["updated"] += 1
                payment_cache[header_key] = payment

            # ── Build line key (occurrence-aware, backward-compatible) ──────────
            # The base key is identical to the historical format so that existing
            # DB records (imported before this fix) are still found on re-import.
            # When the same base key appears a SECOND time in the same CSV run
            # (i.e. a legitimate duplicate row), we append "|dup<n>" so the second
            # row is stored as a distinct line instead of being silently dropped.
            _base_line_key = "|".join(
                [
                    student.student_code,
                    payment_at.isoformat(),
                    str(enrollment.id),
                    str(meeting_count),
                    str(int(nominal_amount)),
                    str(int(tutor_payable)),
                    str(int(margin_amount)),
                ]
            )
            if _base_line_key in _seen_line_keys:
                # Duplicate row in this CSV run → give it a unique suffix
                _dup_n = _dup_counters[_base_line_key] + 1
                _dup_counters[_base_line_key] = _dup_n
                line_key = f"{_base_line_key}|dup{_dup_n}"
            else:
                # First occurrence → use base key (backward-compatible)
                _seen_line_keys.add(_base_line_key)
                line_key = _base_line_key
            line_note = self._make_note("payments-line", line_key)
            existing_line = StudentPaymentLine.query.filter_by(notes=line_note).first()
            if not existing_line and payment_at.year == 2025 and payment_at.month == 2:
                existing_line = StudentPaymentLine.query.filter_by(
                    student_payment_id=payment.id,
                    enrollment_id=enrollment.id,
                    meeting_count=meeting_count,
                    nominal_amount=nominal_amount,
                ).first()
            if existing_line:
                existing_line.student_payment_id = payment.id
                existing_line.service_month = date(payment_at.year, payment_at.month, 1)
                existing_line.student_rate_per_meeting = (
                    nominal_amount / meeting_count if meeting_count else 0
                )
                existing_line.tutor_rate_per_meeting = (
                    tutor_payable / meeting_count if meeting_count else 0
                )
                existing_line.tutor_payable_amount = tutor_payable
                existing_line.margin_amount = margin_amount or (
                    nominal_amount - tutor_payable
                )
                existing_line.notes = line_note
                result["updated"] += 1
            else:
                line = StudentPaymentLine(
                    student_payment_id=payment.id,
                    enrollment_id=enrollment.id,
                    service_month=date(payment_at.year, payment_at.month, 1),
                    meeting_count=meeting_count,
                    student_rate_per_meeting=(
                        nominal_amount / meeting_count if meeting_count else 0
                    ),
                    tutor_rate_per_meeting=(
                        tutor_payable / meeting_count if meeting_count else 0
                    ),
                    nominal_amount=nominal_amount,
                    tutor_payable_amount=tutor_payable,
                    margin_amount=margin_amount or (nominal_amount - tutor_payable),
                    notes=line_note,
                )
                self.session.add(line)
                result["created"] += 1

        for payment in payment_cache.values():
            payment.total_amount = sum(
                float(line.nominal_amount or 0) for line in payment.payment_lines
            )
        return result

    def _import_attendance(self, path):
        rows = self._read_rows(path)
        result = {"created": 0, "updated": 0, "skipped": 0, "rows": len(rows)}

        for index, row in enumerate(rows, start=1):
            session_date = self.bulk._parse_datetime(row.get("tanggal"))
            tutor_name = self.bulk._normalize_name(row.get("tutor"))
            student_name = self.bulk._normalize_name(row.get("siswa"))
            if not session_date or not tutor_name or not student_name:
                result["skipped"] += 1
                continue

            tutor = self._find_tutor_flexible(name=tutor_name)
            student = self._find_student_flexible(name=student_name)
            if not tutor or not student:
                result["skipped"] += 1
                self.warnings.append(
                    f"Presensi {path.name} baris {index} dilewati karena tutor atau siswa tidak ditemukan."
                )
                continue

            curriculum = self.bulk._get_or_create_curriculum(row.get("kurikulum"))
            level = self.bulk._get_or_create_level(row.get("jenjang"))
            subject = self.bulk._get_or_create_subject(row.get("mapel"))
            nominal = self.bulk._parse_currency(row.get("nominal"))
            enrollment = self._resolve_enrollment(
                student=student,
                tutor=tutor,
                subject=subject,
                curriculum=curriculum,
                level=level,
                grade=student.grade,
                reference_date=session_date,
                student_rate=nominal,
                tutor_rate=nominal,
            )
            note = self._make_note(
                "attendance",
                "|".join(
                    [
                        session_date.date().isoformat(),
                        str(student.id),
                        str(tutor.id),
                        str(subject.id),
                    ]
                ),
            )
            attendance = AttendanceSession.query.filter_by(notes=note).first()
            if not attendance:
                attendance = AttendanceSession.query.filter_by(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=session_date.date(),
                ).first()
            if attendance:
                attendance.enrollment_id = enrollment.id
                attendance.status = "attended"
                attendance.student_present = True
                attendance.tutor_present = True
                attendance.tutor_fee_amount = nominal
                attendance.notes = note
                result["updated"] += 1
                continue

            attendance = AttendanceSession(
                enrollment_id=enrollment.id,
                student_id=student.id,
                tutor_id=tutor.id,
                subject_id=subject.id,
                session_date=session_date.date(),
                status="attended",
                student_present=True,
                tutor_present=True,
                tutor_fee_amount=nominal,
                notes=note,
            )
            self.session.add(attendance)
            result["created"] += 1
        return result

    def _import_incomes(self, path, current_user_id=None):
        rows = self._read_rows(path)
        result = {"created": 0, "updated": 0, "skipped": 0, "rows": len(rows)}
        occurrences = self._build_occurrence_indexes(
            rows,
            lambda row: (
                self._parse_period_label(row.get("no")),
                self.bulk._normalize_name(row.get("deskripsi")),
                self.bulk._parse_currency(row.get("nominal")),
            ),
        )

        for index, row in enumerate(rows, start=1):
            income_month = self._parse_period_label(row.get("no"))
            description = self.bulk._normalize_name(row.get("deskripsi"))
            amount = self.bulk._parse_currency(row.get("nominal"))
            occurrence = occurrences[index - 1]
            if not income_month or not description or amount <= 0:
                result["skipped"] += 1
                continue
            if income_month.year == 2025 and income_month.month == 2:
                OtherIncome.query.filter(
                    db.extract("year", OtherIncome.income_date) == 2025,
                    db.extract("month", OtherIncome.income_date) == 2,
                    OtherIncome.description == description,
                    OtherIncome.amount == amount,
                ).delete(synchronize_session=False)
                self.session.flush()
            note = self._make_note(
                "incomes",
                f"{income_month.isoformat()}|{description}|{int(amount)}|{occurrence}",
            )
            income = OtherIncome.query.filter_by(notes=note).first()
            if income:
                result["updated"] += 1
                continue
            income = OtherIncome(
                income_date=datetime.combine(income_month, time.min),
                category=description.split()[0][:50] if description else "Import",
                description=description,
                amount=amount,
                notes=note,
                created_by=current_user_id,
                is_active=True,
            )
            self.session.add(income)
            result["created"] += 1
        return result

    def _import_expenses(self, path, current_user_id=None):
        rows = self._read_rows(path)
        result = {"created": 0, "updated": 0, "skipped": 0, "rows": len(rows)}
        occurrences = self._build_occurrence_indexes(
            rows,
            lambda row: (
                self._parse_period_label(row.get("no")),
                self.bulk._normalize_name(row.get("deskripsi")),
                self.bulk._parse_currency(row.get("nominal")),
            ),
        )

        for index, row in enumerate(rows, start=1):
            expense_month = self._parse_period_label(row.get("no"))
            description = self.bulk._normalize_name(row.get("deskripsi"))
            amount = self.bulk._parse_currency(row.get("nominal"))
            occurrence = occurrences[index - 1]
            if not expense_month or not description or amount <= 0:
                result["skipped"] += 1
                continue
            if expense_month.year == 2025 and expense_month.month == 2:
                Expense.query.filter(
                    db.extract("year", Expense.expense_date) == 2025,
                    db.extract("month", Expense.expense_date) == 2,
                    Expense.description == description,
                    Expense.amount == amount,
                ).delete(synchronize_session=False)
                self.session.flush()
            note = self._make_note(
                "expenses",
                f"{expense_month.isoformat()}|{description}|{int(amount)}|{occurrence}",
            )
            expense = Expense.query.filter_by(notes=note).first()
            if expense:
                result["updated"] += 1
                continue
            category = description.split()[0][:50] if description else "Import"
            expense = Expense(
                expense_date=datetime.combine(expense_month, time.min),
                category=category,
                description=description,
                amount=amount,
                payment_method="transfer",
                reference_number=None,
                notes=note,
                created_by=current_user_id,
            )
            self.session.add(expense)
            result["created"] += 1
        return result

    def _import_tutor_payouts(self, path):
        rows = self._read_rows(path)
        result = {"created": 0, "updated": 0, "skipped": 0, "rows": len(rows)}
        occurrences = self._build_occurrence_indexes(
            rows,
            lambda row: (
                self._parse_period_label(row.get("no")),
                self.bulk._normalize_name(row.get("id tutor") or row.get("tutor")),
                self.bulk._parse_currency(row.get("nominal")),
            ),
        )

        for index, row in enumerate(rows, start=1):
            payout_month = self._parse_period_label(row.get("no"))
            tutor_code = self.bulk._normalize_name(row.get("id tutor"))
            tutor_name = self.bulk._normalize_name(row.get("tutor"))
            amount = self.bulk._parse_currency(row.get("nominal"))
            occurrence = occurrences[index - 1]
            if not payout_month or not tutor_name or amount <= 0:
                result["skipped"] += 1
                continue

            tutor = self._find_tutor_flexible(code=tutor_code, name=tutor_name)
            if not tutor:
                tutor = self.bulk._get_or_create_tutor(
                    tutor_code,
                    tutor_name,
                    bank_account_number=self.bulk._normalize_name(row.get("rekening")),
                    bank_name=self.bulk._normalize_name(row.get("bank")),
                    status="active",
                    is_active=True,
                )
            note = self._make_note(
                "tutor-payouts",
                f"{payout_month.isoformat()}|{tutor.tutor_code}|{int(amount)}|{occurrence}",
            )
            existing_line = TutorPayoutLine.query.filter_by(notes=note).first()
            if existing_line:
                payout = TutorPayout.query.get(existing_line.tutor_payout_id)
                if payout:
                    payout.amount = amount
                    payout.bank_name = (
                        self.bulk._normalize_name(row.get("bank")) or tutor.bank_name
                    )
                    payout.account_number = (
                        self.bulk._normalize_name(row.get("rekening"))
                        or tutor.bank_account_number
                    )
                    payout.notes = note
                result["updated"] += 1
                continue

            payout = TutorPayout(
                tutor_id=tutor.id,
                payout_date=datetime.combine(payout_month, time.min),
                amount=amount,
                bank_name=self.bulk._normalize_name(row.get("bank")) or tutor.bank_name,
                account_number=self.bulk._normalize_name(row.get("rekening"))
                or tutor.bank_account_number,
                payment_method="transfer",
                reference_number=f"LEGACY-TPO-{payout_month.strftime('%Y%m')}-{tutor.tutor_code[-6:]}-{occurrence}",
                notes=note,
                status="completed",
            )
            self.session.add(payout)
            self.session.flush()
            payout_line = TutorPayoutLine(
                tutor_payout_id=payout.id,
                service_month=payout_month,
                amount=amount,
                notes=note,
            )
            self.session.add(payout_line)
            result["created"] += 1
        return result
