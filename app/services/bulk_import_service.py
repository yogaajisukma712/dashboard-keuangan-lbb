"""
Bulk CSV import service for Dashboard Keuangan LBB Super Smart.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, time

from app import db
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    EnrollmentSchedule,
    Expense,
    Level,
    OtherIncome,
    PricingRule,
    Student,
    StudentPayment,
    StudentPaymentLine,
    Subject,
    Tutor,
    TutorPayout,
    TutorPayoutLine,
)


DATASET_DEFINITIONS = {
    "students": {
        "label": "Data Siswa",
        "sample_file": "Data Siswa.csv",
        "description": "Master siswa. Buat atau update siswa dari file CSV.",
    },
    "tutors": {
        "label": "Data Tutor",
        "sample_file": "Data Tutor.csv",
        "description": "Master tutor. Buat atau update tutor beserta rekeningnya.",
    },
    "pricing_rates": {
        "label": "Tarif Siswa",
        "sample_file": "Data Harga.csv",
        "description": "Tarif jual siswa dan default kuota per batch.",
    },
    "tutor_fees": {
        "label": "Fee Tutor",
        "sample_file": "Data Fee.csv",
        "description": "Fee tutor per kurikulum dan jenjang.",
    },
    "enrollments": {
        "label": "Enrollment + Jadwal",
        "sample_file": "Data Siswa, Jadwal, Catatan Sesi per bulan berjala.csv",
        "description": "Membangun enrollment aktif dan jadwal mingguan.",
    },
    "attendance": {
        "label": "Presensi Tutor",
        "sample_file": "Data Presensi Tutor.csv",
        "description": "Import presensi per sesi dan nominal tutor.",
    },
    "payments": {
        "label": "Pembayaran Siswa",
        "sample_file": "Data Pembayaran Siswa.csv",
        "description": "Import pembayaran siswa dan line item per mapel.",
    },
    "incomes": {
        "label": "Pemasukan Lain",
        "sample_file": "Data Pemasukan lain lain.csv",
        "description": "Import pemasukan non siswa.",
    },
    "expenses": {
        "label": "Pengeluaran",
        "sample_file": "Data Pengeluaran lain lain.csv",
        "description": "Import pengeluaran operasional.",
    },
    "tutor_payouts": {
        "label": "Rekap Transfer Tutor",
        "sample_file": "Data Presensi Tutor akumulasi.csv",
        "description": "Import payout tutor per bulan layanan.",
    },
}

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

DAY_NAME_MAP = {
    "senin": 0,
    "selasa": 1,
    "rabu": 2,
    "kamis": 3,
    "jumat": 4,
    "sabtu": 5,
    "minggu": 6,
    "ahad": 6,
}


class BulkImportService:
    """Import structured CSV datasets into application tables."""

    def __init__(self, session=None):
        self.session = session or db.session
        self._student_cache = {}
        self._tutor_cache = {}
        self._subject_cache = {}
        self._curriculum_cache = {}
        self._level_cache = {}
        self._pricing_cache = {}
        self._result = None

    def import_dataset(
        self,
        dataset_key,
        file_storage,
        current_user_id=None,
        service_month=None,
    ):
        if dataset_key not in DATASET_DEFINITIONS:
            raise ValueError("Tipe dataset tidak dikenali.")
        if not file_storage:
            raise ValueError("File CSV wajib diunggah.")

        rows = self._read_csv(file_storage)
        if not rows:
            raise ValueError("CSV kosong atau tidak memiliki baris data.")

        self._result = {
            "dataset_key": dataset_key,
            "dataset_label": DATASET_DEFINITIONS[dataset_key]["label"],
            "rows": len(rows),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "warnings": [],
        }

        handler = getattr(self, f"_import_{dataset_key}")
        handler(rows, current_user_id=current_user_id, service_month=service_month)
        return self._result

    def _read_csv(self, file_storage):
        payload = file_storage.read()
        if not payload:
            return []

        text = self._decode_csv_payload(payload)
        dialect = self._detect_csv_dialect(text)
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = []
        for raw_row in reader:
            row = {}
            for key, value in (raw_row or {}).items():
                clean_key = self._clean_header(key)
                if not clean_key:
                    continue
                row[clean_key] = (value or "").strip()
            if any(value for value in row.values()):
                rows.append(row)
        return rows

    def _decode_csv_payload(self, payload):
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8-sig", errors="replace")

    def _detect_csv_dialect(self, text):
        sample = "\n".join((text or "").splitlines()[:10]).strip()
        if not sample:
            return csv.excel
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;|\t")
        except csv.Error:
            return csv.excel

    def _clean_header(self, value):
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    def _normalize_name(self, value):
        return re.sub(r"\s+", " ", (value or "").strip())

    def _slug(self, value):
        slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
        return slug or "item"

    def _parse_currency(self, value):
        cleaned = re.sub(r"[^0-9-]", "", (value or "0"))
        if not cleaned or cleaned == "-":
            return 0.0
        return float(cleaned)

    def _parse_int(self, value, default=0):
        cleaned = re.sub(r"[^0-9-]", "", str(value or ""))
        if not cleaned or cleaned == "-":
            return default
        return int(cleaned)

    def _parse_bool(self, value):
        return str(value or "").strip().lower() in {"1", "true", "ya", "yes"}

    def _parse_datetime(self, value):
        text = (value or "").strip()
        if not text:
            return None
        for fmt in (
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        raise ValueError(f"Tanggal tidak valid: {value}")

    def _parse_month_name(self, value):
        month_num = MONTH_NAME_MAP.get((value or "").strip().lower())
        if not month_num:
            raise ValueError(f"Bulan tidak dikenal: {value}")
        return month_num

    def _parse_time(self, value):
        text = (value or "").strip()
        if not text:
            return None
        for fmt in ("%H:%M", "%H.%M", "%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).time()
            except ValueError:
                continue
        return None

    def _first_of_month(self, year, month):
        return date(int(year), int(month), 1)

    def _warn(self, message):
        self._result["warnings"].append(message)

    def _mark_created(self):
        self._result["created"] += 1

    def _mark_updated(self):
        self._result["updated"] += 1

    def _mark_skipped(self, message):
        self._result["skipped"] += 1
        self._warn(message)

    def _get_or_create_curriculum(self, name):
        key = self._normalize_name(name)
        if not key:
            return None
        cache_key = key.lower()
        if cache_key in self._curriculum_cache:
            return self._curriculum_cache[cache_key]
        curriculum = Curriculum.query.filter(
            db.func.lower(Curriculum.name) == cache_key
        ).first()
        if not curriculum:
            curriculum = Curriculum(name=key, is_active=True)
            self.session.add(curriculum)
            self.session.flush()
            self._mark_created()
        self._curriculum_cache[cache_key] = curriculum
        return curriculum

    def _get_or_create_level(self, name):
        key = self._normalize_name(name)
        if not key:
            return None
        cache_key = key.lower()
        if cache_key in self._level_cache:
            return self._level_cache[cache_key]
        level = Level.query.filter(db.func.lower(Level.name) == cache_key).first()
        if not level:
            level = Level(name=key, is_active=True)
            self.session.add(level)
            self.session.flush()
            self._mark_created()
        self._level_cache[cache_key] = level
        return level

    def _get_or_create_subject(self, name):
        key = self._normalize_name(name)
        if not key:
            return None
        cache_key = key.lower()
        if cache_key in self._subject_cache:
            return self._subject_cache[cache_key]
        subject = Subject.query.filter(db.func.lower(Subject.name) == cache_key).first()
        if not subject:
            subject = Subject(name=key, is_active=True)
            self.session.add(subject)
            self.session.flush()
            self._mark_created()
        self._subject_cache[cache_key] = subject
        return subject

    def _find_student(self, code=None, name=None):
        if code:
            cache_key = code.lower()
            if cache_key in self._student_cache:
                return self._student_cache[cache_key]
            student = Student.query.filter_by(student_code=code).first()
            if student:
                self._student_cache[cache_key] = student
                return student
        name_key = self._normalize_name(name)
        if name_key:
            student = Student.query.filter(
                db.func.lower(Student.name) == name_key.lower()
            ).first()
            if student and student.student_code:
                self._student_cache[student.student_code.lower()] = student
            return student
        return None

    def _find_tutor(self, code=None, name=None):
        if code:
            cache_key = code.lower()
            if cache_key in self._tutor_cache:
                return self._tutor_cache[cache_key]
            tutor = Tutor.query.filter_by(tutor_code=code).first()
            if tutor:
                self._tutor_cache[cache_key] = tutor
                return tutor
        name_key = self._normalize_name(name)
        if name_key:
            tutor = Tutor.query.filter(
                db.func.lower(Tutor.name) == name_key.lower()
            ).first()
            if tutor and tutor.tutor_code:
                self._tutor_cache[tutor.tutor_code.lower()] = tutor
            return tutor
        return None

    def _get_or_create_student(self, code, name, **attrs):
        code = self._normalize_name(code)
        student = self._find_student(code=code, name=name)
        if student:
            changed = False
            for key, value in attrs.items():
                if value not in (None, "") and getattr(student, key) != value:
                    setattr(student, key, value)
                    changed = True
            if name and student.name != name:
                student.name = name
                changed = True
            if changed:
                self._mark_updated()
            return student

        student = Student(
            student_code=code or f"IMP-STU-{self._slug(name)}",
            name=self._normalize_name(name) or code or "Siswa Import",
            status=attrs.pop("status", "active"),
            is_active=attrs.pop("is_active", True),
            **attrs,
        )
        self.session.add(student)
        self.session.flush()
        self._student_cache[student.student_code.lower()] = student
        self._mark_created()
        return student

    def _get_or_create_tutor(self, code, name, **attrs):
        code = self._normalize_name(code)
        tutor = self._find_tutor(code=code, name=name)
        if tutor:
            changed = False
            for key, value in attrs.items():
                if value not in (None, "") and getattr(tutor, key) != value:
                    setattr(tutor, key, value)
                    changed = True
            if name and tutor.name != name:
                tutor.name = name
                changed = True
            if changed:
                self._mark_updated()
            return tutor

        tutor = Tutor(
            tutor_code=code or f"IMP-TUT-{self._slug(name)}",
            name=self._normalize_name(name) or code or "Tutor Import",
            account_holder_name=attrs.get("account_holder_name") or self._normalize_name(name),
            status=attrs.pop("status", "active"),
            is_active=attrs.pop("is_active", True),
            **attrs,
        )
        self.session.add(tutor)
        self.session.flush()
        self._tutor_cache[tutor.tutor_code.lower()] = tutor
        self._mark_created()
        return tutor

    def _get_or_create_pricing(self, curriculum, level, subject=None):
        cache_key = (
            curriculum.id if curriculum else None,
            level.id if level else None,
            subject.id if subject else None,
        )
        if cache_key in self._pricing_cache:
            return self._pricing_cache[cache_key]

        query = PricingRule.query.filter_by(
            curriculum_id=curriculum.id if curriculum else None,
            level_id=level.id if level else None,
            subject_id=subject.id if subject else None,
        )
        pricing = query.order_by(PricingRule.id.asc()).first()
        self._pricing_cache[cache_key] = pricing
        return pricing

    def _match_pricing(self, curriculum, level, subject=None):
        pricing = self._get_or_create_pricing(curriculum, level, subject)
        if pricing or not subject:
            return pricing
        return self._get_or_create_pricing(curriculum, level, None)

    def _get_or_create_enrollment(
        self,
        student,
        subject,
        tutor,
        curriculum,
        level,
        grade,
        meeting_quota,
        student_rate,
        tutor_rate,
        start_date=None,
        status="active",
        notes=None,
    ):
        enrollment = Enrollment.query.filter_by(
            student_id=student.id,
            subject_id=subject.id,
            tutor_id=tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade=grade,
        ).first()

        if enrollment:
            changed = False
            updates = {
                "meeting_quota_per_month": meeting_quota,
                "student_rate_per_meeting": student_rate,
                "tutor_rate_per_meeting": tutor_rate,
                "status": status,
                "is_active": status == "active",
                "notes": notes or enrollment.notes,
            }
            if start_date and not enrollment.start_date:
                updates["start_date"] = start_date
            for key, value in updates.items():
                if value is not None and getattr(enrollment, key) != value:
                    setattr(enrollment, key, value)
                    changed = True
            if changed:
                self._mark_updated()
            return enrollment

        enrollment = Enrollment(
            student_id=student.id,
            subject_id=subject.id,
            tutor_id=tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
            grade=grade,
            meeting_quota_per_month=meeting_quota or 4,
            student_rate_per_meeting=student_rate or 0,
            tutor_rate_per_meeting=tutor_rate or 0,
            start_date=start_date or datetime.utcnow(),
            status=status,
            is_active=status == "active",
            notes=notes,
        )
        self.session.add(enrollment)
        self.session.flush()
        self._mark_created()
        return enrollment

    def _upsert_schedule(self, enrollment, day_label, time_label):
        day_text = self._normalize_name(day_label)
        time_obj = self._parse_time(time_label)
        if not day_text or not time_obj:
            return

        day_name = day_text.split()[-1].lower()
        day_index = DAY_NAME_MAP.get(day_name)
        if day_index is None:
            return

        schedule = EnrollmentSchedule.query.filter_by(
            enrollment_id=enrollment.id,
            day_of_week=day_index,
            start_time=time_obj,
        ).first()
        if schedule:
            return

        schedule = EnrollmentSchedule(
            enrollment_id=enrollment.id,
            day_of_week=day_index,
            day_name=day_name.capitalize(),
            start_time=time_obj,
            end_time=None,
            is_active=True,
        )
        self.session.add(schedule)
        self.session.flush()
        self._mark_created()

    def _import_students(self, rows, **_kwargs):
        for row in rows:
            student_code = row.get("id siswa")
            name = self._normalize_name(row.get("nama"))
            if not student_code or not name:
                self._mark_skipped("Baris siswa dilewati karena ID atau nama kosong.")
                continue

            curriculum = self._get_or_create_curriculum(row.get("kurikulum"))
            level = self._get_or_create_level(row.get("jenjang"))
            self._get_or_create_student(
                student_code,
                name,
                curriculum_id=curriculum.id if curriculum else None,
                level_id=level.id if level else None,
                grade=self._normalize_name(row.get("kelas")),
                status="active",
                is_active=True,
            )

    def _import_tutors(self, rows, **_kwargs):
        for row in rows:
            tutor_code = row.get("id tutor")
            name = self._normalize_name(row.get("nama"))
            if not tutor_code or not name:
                self._mark_skipped("Baris tutor dilewati karena ID atau nama kosong.")
                continue

            self._get_or_create_tutor(
                tutor_code,
                name,
                email=row.get("email"),
                bank_account_number=self._normalize_name(row.get("rekening")),
                bank_name=self._normalize_name(row.get("bank")),
                account_holder_name=name,
                status="active",
                is_active=True,
            )

    def _import_pricing_rates(self, rows, **_kwargs):
        for row in rows:
            curriculum = self._get_or_create_curriculum(row.get("kurikulum"))
            level = self._get_or_create_level(row.get("jenjang"))
            if not curriculum or not level:
                self._mark_skipped("Tarif siswa dilewati karena kurikulum atau jenjang kosong.")
                continue

            pricing = self._get_or_create_pricing(curriculum, level, None)
            student_rate = self._parse_currency(row.get("harga"))
            default_quota = self._parse_int(row.get("sesi / batch"), default=4)

            if pricing:
                pricing.student_rate_per_meeting = student_rate
                pricing.default_meeting_quota = default_quota or pricing.default_meeting_quota
                self._mark_updated()
                continue

            pricing = PricingRule(
                curriculum_id=curriculum.id,
                level_id=level.id,
                subject_id=None,
                student_rate_per_meeting=student_rate,
                tutor_rate_per_meeting=student_rate,
                default_meeting_quota=default_quota or 4,
                is_active=True,
            )
            self.session.add(pricing)
            self.session.flush()
            self._pricing_cache[(curriculum.id, level.id, None)] = pricing
            self._mark_created()

    def _import_tutor_fees(self, rows, **_kwargs):
        for row in rows:
            curriculum = self._get_or_create_curriculum(row.get("kurikulum"))
            level = self._get_or_create_level(row.get("jenjang"))
            if not curriculum or not level:
                self._mark_skipped("Fee tutor dilewati karena kurikulum atau jenjang kosong.")
                continue

            pricing = self._get_or_create_pricing(curriculum, level, None)
            tutor_rate = self._parse_currency(row.get("fee"))
            if pricing:
                pricing.tutor_rate_per_meeting = tutor_rate
                self._mark_updated()
                continue

            pricing = PricingRule(
                curriculum_id=curriculum.id,
                level_id=level.id,
                subject_id=None,
                student_rate_per_meeting=tutor_rate,
                tutor_rate_per_meeting=tutor_rate,
                default_meeting_quota=4,
                is_active=True,
            )
            self.session.add(pricing)
            self.session.flush()
            self._pricing_cache[(curriculum.id, level.id, None)] = pricing
            self._mark_created()

    def _import_enrollments(self, rows, **_kwargs):
        for row in rows:
            student_code = row.get("id siswa")
            student_name = self._normalize_name(row.get("nama siswa"))
            subject_name = self._normalize_name(row.get("mata pelajaran"))
            tutor_name = self._normalize_name(row.get("nama tutor"))
            tutor_code = self._normalize_name(row.get("id tutor"))

            if not student_code or not student_name or not subject_name or not tutor_name:
                self._mark_skipped("Enrollment dilewati karena siswa, mapel, atau tutor kosong.")
                continue

            curriculum = self._get_or_create_curriculum(row.get("kurikulum"))
            level = self._get_or_create_level(row.get("jenjang"))
            subject = self._get_or_create_subject(subject_name)
            student = self._get_or_create_student(
                student_code,
                student_name,
                curriculum_id=curriculum.id if curriculum else None,
                level_id=level.id if level else None,
                grade=self._normalize_name(row.get("kelas")),
                status="active",
                is_active=True,
            )
            tutor = self._get_or_create_tutor(
                tutor_code,
                tutor_name,
                email=row.get("email"),
                account_holder_name=tutor_name,
                status="active",
                is_active=True,
            )

            pricing = self._match_pricing(curriculum, level, subject)
            student_rate = float(pricing.student_rate_per_meeting) if pricing else 0
            tutor_rate = float(pricing.tutor_rate_per_meeting) if pricing else 0
            default_quota = (
                self._parse_int(row.get("jumlah pertemuan"), default=4)
                or (pricing.default_meeting_quota if pricing else 4)
            )

            start_date = None
            if row.get("tahun masuk") and row.get("bulan masuk"):
                try:
                    start_date = datetime.combine(
                        self._first_of_month(
                            self._parse_int(row.get("tahun masuk")),
                            self._parse_month_name(row.get("bulan masuk")),
                        ),
                        time.min,
                    )
                except Exception:
                    start_date = None

            status = "inactive" if self._parse_bool(row.get("tidak les")) else "active"
            enrollment = self._get_or_create_enrollment(
                student=student,
                subject=subject,
                tutor=tutor,
                curriculum=curriculum,
                level=level,
                grade=self._normalize_name(row.get("kelas")),
                meeting_quota=default_quota or 4,
                student_rate=student_rate,
                tutor_rate=tutor_rate,
                start_date=start_date,
                status=status,
                notes="Imported from bulk CSV enrollment dataset.",
            )
            self._upsert_schedule(enrollment, row.get("hari"), row.get("jam"))

    def _import_attendance(self, rows, **_kwargs):
        seen_attendance_keys = set()
        duplicate_attendance_counters = {}

        for index, row in enumerate(rows, start=1):
            session_at = self._parse_datetime(row.get("tanggal"))
            if not session_at:
                self._mark_skipped(f"Presensi baris {index} dilewati karena tanggal kosong.")
                continue

            student = self._find_student(name=row.get("siswa"))
            tutor = self._find_tutor(name=row.get("tutor"))
            curriculum = self._get_or_create_curriculum(row.get("kurikulum"))
            level = self._get_or_create_level(row.get("jenjang"))
            subject = self._get_or_create_subject(row.get("mapel"))

            if not student:
                self._mark_skipped(f"Presensi baris {index} dilewati karena siswa tidak ditemukan.")
                continue
            if not tutor:
                self._mark_skipped(f"Presensi baris {index} dilewati karena tutor tidak ditemukan.")
                continue

            enrollment = Enrollment.query.filter_by(
                student_id=student.id,
                subject_id=subject.id,
                tutor_id=tutor.id,
                status="active",
            ).first()
            if not enrollment:
                pricing = self._match_pricing(curriculum, level, subject)
                enrollment = self._get_or_create_enrollment(
                    student=student,
                    subject=subject,
                    tutor=tutor,
                    curriculum=curriculum,
                    level=level,
                    grade=student.grade,
                    meeting_quota=pricing.default_meeting_quota if pricing else 4,
                    student_rate=float(pricing.student_rate_per_meeting) if pricing else self._parse_currency(row.get("nominal")),
                    tutor_rate=float(pricing.tutor_rate_per_meeting) if pricing else self._parse_currency(row.get("nominal")),
                    start_date=session_at,
                    status="active",
                    notes="Auto-created from attendance import.",
                )

            base_note = "|".join(
                [
                    "Imported from tutor attendance CSV",
                    session_at.date().isoformat(),
                    str(student.id),
                    str(tutor.id),
                    str(subject.id),
                ]
            )
            note = base_note
            if base_note in seen_attendance_keys:
                duplicate_attendance_counters[base_note] += 1
                note = f"{base_note}|{duplicate_attendance_counters[base_note]}"
            else:
                seen_attendance_keys.add(base_note)
                duplicate_attendance_counters[base_note] = 1

            attendance = AttendanceSession.query.filter_by(notes=note).first()
            if not attendance and note == base_note:
                attendance = AttendanceSession.query.filter_by(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    tutor_id=tutor.id,
                    subject_id=subject.id,
                    session_date=session_at.date(),
                ).first()
            if attendance:
                attendance.status = "attended"
                attendance.student_present = True
                attendance.tutor_present = True
                attendance.tutor_fee_amount = self._parse_currency(row.get("nominal"))
                attendance.notes = note
                self._mark_updated()
                continue

            attendance = AttendanceSession(
                enrollment_id=enrollment.id,
                student_id=student.id,
                tutor_id=tutor.id,
                subject_id=subject.id,
                session_date=session_at.date(),
                status="attended",
                student_present=True,
                tutor_present=True,
                tutor_fee_amount=self._parse_currency(row.get("nominal")),
                notes=note,
            )
            self.session.add(attendance)
            self._mark_created()

    def _import_payments(self, rows, current_user_id=None, **_kwargs):
        payment_groups = {}

        for index, row in enumerate(rows, start=1):
            payment_at = self._parse_datetime(row.get("tanggal"))
            student_code = self._normalize_name(row.get("id siswa"))
            subject_name = self._normalize_name(row.get("mata pelajaran"))
            if not payment_at or not student_code or not subject_name:
                self._mark_skipped(f"Pembayaran baris {index} dilewati karena data utama kosong.")
                continue

            student = self._find_student(code=student_code, name=row.get("nama siswa"))
            if not student:
                student = self._get_or_create_student(
                    student_code,
                    row.get("nama siswa"),
                    curriculum_id=None,
                    level_id=None,
                    grade=self._normalize_name(row.get("kelas")),
                    status="active",
                    is_active=True,
                )

            subject = self._get_or_create_subject(subject_name)
            curriculum = self._get_or_create_curriculum(row.get("kurikulum"))
            level = self._get_or_create_level(row.get("jenjang"))
            enrollment = Enrollment.query.filter_by(
                student_id=student.id,
                subject_id=subject.id,
            ).order_by(Enrollment.id.desc()).first()
            if not enrollment:
                self._mark_skipped(
                    f"Pembayaran baris {index} dilewati karena enrollment untuk {student.name} / {subject.name} belum ada."
                )
                continue

            group_key = f"{student.student_code}|{payment_at.isoformat()}"
            payment = payment_groups.get(group_key)
            if not payment:
                receipt_number = f"IMP-PAY-{payment_at.strftime('%Y%m%d%H%M%S')}-{student.student_code[-6:]}"
                existing = StudentPayment.query.filter_by(receipt_number=receipt_number).first()
                if existing:
                    suffix = 2
                    while StudentPayment.query.filter_by(
                        receipt_number=f"{receipt_number}-{suffix}"
                    ).first():
                        suffix += 1
                    receipt_number = f"{receipt_number}-{suffix}"

                payment = StudentPayment(
                    student_id=student.id,
                    payment_date=payment_at,
                    receipt_number=receipt_number,
                    payment_method="bank_transfer",
                    total_amount=0,
                    notes="Imported from student payment CSV.",
                    is_verified=True,
                    verified_by=current_user_id,
                    verified_at=datetime.utcnow(),
                )
                self.session.add(payment)
                self.session.flush()
                payment_groups[group_key] = payment
                self._mark_created()

            meeting_count = self._parse_int(row.get("jumlah pertemuan"), default=0)
            nominal_amount = self._parse_currency(row.get("nominal"))
            tutor_payable = self._parse_currency(row.get("hutang gaji"))
            margin_amount = self._parse_currency(row.get("margin"))
            if meeting_count <= 0:
                self._mark_skipped(f"Pembayaran baris {index} dilewati karena jumlah pertemuan nol.")
                continue

            student_rate = nominal_amount / meeting_count if meeting_count else 0
            tutor_rate = tutor_payable / meeting_count if meeting_count else 0
            if float(enrollment.student_rate_per_meeting or 0) == 0 and student_rate:
                enrollment.student_rate_per_meeting = student_rate
            if float(enrollment.tutor_rate_per_meeting or 0) == 0 and tutor_rate:
                enrollment.tutor_rate_per_meeting = tutor_rate

            existing_line = StudentPaymentLine.query.filter_by(
                student_payment_id=payment.id,
                enrollment_id=enrollment.id,
                nominal_amount=nominal_amount,
                meeting_count=meeting_count,
            ).first()
            if existing_line:
                self._mark_updated()
                continue

            line = StudentPaymentLine(
                student_payment_id=payment.id,
                enrollment_id=enrollment.id,
                service_month=self._first_of_month(payment_at.year, payment_at.month),
                meeting_count=meeting_count,
                student_rate_per_meeting=student_rate,
                tutor_rate_per_meeting=tutor_rate,
                nominal_amount=nominal_amount,
                tutor_payable_amount=tutor_payable,
                margin_amount=margin_amount or (nominal_amount - tutor_payable),
                notes="Imported from payment CSV.",
            )
            self.session.add(line)
            payment.total_amount = float(payment.total_amount or 0) + nominal_amount
            self._mark_created()

    def _import_incomes(self, rows, current_user_id=None, **_kwargs):
        for index, row in enumerate(rows, start=1):
            description = self._normalize_name(row.get("deskripsi"))
            amount = self._parse_currency(row.get("nominal"))
            if not description or amount <= 0:
                self._mark_skipped(f"Pemasukan baris {index} dilewati karena deskripsi atau nominal tidak valid.")
                continue

            existing = OtherIncome.query.filter_by(
                description=description,
                amount=amount,
            ).first()
            if existing:
                self._mark_updated()
                continue

            category = description.split()[0][:50] if description else "Import"
            income = OtherIncome(
                income_date=datetime.utcnow(),
                category=category,
                description=description,
                amount=amount,
                notes="Imported from other income CSV.",
                created_by=current_user_id,
                is_active=True,
            )
            self.session.add(income)
            self._mark_created()

    def _import_expenses(self, rows, current_user_id=None, **_kwargs):
        for index, row in enumerate(rows, start=1):
            description = self._normalize_name(row.get("deskripsi"))
            amount = self._parse_currency(row.get("nominal"))
            if not description or amount <= 0:
                self._mark_skipped(f"Pengeluaran baris {index} dilewati karena deskripsi atau nominal tidak valid.")
                continue

            existing = Expense.query.filter_by(
                description=description,
                amount=amount,
            ).first()
            if existing:
                self._mark_updated()
                continue

            category = description.split()[0][:50] if description else "Import"
            expense = Expense(
                expense_date=datetime.utcnow(),
                category=category,
                description=description,
                amount=amount,
                payment_method="transfer",
                reference_number=None,
                notes="Imported from expense CSV.",
                created_by=current_user_id,
            )
            self.session.add(expense)
            self._mark_created()

    def _import_tutor_payouts(self, rows, service_month=None, **_kwargs):
        if not service_month:
            raise ValueError("Bulan layanan wajib diisi untuk import payout tutor.")

        try:
            year_text, month_text = service_month.split("-", 1)
            payout_month = self._first_of_month(int(year_text), int(month_text))
        except Exception as exc:
            raise ValueError("Format bulan layanan harus YYYY-MM.") from exc

        for index, row in enumerate(rows, start=1):
            tutor = self._get_or_create_tutor(
                self._normalize_name(row.get("id tutor")),
                row.get("tutor"),
                bank_account_number=self._normalize_name(row.get("rekening")),
                bank_name=self._normalize_name(row.get("bank")),
                account_holder_name=self._normalize_name(row.get("tutor")),
                status="active",
                is_active=True,
            )
            amount = self._parse_currency(row.get("nominal"))
            if amount <= 0:
                self._mark_skipped(f"Payout tutor baris {index} dilewati karena nominal tidak valid.")
                continue

            reference_number = f"IMP-TPO-{payout_month.strftime('%Y%m')}-{tutor.tutor_code[-6:]}"
            existing = TutorPayout.query.filter_by(
                tutor_id=tutor.id,
                reference_number=reference_number,
            ).first()
            if existing:
                self._mark_updated()
                continue

            payout = TutorPayout(
                tutor_id=tutor.id,
                payout_date=datetime.combine(payout_month, time.min),
                amount=amount,
                bank_name=tutor.bank_name,
                account_number=tutor.bank_account_number,
                payment_method="transfer",
                reference_number=reference_number,
                notes="Imported from tutor payout summary CSV.",
                status="completed",
            )
            self.session.add(payout)
            self.session.flush()

            payout_line = TutorPayoutLine(
                tutor_payout_id=payout.id,
                service_month=payout_month,
                amount=amount,
                notes="Imported from tutor payout summary CSV.",
            )
            self.session.add(payout_line)
            self._mark_created()
