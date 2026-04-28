"""
Script Import Data Februari 2025
Mengimpor semua data dari folder "Data Input Februari 2025" ke database.
Jalankan dengan: DATABASE_URL=postgresql://postgres:postgres@localhost:5433/lbb_db python3 import_februari_2025.py
"""

import csv
import os
import re
import sys
from datetime import date, datetime

os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/lbb_db"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data Input Februari 2025")

from decimal import Decimal

from app import create_app, db
from app.models.attendance import AttendanceSession
from app.models.closing import MonthlyClosing
from app.models.enrollment import Enrollment, EnrollmentSchedule
from app.models.expense import Expense
from app.models.income import OtherIncome
from app.models.master import Curriculum, Level, Student, Subject, Tutor
from app.models.payment import StudentPayment, StudentPaymentLine
from app.models.payroll import TutorPayout, TutorPayoutLine
from app.models.pricing import PricingRule


def parse_nominal(s):
    """Parse string nominal like 'Rp175,000' or 'Rp40.000' to int."""
    if not s:
        return 0
    s = str(s).strip()
    s = re.sub(r"[Rp\s]", "", s)
    s = s.replace(".", "").replace(",", "")
    try:
        return int(s)
    except ValueError:
        return 0


def read_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: get or create master data
# ─────────────────────────────────────────────────────────────────────────────


def get_or_create_curriculum(name):
    c = Curriculum.query.filter_by(name=name).first()
    if not c:
        c = Curriculum(name=name)
        db.session.add(c)
        db.session.flush()
    return c


def get_or_create_level(name):
    l = Level.query.filter_by(name=name).first()
    if not l:
        l = Level(name=name)
        db.session.add(l)
        db.session.flush()
    return l


def get_or_create_subject(name):
    s = Subject.query.filter_by(name=name).first()
    if not s:
        s = Subject(name=name)
        db.session.add(s)
        db.session.flush()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# 1. IMPORT PRICING RULES
# ─────────────────────────────────────────────────────────────────────────────


def import_pricing():
    print("\n=== Import Pricing Rules ===")
    harga_rows = read_csv("Data Harga.csv")
    fee_rows = read_csv("Data Fee.csv")

    # Build fee lookup: (kurikulum, jenjang) -> fee per sesi
    fee_map = {}
    for row in fee_rows:
        k = row["Kurikulum"].strip()
        j = row["Jenjang"].strip()
        fee_map[(k, j)] = int(row["fee"])

    count = 0
    for row in harga_rows:
        kurikulum = row["Kurikulum"].strip()
        jenjang = row["Jenjang"].strip()
        if not kurikulum or not jenjang:
            continue

        harga_sesi = int(row.get("harga", 0) or 0)
        fee_sesi = fee_map.get((kurikulum, jenjang), 0)

        curriculum = get_or_create_curriculum(kurikulum)
        level = get_or_create_level(jenjang)

        existing = PricingRule.query.filter_by(
            curriculum_id=curriculum.id, level_id=level.id, subject_id=None
        ).first()

        if existing:
            existing.student_rate_per_meeting = harga_sesi
            existing.tutor_rate_per_meeting = fee_sesi
        else:
            pr = PricingRule(
                curriculum_id=curriculum.id,
                level_id=level.id,
                student_rate_per_meeting=harga_sesi,
                tutor_rate_per_meeting=fee_sesi,
                default_meeting_quota=4,
            )
            db.session.add(pr)
            count += 1

    db.session.commit()
    print(f"  Pricing rules dibuat/diperbarui: {count + PricingRule.query.count()}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. IMPORT STUDENTS
# ─────────────────────────────────────────────────────────────────────────────


def import_students():
    print("\n=== Import Students ===")
    rows = read_csv("Data Siswa.csv")
    count_new = count_upd = 0

    for row in rows:
        student_code = str(row["Id Siswa"]).strip()
        name = row["Nama"].strip()
        kurikulum = row["Kurikulum"].strip()
        jenjang = row["Jenjang"].strip()
        kelas = str(row["Kelas"]).strip()

        curriculum = get_or_create_curriculum(kurikulum)
        level = get_or_create_level(jenjang)

        existing = Student.query.filter_by(student_code=student_code).first()
        if existing:
            existing.name = name
            existing.curriculum_id = curriculum.id
            existing.level_id = level.id
            existing.grade = kelas
            count_upd += 1
        else:
            s = Student(
                student_code=student_code,
                name=name,
                curriculum_id=curriculum.id,
                level_id=level.id,
                grade=kelas,
                status="active",
            )
            db.session.add(s)
            count_new += 1

    db.session.commit()
    print(f"  Siswa baru: {count_new}, diperbarui: {count_upd}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. IMPORT TUTORS
# ─────────────────────────────────────────────────────────────────────────────


def import_tutors():
    print("\n=== Import Tutors ===")
    rows = read_csv("Data Tutor.csv")
    count_new = count_upd = 0

    for row in rows:
        tutor_code = str(row["Id Tutor"]).strip()
        name = row["Nama"].strip()
        email = row.get("Email", "").strip()
        bank = row.get("Bank", "").strip()
        rekening = str(row.get("Rekening", "") or "").strip()
        mapel = row.get("Mapel", "").strip()

        existing = Tutor.query.filter_by(tutor_code=tutor_code).first()
        if existing:
            existing.name = name
            existing.email = email
            existing.bank_name = bank
            existing.bank_account_number = rekening
            count_upd += 1
        else:
            t = Tutor(
                tutor_code=tutor_code,
                name=name,
                email=email,
                bank_name=bank,
                bank_account_number=rekening,
                account_holder_name=name,
                status="active",
            )
            db.session.add(t)
            count_new += 1

    db.session.commit()
    print(f"  Tutor baru: {count_new}, diperbarui: {count_upd}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. IMPORT ENROLLMENTS + SCHEDULES
# ─────────────────────────────────────────────────────────────────────────────

DAY_MAP = {
    "01": 0,
    "senin": 0,
    "02": 1,
    "selasa": 1,
    "03": 2,
    "rabu": 2,
    "04": 3,
    "kamis": 3,
    "05": 4,
    "jumat": 4,
    "06": 5,
    "sabtu": 5,
    "07": 6,
    "minggu": 6,
}


def parse_day(hari_str):
    """Parse '01 Senin' -> 0, '07 Minggu' -> 6"""
    if not hari_str or not hari_str.strip():
        return None
    parts = hari_str.strip().split()
    if parts:
        num = parts[0].zfill(2)
        if num in DAY_MAP:
            return DAY_MAP[num]
        name = parts[-1].lower()
        if name in DAY_MAP:
            return DAY_MAP[name]
    return None


DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def get_pricing(curriculum_id, level_id):
    pr = PricingRule.query.filter_by(
        curriculum_id=curriculum_id, level_id=level_id, subject_id=None, is_active=True
    ).first()
    if pr:
        return float(pr.student_rate_per_meeting), float(pr.tutor_rate_per_meeting)
    return 0.0, 0.0


def import_enrollments():
    print("\n=== Import Enrollments + Schedules ===")
    rows = read_csv("Data Siswa, Jadwal, Catatan Sesi per bulan berjala.csv")
    count_new = count_upd = 0
    skipped = 0

    for row in rows:
        student_code = str(row["Id Siswa"]).strip()
        tutor_code = str(row["Id Tutor"]).strip() if row.get("Id Tutor") else ""
        mapel = row["Mata Pelajaran"].strip()
        kurikulum = row["Kurikulum"].strip()
        jenjang = row["Jenjang"].strip()
        kelas = str(row["Kelas"]).strip()
        hari_str = row.get("Hari", "").strip()
        jam_str = row.get("Jam", "").strip()
        jumlah_str = row.get("Jumlah Pertemuan", "0").strip()

        student = Student.query.filter_by(student_code=student_code).first()
        if not student:
            print(f"  [SKIP] Student tidak ditemukan: {student_code}")
            skipped += 1
            continue

        tutor = None
        if tutor_code:
            tutor = Tutor.query.filter_by(tutor_code=tutor_code).first()

        if not tutor:
            # Try to find by name from tutor name column
            tutor_name = row.get("Nama Tutor", "").strip()
            if tutor_name:
                tutor = Tutor.query.filter(Tutor.name.ilike(tutor_name)).first()

        if not tutor:
            print(
                f"  [SKIP] Tutor tidak ditemukan: {tutor_code} / {row.get('Nama Tutor', '')}"
            )
            skipped += 1
            continue

        curriculum = get_or_create_curriculum(kurikulum)
        level = get_or_create_level(jenjang)
        subject = get_or_create_subject(mapel)

        student_rate, tutor_rate = get_pricing(curriculum.id, level.id)

        try:
            quota = int(jumlah_str) if jumlah_str and jumlah_str not in ("", "-") else 4
        except ValueError:
            quota = 4
        quota = max(quota, 1) if quota > 0 else 4

        # Check existing enrollment
        existing = Enrollment.query.filter_by(
            student_id=student.id,
            subject_id=subject.id,
            tutor_id=tutor.id,
            curriculum_id=curriculum.id,
            level_id=level.id,
        ).first()

        if existing:
            existing.grade = kelas
            existing.meeting_quota_per_month = quota
            existing.student_rate_per_meeting = student_rate
            existing.tutor_rate_per_meeting = tutor_rate
            enr = existing
            count_upd += 1
        else:
            enr = Enrollment(
                student_id=student.id,
                subject_id=subject.id,
                tutor_id=tutor.id,
                curriculum_id=curriculum.id,
                level_id=level.id,
                grade=kelas,
                meeting_quota_per_month=quota,
                student_rate_per_meeting=student_rate,
                tutor_rate_per_meeting=tutor_rate,
                status="active",
            )
            db.session.add(enr)
            db.session.flush()
            count_new += 1

        # Schedule
        day_num = parse_day(hari_str)
        if day_num is not None and jam_str:
            try:
                hour, minute = jam_str.split(":")
                from datetime import time as dtime

                start_time = dtime(int(hour), int(minute))
                day_name = DAY_NAMES[day_num]

                # Check if schedule already exists
                existing_sched = EnrollmentSchedule.query.filter_by(
                    enrollment_id=enr.id, day_of_week=day_num, start_time=start_time
                ).first()

                if not existing_sched:
                    sched = EnrollmentSchedule(
                        enrollment_id=enr.id,
                        day_of_week=day_num,
                        day_name=day_name,
                        start_time=start_time,
                    )
                    db.session.add(sched)
            except Exception as e:
                pass

    db.session.commit()
    print(
        f"  Enrollment baru: {count_new}, diperbarui: {count_upd}, dilewati: {skipped}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. IMPORT PRESENSI TUTOR (Attendance Sessions)
# ─────────────────────────────────────────────────────────────────────────────


def parse_date_presensi(tanggal_str):
    """Parse tanggal '01/02/2025' -> date(2025,2,1)"""
    try:
        return datetime.strptime(tanggal_str.strip(), "%d/%m/%Y").date()
    except:
        return None


def get_fee_for_session(kurikulum, jenjang):
    """Get tutor fee per session from pricing rules."""
    curriculum = Curriculum.query.filter_by(name=kurikulum).first()
    level = Level.query.filter_by(name=jenjang).first()
    if not curriculum or not level:
        return 0
    pr = PricingRule.query.filter_by(
        curriculum_id=curriculum.id, level_id=level.id, subject_id=None, is_active=True
    ).first()
    return float(pr.tutor_rate_per_meeting) if pr else 0


def import_attendance():
    print("\n=== Import Presensi Tutor (Attendance Sessions) ===")
    rows = read_csv("Data Presensi Tutor.csv")

    # Clear all Feb 2025 attendance sessions to ensure fresh import
    feb_start = date(2025, 2, 1)
    feb_end = date(2025, 3, 1)
    deleted = AttendanceSession.query.filter(
        AttendanceSession.session_date >= feb_start,
        AttendanceSession.session_date < feb_end,
    ).delete(synchronize_session=False)
    db.session.flush()
    print(f"  Hapus {deleted} sesi lama Februari 2025")

    count_new = skipped = 0

    for row in rows:
        tanggal_str = row["Tanggal"].strip()
        tutor_name = row["Tutor"].strip()
        siswa_name = row["Siswa"].strip()
        kurikulum = row["Kurikulum"].strip()
        jenjang = row["Jenjang"].strip()
        mapel = row["Mapel"].strip()
        nominal_str = row["Nominal"].strip()

        session_date = parse_date_presensi(tanggal_str)
        if not session_date:
            skipped += 1
            continue

        # Resolve nominal from CSV (more accurate than computing from rules)
        nominal = parse_nominal(nominal_str)

        # Find tutor
        tutor = Tutor.query.filter(Tutor.name.ilike(tutor_name)).first()
        if not tutor:
            # try partial match
            tutor = Tutor.query.filter(Tutor.name.ilike(f"%{tutor_name}%")).first()
        if not tutor:
            print(f"  [SKIP] Tutor tidak ditemukan: {tutor_name}")
            skipped += 1
            continue

        # Find student (by name, case insensitive)
        student = Student.query.filter(Student.name.ilike(siswa_name)).first()
        if not student:
            student = Student.query.filter(
                Student.name.ilike(f"%{siswa_name}%")
            ).first()
        if not student:
            print(f"  [SKIP] Siswa tidak ditemukan: {siswa_name}")
            skipped += 1
            continue

        subject = get_or_create_subject(mapel)
        curriculum_obj = Curriculum.query.filter_by(name=kurikulum).first()
        level_obj = Level.query.filter_by(name=jenjang).first()

        # Find enrollment
        enr = None
        if curriculum_obj and level_obj:
            enr = Enrollment.query.filter_by(
                student_id=student.id,
                tutor_id=tutor.id,
                subject_id=subject.id,
                curriculum_id=curriculum_obj.id,
                level_id=level_obj.id,
            ).first()
            if not enr:
                # Try without subject constraint
                enr = Enrollment.query.filter_by(
                    student_id=student.id,
                    tutor_id=tutor.id,
                    curriculum_id=curriculum_obj.id,
                    level_id=level_obj.id,
                ).first()

        if not enr:
            # Try just student + tutor
            enr = Enrollment.query.filter_by(
                student_id=student.id,
                tutor_id=tutor.id,
            ).first()

        if not enr:
            # Create a minimal enrollment
            if curriculum_obj and level_obj:
                student_rate, tutor_rate = get_pricing(curriculum_obj.id, level_obj.id)
                enr = Enrollment(
                    student_id=student.id,
                    subject_id=subject.id,
                    tutor_id=tutor.id,
                    curriculum_id=curriculum_obj.id if curriculum_obj else None,
                    level_id=level_obj.id if level_obj else None,
                    grade="",
                    meeting_quota_per_month=4,
                    student_rate_per_meeting=student_rate,
                    tutor_rate_per_meeting=tutor_rate,
                    status="active",
                )
                db.session.add(enr)
                db.session.flush()
            else:
                skipped += 1
                continue

        # Insert attendance session (no dedup: same day can have multiple sessions)
        att = AttendanceSession(
            enrollment_id=enr.id,
            student_id=student.id,
            tutor_id=tutor.id,
            session_date=session_date,
            status="attended",
            student_present=True,
            tutor_present=True,
            subject_id=subject.id,
            tutor_fee_amount=nominal,
        )
        db.session.add(att)
        count_new += 1

    db.session.commit()
    print(f"  Sesi presensi baru: {count_new}, dilewati: {skipped}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. IMPORT PEMBAYARAN SISWA (Student Payments)
# ─────────────────────────────────────────────────────────────────────────────


def parse_date_payment(tanggal_str):
    """Parse '03/02/2025 8:40:04' or '15/02/2025'"""
    s = tanggal_str.strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except:
            continue
    return None


def import_payments():
    print("\n=== Import Pembayaran Siswa ===")
    rows = read_csv("Data Pembayaran Siswa.csv")

    # Group by (tanggal, student_code) to create one payment header per group
    from collections import defaultdict

    groups = defaultdict(list)
    for row in rows:
        key = (row["Tanggal"].strip(), row["Id Siswa"].strip())
        groups[key].append(row)

    # Clear existing Feb 2025 payments for fresh import
    feb_start = datetime(2025, 2, 1)
    feb_end = datetime(2025, 3, 1)
    existing_payments = StudentPayment.query.filter(
        StudentPayment.payment_date >= feb_start,
        StudentPayment.payment_date < feb_end,
        StudentPayment.receipt_number.like("INV/FEB2025/%"),
    ).all()
    for ep in existing_payments:
        # cascade deletes payment lines too
        db.session.delete(ep)
    db.session.flush()
    print(f"  Hapus {len(existing_payments)} payment lama Februari 2025")

    count_payments = count_lines = skipped = 0
    receipt_counter = 1

    for (tanggal_str, student_code), lines in sorted(groups.items()):
        payment_date = parse_date_payment(tanggal_str)
        if not payment_date:
            print(f"  [SKIP] Tanggal tidak valid: {tanggal_str}")
            skipped += 1
            continue

        student = Student.query.filter_by(student_code=student_code).first()
        if not student:
            print(f"  [SKIP] Siswa tidak ditemukan: {student_code}")
            skipped += 1
            continue

        # Build receipt number
        receipt_num = f"INV/FEB2025/{receipt_counter:04d}"

        total_nominal = sum(parse_nominal(r["Nominal"]) for r in lines)

        payment = StudentPayment(
            payment_date=payment_date,
            student_id=student.id,
            receipt_number=receipt_num,
            payment_method="bank_transfer",
            total_amount=total_nominal,
            notes=f"Import Februari 2025",
            is_verified=True,
        )
        db.session.add(payment)
        db.session.flush()
        receipt_counter += 1
        count_payments += 1

        for row in lines:
            kurikulum = row["Kurikulum"].strip()
            jenjang = (
                row["Jenjang "].strip()
                if "Jenjang " in row
                else row.get("Jenjang", "").strip()
            )
            mapel = row["Mata pelajaran"].strip()
            pertemuan = int(row["Jumlah pertemuan"])
            nominal = parse_nominal(row["Nominal"])
            hutang = parse_nominal(row["Hutang Gaji"])
            margin = parse_nominal(row["Margin"])

            curriculum_obj = Curriculum.query.filter_by(name=kurikulum).first()
            level_obj = Level.query.filter_by(name=jenjang).first()
            subject_obj = get_or_create_subject(mapel)

            # Find enrollment
            enr = None
            if curriculum_obj and level_obj:
                enr = Enrollment.query.filter_by(
                    student_id=student.id,
                    subject_id=subject_obj.id,
                    curriculum_id=curriculum_obj.id,
                    level_id=level_obj.id,
                ).first()
                if not enr:
                    enr = Enrollment.query.filter_by(
                        student_id=student.id,
                        curriculum_id=curriculum_obj.id,
                        level_id=level_obj.id,
                    ).first()

            if not enr:
                # Create minimal enrollment
                tutor_nominal_per = hutang // pertemuan if pertemuan > 0 else 0
                student_rate_per = nominal // pertemuan if pertemuan > 0 else 0
                if curriculum_obj and level_obj:
                    enr = Enrollment(
                        student_id=student.id,
                        subject_id=subject_obj.id,
                        tutor_id=None,
                        curriculum_id=curriculum_obj.id,
                        level_id=level_obj.id,
                        grade=str(
                            row.get("Kelas ", "").strip()
                            or row.get("Kelas", "").strip()
                        ),
                        meeting_quota_per_month=4,
                        student_rate_per_meeting=student_rate_per,
                        tutor_rate_per_meeting=tutor_nominal_per,
                        status="active",
                    )
                    db.session.add(enr)
                    db.session.flush()
                else:
                    print(
                        f"  [WARN] Tidak bisa membuat enrollment untuk {student_code} - {mapel}"
                    )
                    continue

            student_rate_per = nominal // pertemuan if pertemuan > 0 else 0
            tutor_rate_per = hutang // pertemuan if pertemuan > 0 else 0

            line = StudentPaymentLine(
                student_payment_id=payment.id,
                enrollment_id=enr.id,
                service_month=date(payment_date.year, payment_date.month, 1),
                meeting_count=pertemuan,
                student_rate_per_meeting=student_rate_per,
                tutor_rate_per_meeting=tutor_rate_per,
                nominal_amount=nominal,
                tutor_payable_amount=hutang,
                margin_amount=margin,
            )
            db.session.add(line)
            count_lines += 1

    db.session.commit()
    print(
        f"  Payment header: {count_payments}, payment lines: {count_lines}, dilewati: {skipped}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. IMPORT REKAP GAJI TUTOR (Tutor Payouts dari Akumulasi)
# ─────────────────────────────────────────────────────────────────────────────


def import_monthly_closing_jan():
    """
    Buat/perbarui MonthlyClosing Januari 2025 sebagai opening balance Februari.
    Data dari acuan: Grand Saldo Bulan Kemarin = Rp10.665.281
    """
    print("\n=== Import MonthlyClosing Januari 2025 ===")
    existing = MonthlyClosing.query.filter_by(month=1, year=2025).first()
    if existing:
        existing.closing_cash_balance = Decimal("10665281")
        existing.closing_tutor_payable = Decimal("3380000")
        existing.closing_profit = Decimal("7285281")
        existing.total_income = Decimal("60120000")
        existing.total_expense = Decimal("10376448")
        existing.total_tutor_salary = Decimal("7130000")
        existing.is_closed = True
        print("  MonthlyClosing Jan 2025 diperbarui.")
    else:
        jan_closing = MonthlyClosing(
            month=1,
            year=2025,
            opening_cash_balance=Decimal("0"),
            closing_cash_balance=Decimal("10665281"),
            opening_tutor_payable=Decimal("0"),
            closing_tutor_payable=Decimal("3380000"),
            closing_profit=Decimal("7285281"),
            total_income=Decimal("60120000"),
            total_expense=Decimal("10376448"),
            total_tutor_salary=Decimal("7130000"),
            is_closed=True,
            closed_at=datetime(2025, 1, 31, 23, 59),
        )
        db.session.add(jan_closing)
        print("  MonthlyClosing Jan 2025 dibuat.")
    db.session.commit()
    print(f"  Opening balance Februari 2025 = Rp10.665.281")


def import_tutor_payouts():
    print("\n=== Import Rekap Gaji Tutor (Akumulasi) ===")
    rows = read_csv("Data Presensi Tutor akumulasi.csv")

    # Clear existing Feb 2025 payout lines and headers for clean re-import
    feb_date = date(2025, 2, 1)
    existing_lines = TutorPayoutLine.query.filter_by(service_month=feb_date).all()
    deleted_payouts = set()
    for line in existing_lines:
        if line.tutor_payout_id not in deleted_payouts:
            payout = TutorPayout.query.get(line.tutor_payout_id)
            if payout:
                db.session.delete(payout)  # cascade deletes lines
                deleted_payouts.add(line.tutor_payout_id)
    db.session.flush()
    print(f"  Hapus {len(deleted_payouts)} payout lama Februari 2025")

    count = skipped = 0
    for row in rows:
        tutor_name = row["Tutor"].strip()
        tutor_code = str(row["ID Tutor"]).strip()
        nominal = parse_nominal(row["Nominal"])
        rekening = str(row.get("Rekening", "") or "").strip()
        bank = row.get("Bank", "").strip()

        tutor = Tutor.query.filter_by(tutor_code=tutor_code).first()
        if not tutor:
            tutor = Tutor.query.filter(Tutor.name.ilike(tutor_name)).first()
        if not tutor:
            print(f"  [SKIP] Tutor tidak ditemukan: {tutor_name} ({tutor_code})")
            skipped += 1
            continue

        payout = TutorPayout(
            tutor_id=tutor.id,
            payout_date=datetime(2025, 2, 28),
            amount=nominal,
            bank_name=bank or tutor.bank_name,
            account_number=rekening or tutor.bank_account_number,
            payment_method="transfer",
            notes="Import rekap gaji Februari 2025",
            status="completed",
        )
        db.session.add(payout)
        db.session.flush()

        payout_line = TutorPayoutLine(
            tutor_payout_id=payout.id,
            service_month=feb_date,
            amount=nominal,
            notes="Gaji Februari 2025",
        )
        db.session.add(payout_line)
        count += 1

    db.session.commit()
    print(f"  Tutor payouts: {count}, dilewati: {skipped}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. IMPORT PEMASUKAN LAIN-LAIN
# ─────────────────────────────────────────────────────────────────────────────


def import_other_incomes():
    print("\n=== Import Pemasukan Lain-Lain ===")
    rows = read_csv("Data Pemasukan lain lain.csv")

    # Clear existing Feb 2025 other incomes to avoid duplicates
    feb_start = datetime(2025, 2, 1)
    feb_end = datetime(2025, 3, 1)
    OtherIncome.query.filter(
        OtherIncome.income_date >= feb_start,
        OtherIncome.income_date < feb_end,
    ).delete(synchronize_session=False)
    db.session.flush()

    count = 0
    for row in rows:
        deskripsi = row["Deskripsi"].strip()
        nominal = parse_nominal(row["Nominal"])

        inc = OtherIncome(
            income_date=datetime(2025, 2, 1),
            category="lain-lain",
            description=deskripsi,
            amount=nominal,
        )
        db.session.add(inc)
        count += 1

    db.session.commit()
    print(f"  Pemasukan lain-lain: {count}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. IMPORT PENGELUARAN LAIN-LAIN
# ─────────────────────────────────────────────────────────────────────────────


def import_expenses():
    print("\n=== Import Pengeluaran Lain-Lain ===")
    rows = read_csv("Data Pengeluaran lain lain.csv")

    # Clear existing Feb 2025 expenses to avoid duplicates
    feb_start = datetime(2025, 2, 1)
    feb_end = datetime(2025, 3, 1)
    Expense.query.filter(
        Expense.expense_date >= feb_start,
        Expense.expense_date < feb_end,
    ).delete(synchronize_session=False)
    db.session.flush()

    count = 0
    for row in rows:
        deskripsi = row["Deskripsi"].strip()
        nominal = parse_nominal(row["Nominal"])

        # Determine category
        desc_lower = deskripsi.lower()
        if "iklan" in desc_lower:
            cat = "iklan"
        elif "kuota" in desc_lower:
            cat = "kuota"
        elif "tarik tunai" in desc_lower:
            cat = "tarik_tunai"
        elif "carger" in desc_lower or "charger" in desc_lower:
            cat = "peralatan"
        elif "tripod" in desc_lower:
            cat = "peralatan"
        else:
            cat = "lain-lain"

        exp = Expense(
            expense_date=datetime(2025, 2, 1),
            category=cat,
            description=deskripsi,
            amount=nominal,
        )
        db.session.add(exp)
        count += 1

    db.session.commit()
    print(f"  Pengeluaran: {count}")


# ─────────────────────────────────────────────────────────────────────────────
# VERIFY CALCULATIONS
# ─────────────────────────────────────────────────────────────────────────────


def verify_calculations():
    """
    Verifikasi kalkulasi Februari 2025 dibandingkan dengan acuan.
    Semua query difilter ke Februari 2025 saja agar tidak tercampur data historis.
    """
    print("\n=== Verifikasi Kalkulasi Februari 2025 ===")

    from sqlalchemy import extract, func

    FEB_MONTH = 2
    FEB_YEAR = 2025

    ACUAN = {
        "nominal": 13_700_000,
        "hutang_tutor": 9_610_000,
        "margin": 4_090_000,
        "fee_presensi": 9_045_000,
        "gaji_dibayar": 9_045_000,
        "pemasukan_lain": 25_000,
        "pengeluaran": 1_489_536,
        "grand_total_saldo": 22_900_745,  # opening(10_665_281) + income(13_700_000) + other(25_000) - exp(1_489_536)
        "grand_hutang_gaji": 12_990_000,  # 3_380_000 (Jan) + 9_610_000 (Feb)
        "grand_profit": 9_910_745,  # grand_total_saldo - grand_hutang_gaji
        "estimasi_sisa_saldo": 13_855_745,  # grand_total_saldo - fee_presensi
    }

    def check(label, got, expected, tol=1):
        ok = abs(float(got) - float(expected)) <= tol
        status = "✓ OK" if ok else "✗ MISMATCH"
        print(f"  {status}  {label}")
        print(
            f"         dapat Rp{float(got):,.0f}  |  ekspektasi Rp{float(expected):,.0f}"
            + (
                f"  |  selisih Rp{abs(float(got) - float(expected)):,.0f}"
                if not ok
                else ""
            )
        )
        return ok

    # ── Pembayaran Siswa (filter Feb 2025) ──
    total_nominal = (
        db.session.query(func.sum(StudentPaymentLine.nominal_amount))
        .join(StudentPayment)
        .filter(
            extract("month", StudentPayment.payment_date) == FEB_MONTH,
            extract("year", StudentPayment.payment_date) == FEB_YEAR,
        )
        .scalar()
        or 0
    )
    total_hutang_tutor = (
        db.session.query(func.sum(StudentPaymentLine.tutor_payable_amount))
        .join(StudentPayment)
        .filter(
            extract("month", StudentPayment.payment_date) == FEB_MONTH,
            extract("year", StudentPayment.payment_date) == FEB_YEAR,
        )
        .scalar()
        or 0
    )
    total_margin = (
        db.session.query(func.sum(StudentPaymentLine.margin_amount))
        .join(StudentPayment)
        .filter(
            extract("month", StudentPayment.payment_date) == FEB_MONTH,
            extract("year", StudentPayment.payment_date) == FEB_YEAR,
        )
        .scalar()
        or 0
    )

    print(f"\n  [Pembayaran Siswa - Februari 2025]")
    check("Total Nominal", total_nominal, ACUAN["nominal"])
    check("Total Hutang Tutor", total_hutang_tutor, ACUAN["hutang_tutor"])
    check("Total Margin", total_margin, ACUAN["margin"])
    n_ok = (
        abs(float(total_nominal) - (float(total_hutang_tutor) + float(total_margin)))
        < 1
    )
    print(f"  {'✓ OK' if n_ok else '✗ MISMATCH'}  Cek Nominal = Hutang + Margin")

    # ── Presensi Tutor (filter Feb 2025) ──
    total_fee_presensi = (
        db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
        .filter(
            extract("month", AttendanceSession.session_date) == FEB_MONTH,
            extract("year", AttendanceSession.session_date) == FEB_YEAR,
            AttendanceSession.status == "attended",
        )
        .scalar()
        or 0
    )

    # ── Tutor Payouts (filter Feb 2025 service month) ──
    feb_date = date(2025, 2, 1)
    total_payout = (
        db.session.query(func.sum(TutorPayoutLine.amount))
        .filter(TutorPayoutLine.service_month == feb_date)
        .scalar()
        or 0
    )

    print(f"\n  [Presensi & Gaji Tutor - Februari 2025]")
    check("Total Fee Presensi (accrual)", total_fee_presensi, ACUAN["fee_presensi"])
    check("Total Gaji Dibayarkan", total_payout, ACUAN["gaji_dibayar"])

    # ── Pemasukan & Pengeluaran Lain ──
    total_other_income = (
        db.session.query(func.sum(OtherIncome.amount))
        .filter(
            extract("month", OtherIncome.income_date) == FEB_MONTH,
            extract("year", OtherIncome.income_date) == FEB_YEAR,
        )
        .scalar()
        or 0
    )
    total_expense = (
        db.session.query(func.sum(Expense.amount))
        .filter(
            extract("month", Expense.expense_date) == FEB_MONTH,
            extract("year", Expense.expense_date) == FEB_YEAR,
        )
        .scalar()
        or 0
    )

    print(f"\n  [Pemasukan & Pengeluaran Lain - Februari 2025]")
    check("Pemasukan Lain-Lain", total_other_income, ACUAN["pemasukan_lain"])
    check("Pengeluaran Operasional", total_expense, ACUAN["pengeluaran"])

    # ── Grand KPI (pakai DashboardService) ──
    print(f"\n  [Grand KPI dari DashboardService]")
    try:
        from app.services.dashboard_service import DashboardService

        svc = DashboardService()
        opening = svc.get_opening_balance(FEB_MONTH, FEB_YEAR)
        grand_saldo = svc.get_cash_balance(FEB_MONTH, FEB_YEAR)
        grand_hutang = svc.get_grand_tutor_payable(FEB_MONTH, FEB_YEAR)
        grand_profit = svc.get_grand_profit(FEB_MONTH, FEB_YEAR)
        estimasi_sisa = svc.get_estimated_remaining_balance(FEB_MONTH, FEB_YEAR)

        check("Opening Balance (Saldo Bulan Kemarin)", opening, 10_665_281)
        check("Grand Total Saldo", grand_saldo, ACUAN["grand_total_saldo"])
        check("Grand Hutang Gaji (kumulatif)", grand_hutang, ACUAN["grand_hutang_gaji"])
        check("Grand Profit", grand_profit, ACUAN["grand_profit"])
        check("Estimasi Sisa Saldo", estimasi_sisa, ACUAN["estimasi_sisa_saldo"])
    except Exception as e:
        print(f"  [WARN] Tidak bisa load DashboardService: {e}")

    # ── Summary ──
    total_pemasukan = float(total_nominal) + float(total_other_income)
    total_pengeluaran = float(total_payout) + float(total_expense)
    kas_bersih = total_pemasukan - total_pengeluaran

    print(f"\n  === RINGKASAN KEUANGAN FEBRUARI 2025 ===")
    print(f"  Pemasukan Siswa     : Rp {float(total_nominal):>15,.0f}")
    print(f"  Pemasukan Lain-Lain : Rp {float(total_other_income):>15,.0f}")
    print(f"  Total Pemasukan     : Rp {total_pemasukan:>15,.0f}")
    print(f"  Gaji Tutor Dibayar  : Rp {float(total_payout):>15,.0f}")
    print(f"  Pengeluaran Lain    : Rp {float(total_expense):>15,.0f}")
    print(f"  Total Pengeluaran   : Rp {total_pengeluaran:>15,.0f}")
    print(f"  Kas Bersih Bulan Ini: Rp {kas_bersih:>15,.0f}")
    print(f"  Margin Lembaga      : Rp {float(total_margin):>15,.0f}")

    # ── Per tutor breakdown (Feb only) ──
    print(f"\n  === REKAP GAJI TUTOR (Februari 2025) ===")
    tutors = Tutor.query.all()
    grand_total_fee = 0
    for tutor in sorted(tutors, key=lambda t: t.name):
        fee = (
            db.session.query(func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.tutor_id == tutor.id,
                extract("month", AttendanceSession.session_date) == FEB_MONTH,
                extract("year", AttendanceSession.session_date) == FEB_YEAR,
                AttendanceSession.status == "attended",
            )
            .scalar()
            or 0
        )
        if fee > 0:
            print(f"  {tutor.name:<50} Rp {float(fee):>12,.0f}")
            grand_total_fee += float(fee)
    print(f"  {'':50} --------------------")
    print(f"  {'TOTAL':50} Rp {grand_total_fee:>12,.0f}")
    acuan_fee = ACUAN["fee_presensi"]
    ok_total = abs(grand_total_fee - acuan_fee) <= 1
    selisih_fee = abs(grand_total_fee - acuan_fee)
    hasil_fee = "✓ MATCH" if ok_total else f"✗ SELISIH Rp{selisih_fee:,.0f}"
    print(f"  Total vs Acuan (Rp9.045.000): {hasil_fee}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main():
    app = create_app("development")
    with app.app_context():
        print("=" * 60)
        print("  IMPORT DATA FEBRUARI 2025")
        print("=" * 60)

        import_pricing()
        import_students()
        import_tutors()
        import_enrollments()
        import_monthly_closing_jan()  # Opening balance Februari
        import_attendance()
        import_payments()
        import_tutor_payouts()
        import_other_incomes()
        import_expenses()
        verify_calculations()

        print("\n" + "=" * 60)
        print("  IMPORT SELESAI")
        print("=" * 60)


if __name__ == "__main__":
    main()
