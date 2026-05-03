"""
Helpers and ingest service for WhatsApp tutor attendance automation.
"""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from datetime import date, datetime

from flask import current_app

from app import db
from app.models import (
    AttendanceSession,
    Enrollment,
    Student,
    Subject,
    Tutor,
    WhatsAppContact,
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppGroupParticipant,
    WhatsAppMessage,
    WhatsAppStudentGroupValidation,
    WhatsAppStudentValidation,
    WhatsAppTutorValidation,
)


def normalize_person_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(part for part in text.split() if part)


def normalize_phone_number(value: str | None) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if digits.startswith("620"):
        return "62" + digits[3:]
    return digits


def normalize_group_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def get_excluded_group_names(raw_value: str | None = None) -> list[str]:
    if raw_value is None:
        raw_value = ""
        try:
            raw_value = current_app.config.get("WHATSAPP_EXCLUDED_GROUP_NAMES", "")
        except RuntimeError:
            raw_value = ""
        raw_value = raw_value or ""

    names: list[str] = []
    for candidate in re.split(r"[\n,]+", str(raw_value or "")):
        value = " ".join(candidate.strip().split())
        if value and value not in names:
            names.append(value)
    return names


def is_excluded_group_name(
    group_name: str | None, excluded_group_names: list[str] | None = None
) -> bool:
    normalized_group_name = normalize_group_name(group_name)
    if not normalized_group_name:
        return False
    names = excluded_group_names or get_excluded_group_names()
    normalized_excluded = {
        normalize_group_name(item) for item in names if normalize_group_name(item)
    }
    return normalized_group_name in normalized_excluded


def phone_number_variants(value: str | None) -> set[str]:
    normalized = normalize_phone_number(value)
    if not normalized:
        return set()
    variants = {normalized}
    if normalized.startswith("62") and len(normalized) > 2:
        variants.add("0" + normalized[2:])
    if normalized.startswith("0") and len(normalized) > 1:
        variants.add("62" + normalized[1:])
    return variants


def phone_numbers_match(left: str | None, right: str | None) -> bool:
    left_variants = phone_number_variants(left)
    right_variants = phone_number_variants(right)
    return bool(left_variants and right_variants and left_variants.intersection(right_variants))


def extract_group_invite_code(url: str | None) -> str | None:
    value = str(url or "").strip()
    match = re.search(r"chat\.whatsapp\.com/([A-Za-z0-9]+)", value)
    return match.group(1) if match else None


def find_best_name_match(target_name: str | None, candidates: list[dict]) -> dict | None:
    normalized_target = normalize_person_name(target_name)
    if not normalized_target:
        return None

    exact_match = None
    partial_match = None
    for candidate in candidates:
        normalized_candidate = normalize_person_name(candidate.get("name"))
        if not normalized_candidate:
            continue
        if normalized_candidate == normalized_target:
            exact_match = candidate
            break
        if (
            normalized_target in normalized_candidate
            or normalized_candidate in normalized_target
        ) and partial_match is None:
            partial_match = candidate
    return exact_match or partial_match


def collect_contact_name_variants(contact_payload: dict) -> list[str]:
    names: list[str] = []
    for candidate in [
        contact_payload.get("display_name"),
        contact_payload.get("push_name"),
        contact_payload.get("short_name"),
        *contact_payload.get("membership_names", []),
    ]:
        value = str(candidate or "").strip()
        if value and value not in names:
            names.append(value)
    return names


def build_student_contact_suggestions(
    contact_payload: dict, students: list[dict], limit: int = 3
) -> list[dict]:
    normalized_phone = normalize_phone_number(contact_payload.get("phone_number"))
    contact_names = collect_contact_name_variants(contact_payload)
    group_names = [
        str(value).strip()
        for value in contact_payload.get("group_names", [])
        if str(value or "").strip()
    ]
    historical_student_names = [
        str(value).strip()
        for value in contact_payload.get("historical_student_names", [])
        if str(value or "").strip()
    ]
    normalized_contact_names = [
        (value, normalize_person_name(value))
        for value in contact_names
        if normalize_person_name(value)
    ]
    normalized_group_names = [
        (value, normalize_person_name(value))
        for value in group_names
        if normalize_person_name(value)
    ]
    normalized_historical_names = [
        (value, normalize_person_name(value))
        for value in historical_student_names
        if normalize_person_name(value)
    ]

    suggestions: list[dict] = []
    for student in students:
        score = 0
        reasons: list[str] = []
        matched_group_names: list[str] = []

        student_name = str(student.get("name") or "").strip()
        normalized_student_name = normalize_person_name(student_name)
        if not normalized_student_name:
            continue

        student_phone = normalize_phone_number(student.get("phone"))
        parent_phone = normalize_phone_number(student.get("parent_phone"))
        if normalized_phone and student_phone and phone_numbers_match(normalized_phone, student_phone):
            score = 100
            reasons.append("Nomor WhatsApp sama dengan nomor siswa.")
        elif normalized_phone and parent_phone and phone_numbers_match(normalized_phone, parent_phone):
            score = 96
            reasons.append("Nomor WhatsApp sama dengan nomor orang tua siswa.")

        for original_contact_name, normalized_contact_name in normalized_contact_names:
            if normalized_contact_name == normalized_student_name:
                if score < 90:
                    score = 90
                reasons.append(
                    f"Nama kontak cocok langsung dengan siswa '{student_name}'."
                )
            elif (
                len(normalized_contact_name) >= 4
                and (
                    normalized_contact_name in normalized_student_name
                    or normalized_student_name in normalized_contact_name
                )
            ):
                if score < 72:
                    score = 72
                reasons.append(
                    f"Nama kontak '{original_contact_name}' mirip dengan siswa '{student_name}'."
                )

        for original_group_name, normalized_group_name in normalized_group_names:
            if normalized_student_name in normalized_group_name:
                if score < 84:
                    score = 84
                if original_group_name not in matched_group_names:
                    matched_group_names.append(original_group_name)
                reasons.append(
                    f"Nama group '{original_group_name}' memuat nama siswa '{student_name}'."
                )

        for historical_name, normalized_historical_name in normalized_historical_names:
            if normalized_historical_name == normalized_student_name:
                if score < 98:
                    score = 98
                reasons.append(
                    f"Nama siswa '{historical_name}' pernah muncul di evaluasi dari nomor ini."
                )
            elif (
                len(normalized_historical_name) >= 4
                and (
                    normalized_historical_name in normalized_student_name
                    or normalized_student_name in normalized_historical_name
                )
            ):
                if score < 82:
                    score = 82
                reasons.append(
                    f"Nama siswa historis '{historical_name}' mirip dengan siswa '{student_name}'."
                )

        if score <= 0:
            continue

        suggestions.append(
            {
                "student_id": student.get("id"),
                "student_name": student_name,
                "student_code": student.get("student_code"),
                "student_phone": student.get("phone"),
                "parent_phone": student.get("parent_phone"),
                "confidence": score,
                "matched_group_names": matched_group_names[:3],
                "reasons": reasons[:3],
            }
        )

    suggestions.sort(
        key=lambda item: (-item["confidence"], str(item.get("student_name") or "").lower())
    )
    return suggestions[:limit]


def build_student_group_suggestions(
    group_payload: dict, students: list[dict], limit: int = 3
) -> list[dict]:
    group_name = str(group_payload.get("group_name") or "").strip()
    normalized_group_name = normalize_person_name(group_name)
    historical_student_names = [
        str(value).strip()
        for value in group_payload.get("historical_student_names", [])
        if str(value or "").strip()
    ]
    normalized_historical_names = [
        (value, normalize_person_name(value))
        for value in historical_student_names
        if normalize_person_name(value)
    ]

    suggestions: list[dict] = []
    for student in students:
        student_name = str(student.get("name") or "").strip()
        normalized_student_name = normalize_person_name(student_name)
        if not normalized_student_name:
            continue

        score = 0
        reasons: list[str] = []
        matched_historical_names: list[str] = []

        if normalized_group_name:
            if normalized_group_name == normalized_student_name:
                score = 96
                reasons.append(
                    f"Nama group sama persis dengan siswa '{student_name}'."
                )
            elif (
                len(normalized_student_name) >= 4
                and (
                    normalized_student_name in normalized_group_name
                    or normalized_group_name in normalized_student_name
                )
            ):
                score = 82
                reasons.append(
                    f"Nama siswa '{student_name}' muncul di nama group '{group_name}'."
                )

        for historical_name, normalized_historical_name in normalized_historical_names:
            if normalized_historical_name == normalized_student_name:
                if score < 100:
                    score = 100
                matched_historical_names.append(historical_name)
                reasons.append(
                    f"Nama siswa '{historical_name}' pernah muncul pada evaluasi group ini."
                )
            elif (
                len(normalized_historical_name) >= 4
                and (
                    normalized_historical_name in normalized_student_name
                    or normalized_student_name in normalized_historical_name
                )
            ):
                if score < 88:
                    score = 88
                matched_historical_names.append(historical_name)
                reasons.append(
                    f"Nama siswa historis '{historical_name}' mirip dengan siswa '{student_name}'."
                )

        if score <= 0:
            continue

        suggestions.append(
            {
                "student_id": student.get("id"),
                "student_name": student_name,
                "student_code": student.get("student_code"),
                "student_phone": student.get("phone"),
                "parent_phone": student.get("parent_phone"),
                "confidence": score,
                "matched_historical_names": matched_historical_names[:3],
                "reasons": reasons[:3],
            }
        )

    suggestions.sort(
        key=lambda item: (-item["confidence"], str(item.get("student_name") or "").lower())
    )
    return suggestions[:limit]


def build_tutor_contact_suggestions(
    contact_payload: dict, tutors: list[dict], limit: int = 3
) -> list[dict]:
    normalized_phone = normalize_phone_number(contact_payload.get("phone_number"))
    contact_names = collect_contact_name_variants(contact_payload)
    historical_tutor_names = [
        str(value).strip()
        for value in contact_payload.get("historical_tutor_names", [])
        if str(value or "").strip()
    ]
    normalized_contact_names = []
    for contact_name in contact_names:
        normalized_name = normalize_person_name(contact_name)
        if normalized_name:
            normalized_contact_names.append((contact_name, normalized_name))
    normalized_historical_names = []
    for tutor_name in historical_tutor_names:
        normalized_name = normalize_person_name(tutor_name)
        if normalized_name:
            normalized_historical_names.append((tutor_name, normalized_name))

    suggestions: list[dict] = []
    for tutor in tutors:
        score = 0
        reasons: list[str] = []
        matched_label = None

        tutor_phone = normalize_phone_number(tutor.get("phone"))
        if normalized_phone and tutor_phone and phone_numbers_match(normalized_phone, tutor_phone):
            score = 100
            reasons.append("Nomor WhatsApp sama dengan nomor tutor.")

        tutor_name_variants = []
        for name_value in [tutor.get("name"), tutor.get("account_holder_name")]:
            normalized_tutor_name = normalize_person_name(name_value)
            if normalized_tutor_name:
                tutor_name_variants.append((str(name_value).strip(), normalized_tutor_name))

        for original_contact_name, normalized_contact_name in normalized_contact_names:
            for tutor_label, normalized_tutor_name in tutor_name_variants:
                if normalized_contact_name == normalized_tutor_name:
                    if score < 92:
                        score = 92
                        matched_label = tutor_label
                    reasons.append(
                        f"Nama kontak cocok langsung dengan tutor '{tutor_label}'."
                    )
                elif (
                    len(normalized_contact_name) >= 4
                    and len(normalized_tutor_name) >= 4
                    and (
                        normalized_contact_name in normalized_tutor_name
                        or normalized_tutor_name in normalized_contact_name
                    )
                ):
                    if score < 74:
                        score = 74
                        matched_label = tutor_label
                    reasons.append(
                        f"Nama kontak '{original_contact_name}' mirip dengan tutor '{tutor_label}'."
                    )

        for historical_name, normalized_historical_name in normalized_historical_names:
            for tutor_label, normalized_tutor_name in tutor_name_variants:
                if normalized_historical_name == normalized_tutor_name:
                    if score < 98:
                        score = 98
                        matched_label = tutor_label
                    reasons.append(
                        f"Nama tutor '{historical_name}' pernah muncul di evaluasi dari nomor ini."
                    )
                elif (
                    len(normalized_historical_name) >= 4
                    and len(normalized_tutor_name) >= 4
                    and (
                        normalized_historical_name in normalized_tutor_name
                        or normalized_tutor_name in normalized_historical_name
                    )
                ):
                    if score < 82:
                        score = 82
                        matched_label = tutor_label
                    reasons.append(
                        f"Nama tutor historis '{historical_name}' mirip dengan tutor '{tutor_label}'."
                    )

        if score <= 0:
            continue

        suggestions.append(
            {
                "tutor_id": tutor.get("id"),
                "tutor_name": tutor.get("name"),
                "tutor_phone": tutor.get("phone"),
                "confidence": score,
                "matched_label": matched_label,
                "reasons": reasons[:3],
            }
        )

    suggestions.sort(
        key=lambda item: (-item["confidence"], str(item.get("tutor_name") or "").lower())
    )
    return suggestions[:limit]


def resolve_attendance_date(message_sent_at: datetime, _reported_lesson_date: date | None) -> date:
    return message_sent_at.date()


def build_contact_group_membership_snapshot(
    contact: WhatsAppContact, excluded_group_names: list[str] | None = None
) -> tuple[list[dict], list[str], list[str]]:
    excluded_names = excluded_group_names or get_excluded_group_names()
    group_memberships: list[dict] = []
    excluded_hits: list[str] = []
    membership_names: list[str] = []

    for membership in contact.memberships.all():
        group = membership.group
        if group is None:
            continue
        group_name = str(group.name or "").strip()
        display_name = membership.display_name or contact.display_name
        if is_excluded_group_name(group_name, excluded_names):
            if group_name and group_name not in excluded_hits:
                excluded_hits.append(group_name)
            continue
        if display_name and display_name not in membership_names:
            membership_names.append(display_name)
        group_memberships.append(
            {
                "group_id": group.whatsapp_group_id,
                "group_name": group_name,
                "display_name": display_name,
                "is_admin": bool(membership.is_admin),
                "is_super_admin": bool(membership.is_super_admin),
            }
        )

    group_memberships.sort(key=lambda item: str(item.get("group_name") or "").lower())
    excluded_hits.sort(key=str.lower)
    return group_memberships, excluded_hits, membership_names


def serialize_tutor_validation(
    validation: WhatsAppTutorValidation | None,
) -> dict | None:
    if validation is None:
        return None
    return {
        "id": validation.id,
        "tutor_id": validation.tutor_id,
        "tutor_name": validation.tutor.name if validation.tutor else None,
        "phone_number": validation.validated_phone_number,
        "validated_contact_name": validation.validated_contact_name,
        "group_names": [
            item.get("group_name")
            for item in (validation.group_memberships_json or [])
            if item.get("group_name")
        ],
        "excluded_group_names": list(validation.excluded_group_names_json or []),
        "validated_at": (
            validation.validated_at.isoformat() if validation.validated_at else None
        ),
    }


def serialize_student_validation(
    validation: WhatsAppStudentValidation | None,
) -> dict | None:
    if validation is None:
        return None
    return {
        "id": validation.id,
        "student_id": validation.student_id,
        "student_name": validation.student.name if validation.student else None,
        "student_code": validation.student.student_code if validation.student else None,
        "phone_number": validation.validated_phone_number,
        "validated_contact_name": validation.validated_contact_name,
        "group_names": [
            item.get("group_name")
            for item in (validation.group_memberships_json or [])
            if item.get("group_name")
        ],
        "excluded_group_names": list(validation.excluded_group_names_json or []),
        "validated_at": (
            validation.validated_at.isoformat() if validation.validated_at else None
        ),
        "updated_phone_field": (
            (validation.validation_source_json or {}).get("updated_phone_field")
        ),
    }


def serialize_student_group_validation(
    validation: WhatsAppStudentGroupValidation | None,
) -> dict | None:
    if validation is None:
        return None
    return {
        "id": validation.id,
        "group_id": validation.group_id,
        "student_id": validation.student_id,
        "student_name": validation.student.name if validation.student else None,
        "student_code": validation.student.student_code if validation.student else None,
        "validated_at": (
            validation.validated_at.isoformat() if validation.validated_at else None
        ),
    }


def merge_student_group_memberships(
    existing_memberships: list[dict] | None,
    group: WhatsAppGroup,
) -> list[dict]:
    rows: list[dict] = [
        {
            "group_id": group.id,
            "whatsapp_group_id": group.whatsapp_group_id,
            "group_name": group.name,
        }
    ]
    seen_group_ids: set[int] = {group.id}

    for item in existing_memberships or []:
        if not isinstance(item, dict):
            continue
        group_id = item.get("group_id")
        whatsapp_group_id = str(item.get("whatsapp_group_id") or "").strip()
        group_name = str(item.get("group_name") or "").strip()
        if group_id is None or not whatsapp_group_id or not group_name:
            continue
        if int(group_id) in seen_group_ids:
            continue
        rows.append(
            {
                "group_id": int(group_id),
                "whatsapp_group_id": whatsapp_group_id,
                "group_name": group_name,
            }
        )
        seen_group_ids.add(int(group_id))

    return rows


def normalize_group_membership_item(item: dict | None) -> dict | None:
    if not isinstance(item, dict):
        return None
    raw_group_id = item.get("group_id")
    whatsapp_group_id = str(item.get("whatsapp_group_id") or "").strip()
    group_name = str(item.get("group_name") or "").strip()
    group_id: int | None = None
    if raw_group_id not in (None, ""):
        try:
            group_id = int(raw_group_id)
        except (TypeError, ValueError):
            if not whatsapp_group_id:
                whatsapp_group_id = str(raw_group_id).strip()
    if group_id is None and not whatsapp_group_id:
        return None
    return {
        "group_id": group_id,
        "whatsapp_group_id": whatsapp_group_id or None,
        "group_name": group_name or None,
    }


def get_student_group_memberships(student: Student | None) -> list[dict]:
    rows: list[dict] = []
    for item in (student.whatsapp_group_memberships_json if student else []) or []:
        normalized = normalize_group_membership_item(item)
        if normalized is not None:
            rows.append(normalized)
    return rows


def get_tutor_group_memberships(tutor: Tutor | None) -> list[dict]:
    if tutor is None:
        return []
    validation = WhatsAppTutorValidation.query.filter_by(tutor_id=tutor.id).first()
    rows: list[dict] = []
    for item in (validation.group_memberships_json if validation else []) or []:
        normalized = normalize_group_membership_item(item)
        if normalized is not None:
            rows.append(normalized)
    return rows


def get_enrollment_group_memberships(enrollment: Enrollment | None) -> list[dict]:
    if enrollment is None:
        return []

    rows: list[dict] = []
    seen_keys: set[tuple[object, object]] = set()
    for item in (enrollment.whatsapp_group_memberships_json or []) or []:
        normalized = normalize_group_membership_item(item)
        if normalized is None:
            continue
        key = (normalized.get("group_id"), normalized.get("whatsapp_group_id"))
        if key in seen_keys:
            continue
        rows.append(normalized)
        seen_keys.add(key)

    primary_group = normalize_group_membership_item(
        {
            "whatsapp_group_id": enrollment.whatsapp_group_id,
            "group_name": enrollment.whatsapp_group_name,
        }
    )
    if primary_group is not None:
        key = (primary_group.get("group_id"), primary_group.get("whatsapp_group_id"))
        if key not in seen_keys:
            rows.append(primary_group)

    return rows


def find_shared_group_memberships(
    student_group_memberships: list[dict],
    tutor_group_memberships: list[dict],
) -> list[dict]:
    tutor_by_whatsapp_id: dict[str, dict] = {}
    tutor_by_group_id: dict[int, dict] = {}
    for item in tutor_group_memberships:
        whatsapp_group_id = str(item.get("whatsapp_group_id") or "").strip()
        group_id = item.get("group_id")
        if whatsapp_group_id:
            tutor_by_whatsapp_id[whatsapp_group_id] = item
        if isinstance(group_id, int):
            tutor_by_group_id[group_id] = item

    matches: list[dict] = []
    seen_keys: set[tuple[object, object]] = set()
    for student_item in student_group_memberships:
        whatsapp_group_id = str(student_item.get("whatsapp_group_id") or "").strip()
        group_id = student_item.get("group_id")
        tutor_item = None
        if whatsapp_group_id and whatsapp_group_id in tutor_by_whatsapp_id:
            tutor_item = tutor_by_whatsapp_id[whatsapp_group_id]
        elif isinstance(group_id, int) and group_id in tutor_by_group_id:
            tutor_item = tutor_by_group_id[group_id]
        if tutor_item is None:
            continue
        match = {
            "group_id": student_item.get("group_id") or tutor_item.get("group_id"),
            "whatsapp_group_id": (
                student_item.get("whatsapp_group_id")
                or tutor_item.get("whatsapp_group_id")
            ),
            "group_name": student_item.get("group_name") or tutor_item.get("group_name"),
        }
        key = (match.get("group_id"), match.get("whatsapp_group_id"))
        if key in seen_keys:
            continue
        matches.append(match)
        seen_keys.add(key)
    return matches


def find_matching_enrollment_group(
    enrollment: Enrollment | None, group: WhatsAppGroup | None
) -> dict | None:
    if enrollment is None or group is None:
        return None

    target_whatsapp_group_id = str(group.whatsapp_group_id or "").strip()
    target_group_id = group.id
    for item in get_enrollment_group_memberships(enrollment):
        whatsapp_group_id = str(item.get("whatsapp_group_id") or "").strip()
        group_id = item.get("group_id")
        if target_whatsapp_group_id and whatsapp_group_id == target_whatsapp_group_id:
            return item
        if isinstance(group_id, int) and group_id == target_group_id:
            return item
    return None


class WhatsAppIngestService:
    @staticmethod
    def get_excluded_group_names() -> list[str]:
        return get_excluded_group_names()

    @staticmethod
    def list_active_students() -> list[dict]:
        students = [
            {
                "id": student.id,
                "name": student.name,
                "student_code": student.student_code,
                "grade": student.grade,
                "phone": student.phone,
                "parent_phone": student.parent_phone,
            }
            for student in Student.query.filter_by(is_active=True).all()
        ]
        students.sort(key=lambda item: str(item.get("name") or "").lower())
        return students

    @staticmethod
    def list_active_tutors() -> list[dict]:
        tutors = [
            {
                "id": tutor.id,
                "name": tutor.name,
                "phone": tutor.phone,
                "account_holder_name": tutor.account_holder_name,
            }
            for tutor in Tutor.query.filter_by(is_active=True).all()
        ]
        tutors.sort(key=lambda item: str(item.get("name") or "").lower())
        return tutors

    @staticmethod
    def sync_enrollment_whatsapp_group(enrollment: Enrollment) -> dict:
        student = enrollment.student or db.session.get(Student, enrollment.student_id)
        tutor = enrollment.tutor or db.session.get(Tutor, enrollment.tutor_id)
        shared_groups = find_shared_group_memberships(
            get_student_group_memberships(student),
            get_tutor_group_memberships(tutor),
        )
        if not shared_groups:
            enrollment.whatsapp_group_id = None
            enrollment.whatsapp_group_name = None
            enrollment.whatsapp_group_memberships_json = []
            return {"matched": False, "groups": []}

        primary_group = shared_groups[0]
        enrollment.whatsapp_group_id = str(primary_group.get("whatsapp_group_id") or "")
        enrollment.whatsapp_group_name = str(primary_group.get("group_name") or "")
        enrollment.whatsapp_group_memberships_json = shared_groups
        return {"matched": True, "groups": shared_groups}

    @staticmethod
    def sync_enrollments_for_student(student_id: int) -> list[dict]:
        rows: list[dict] = []
        for enrollment in Enrollment.query.filter_by(student_id=student_id).all():
            result = WhatsAppIngestService.sync_enrollment_whatsapp_group(enrollment)
            rows.append(
                {
                    "enrollment_id": enrollment.id,
                    "matched": result["matched"],
                    "whatsapp_group_id": enrollment.whatsapp_group_id,
                    "whatsapp_group_name": enrollment.whatsapp_group_name,
                    "whatsapp_group_memberships": list(
                        enrollment.whatsapp_group_memberships_json or []
                    ),
                }
            )
        return rows

    @staticmethod
    def sync_enrollments_for_tutor(tutor_id: int) -> list[dict]:
        rows: list[dict] = []
        for enrollment in Enrollment.query.filter_by(tutor_id=tutor_id).all():
            result = WhatsAppIngestService.sync_enrollment_whatsapp_group(enrollment)
            rows.append(
                {
                    "enrollment_id": enrollment.id,
                    "matched": result["matched"],
                    "whatsapp_group_id": enrollment.whatsapp_group_id,
                    "whatsapp_group_name": enrollment.whatsapp_group_name,
                    "whatsapp_group_memberships": list(
                        enrollment.whatsapp_group_memberships_json or []
                    ),
                }
            )
        return rows

    @staticmethod
    def find_validated_tutor_by_phone(
        author_phone_number: str | None,
    ) -> WhatsAppTutorValidation | None:
        normalized_phone = normalize_phone_number(author_phone_number)
        if not normalized_phone:
            return None

        for validation in WhatsAppTutorValidation.query.all():
            if phone_numbers_match(validation.validated_phone_number, normalized_phone):
                return validation
        return None

    @staticmethod
    def match_entities_from_group_context(
        evaluation: WhatsAppEvaluation,
        author_phone_number: str | None,
    ) -> dict:
        fallback = WhatsAppIngestService.match_entities(
            evaluation.student_name,
            evaluation.tutor_name,
            evaluation.subject_name,
            author_phone_number,
        )
        group = evaluation.group
        validation = WhatsAppIngestService.find_validated_tutor_by_phone(
            author_phone_number
        )

        if group is None or validation is None or validation.tutor is None:
            return fallback

        tutor = validation.tutor
        candidates = [
            enrollment
            for enrollment in Enrollment.query.filter_by(status="active").all()
            if find_matching_enrollment_group(enrollment, group) is not None
        ]
        if not candidates:
            return {
                "student": fallback["student"],
                "tutor": tutor,
                "subject": fallback["subject"],
                "enrollment": None,
                "confidence": 40,
                "status": "unmatched",
                "note": (
                    "Tutor matched from validated WhatsApp number, "
                    "but no active enrollment shares this WhatsApp group."
                ),
            }

        filtered_candidates = list(candidates)
        matched_student = None
        student_match = find_best_name_match(
            evaluation.student_name,
            [
                {
                    "id": enrollment.id,
                    "name": enrollment.student.name if enrollment.student else None,
                    "obj": enrollment,
                }
                for enrollment in filtered_candidates
                if enrollment.student is not None
            ],
        )
        if student_match is not None:
            filtered_candidates = [student_match["obj"]]
            matched_student = student_match["obj"].student

        matched_subject = WhatsAppIngestService.find_subject(evaluation.subject_name)
        if matched_subject is not None:
            subject_filtered = [
                enrollment
                for enrollment in filtered_candidates
                if enrollment.subject_id == matched_subject.id
            ]
            if subject_filtered:
                filtered_candidates = subject_filtered

        tutor_owned_candidates = [
            enrollment
            for enrollment in filtered_candidates
            if enrollment.tutor_id == tutor.id
        ]
        if len(tutor_owned_candidates) == 1:
            filtered_candidates = tutor_owned_candidates

        if len(filtered_candidates) == 1:
            selected = filtered_candidates[0]
            return {
                "student": matched_student or selected.student or fallback["student"],
                "tutor": tutor,
                "subject": matched_subject or selected.subject or fallback["subject"],
                "enrollment": selected,
                "confidence": 99,
                "status": "matched",
                "note": (
                    "Enrollment matched from validated tutor WhatsApp number "
                    "and WhatsApp group."
                ),
            }

        if len(filtered_candidates) > 1:
            return {
                "student": matched_student or fallback["student"],
                "tutor": tutor,
                "subject": matched_subject or fallback["subject"],
                "enrollment": None,
                "confidence": 65,
                "status": "ambiguous",
                "note": (
                    "Multiple active enrollments share this WhatsApp group for the sender tutor."
                ),
            }

        return fallback

    @staticmethod
    def find_existing_attendance_for_whatsapp_identity(
        enrollment: Enrollment,
        evaluation: WhatsAppEvaluation,
        matched_tutor: Tutor | None,
    ) -> AttendanceSession | None:
        if evaluation.attendance_session is not None:
            return evaluation.attendance_session

        tutor_id = matched_tutor.id if matched_tutor is not None else enrollment.tutor_id
        author_phone_number = normalize_phone_number(
            evaluation.message.author_phone_number if evaluation.message else None
        )
        related_evaluations = (
            WhatsAppEvaluation.query.join(WhatsAppMessage, WhatsAppEvaluation.message_id == WhatsAppMessage.id)
            .filter(
                WhatsAppEvaluation.id != evaluation.id,
                WhatsAppEvaluation.group_id == evaluation.group_id,
                WhatsAppEvaluation.attendance_date == evaluation.attendance_date,
                WhatsAppEvaluation.matched_enrollment_id == enrollment.id,
                WhatsAppEvaluation.matched_tutor_id == tutor_id,
                WhatsAppEvaluation.attendance_session_id.isnot(None),
            )
            .order_by(WhatsAppEvaluation.id.asc())
            .all()
        )
        for candidate in related_evaluations:
            candidate_phone_number = normalize_phone_number(
                candidate.message.author_phone_number if candidate.message else None
            )
            if not phone_numbers_match(author_phone_number, candidate_phone_number):
                continue
            if candidate.attendance_session is not None:
                return candidate.attendance_session

        return (
            AttendanceSession.query.filter(
                AttendanceSession.enrollment_id == enrollment.id,
                AttendanceSession.tutor_id == tutor_id,
                db.func.date(AttendanceSession.session_date) == evaluation.attendance_date,
                AttendanceSession.status == "attended",
            )
            .order_by(AttendanceSession.id.asc())
            .first()
        )

    @staticmethod
    def refresh_evaluation_attendance_link(
        evaluation: WhatsAppEvaluation,
    ) -> dict:
        author_phone_number = (
            evaluation.message.author_phone_number if evaluation.message else None
        )
        matches = WhatsAppIngestService.match_entities_from_group_context(
            evaluation,
            author_phone_number,
        )

        if matches["enrollment"] is None and evaluation.attendance_session is not None:
            return {
                "attendance_linked": False,
                "status": "preserved-existing-link",
                "notes": "Existing attendance link preserved.",
            }

        evaluation.matched_student_id = matches["student"].id if matches["student"] else None
        evaluation.matched_tutor_id = matches["tutor"].id if matches["tutor"] else None
        evaluation.matched_subject_id = matches["subject"].id if matches["subject"] else None
        evaluation.matched_enrollment_id = (
            matches["enrollment"].id if matches["enrollment"] else None
        )
        evaluation.confidence_score = matches["confidence"]
        evaluation.match_status = matches["status"]
        evaluation.notes = matches["note"]

        attendance_linked = False
        if matches["enrollment"] is not None:
            attendance = WhatsAppIngestService.link_or_create_attendance(
                matches["enrollment"], evaluation, matched_tutor=matches["tutor"]
            )
            if attendance is not None:
                evaluation.attendance_session = attendance
                attendance_linked = True
                evaluation.match_status = "attendance-linked"
        return {
            "attendance_linked": attendance_linked,
            "status": evaluation.match_status,
            "notes": evaluation.notes,
        }

    @staticmethod
    def scan_attendance_for_month(month: int, year: int) -> dict:
        if month < 1 or month > 12:
            raise ValueError("Bulan scan presensi WhatsApp tidak valid.")
        if year < 2000 or year > 2100:
            raise ValueError("Tahun scan presensi WhatsApp tidak valid.")

        period_start = date(year, month, 1)
        period_end = date(year, month, monthrange(year, month)[1])
        evaluations = (
            WhatsAppEvaluation.query.filter(
                WhatsAppEvaluation.attendance_date.between(period_start, period_end)
            )
            .order_by(
                WhatsAppEvaluation.attendance_date.asc(),
                WhatsAppEvaluation.id.asc(),
            )
            .all()
        )

        summary = {
            "month": month,
            "year": year,
            "processed_evaluations": len(evaluations),
            "linked_attendance": 0,
            "already_linked": 0,
            "ambiguous": 0,
            "unmatched": 0,
            "matched_without_link": 0,
        }

        for evaluation in evaluations:
            if evaluation.attendance_session is not None:
                summary["already_linked"] += 1
            result = WhatsAppIngestService.refresh_evaluation_attendance_link(evaluation)
            status = result["status"]
            if result["attendance_linked"]:
                summary["linked_attendance"] += 1
            elif status == "ambiguous":
                summary["ambiguous"] += 1
            elif status == "unmatched":
                summary["unmatched"] += 1
            elif status == "matched":
                summary["matched_without_link"] += 1

        db.session.commit()
        return summary

    @staticmethod
    def list_groups_with_student_suggestions(limit_per_group: int = 3) -> list[dict]:
        excluded_group_names = get_excluded_group_names()
        students = WhatsAppIngestService.list_active_students()
        groups = WhatsAppGroup.query.order_by(WhatsAppGroup.id.asc()).all()
        message_counts = {
            int(group_id): int(total)
            for group_id, total in db.session.query(
                WhatsAppMessage.group_id, db.func.count(WhatsAppMessage.id)
            )
            .group_by(WhatsAppMessage.group_id)
            .all()
        }
        evaluation_counts = {
            int(group_id): int(total)
            for group_id, total in db.session.query(
                WhatsAppEvaluation.group_id, db.func.count(WhatsAppEvaluation.id)
            )
            .group_by(WhatsAppEvaluation.group_id)
            .all()
        }
        linked_attendance_counts = {
            int(group_id): int(total)
            for group_id, total in db.session.query(
                WhatsAppEvaluation.group_id, db.func.count(WhatsAppEvaluation.id)
            )
            .filter(WhatsAppEvaluation.attendance_session_id.isnot(None))
            .group_by(WhatsAppEvaluation.group_id)
            .all()
        }

        historical_student_names_by_group_id: dict[int, list[str]] = {}
        for evaluation in WhatsAppEvaluation.query.all():
            if evaluation.group_id is None:
                continue
            student_name = str(evaluation.student_name or "").strip()
            if not student_name:
                continue
            historical_student_names_by_group_id.setdefault(evaluation.group_id, [])
            if (
                student_name
                not in historical_student_names_by_group_id[evaluation.group_id]
            ):
                historical_student_names_by_group_id[evaluation.group_id].append(
                    student_name
                )

        validations_by_group_id = {
            item.group_id: item for item in WhatsAppStudentGroupValidation.query.all()
        }

        rows: list[dict] = []
        for group in groups:
            if is_excluded_group_name(group.name, excluded_group_names):
                continue
            metadata = group.metadata_json or {}
            sync_metadata = metadata.get("sync") if isinstance(metadata, dict) else {}
            fetched_count = int((sync_metadata or {}).get("fetched_message_count") or 0)
            db_message_count = message_counts.get(group.id, 0)
            sync_gap = max(0, fetched_count - db_message_count)

            group_payload = {
                "group_id": group.id,
                "whatsapp_group_id": group.whatsapp_group_id,
                "group_name": group.name,
                "participant_count": group.participant_count,
                "message_count": db_message_count,
                "evaluation_count": evaluation_counts.get(group.id, 0),
                "linked_attendance_count": linked_attendance_counts.get(group.id, 0),
                "last_synced_at": (
                    group.last_synced_at.isoformat() if group.last_synced_at else None
                ),
                "sync_scan": {
                    "scan_mode": (sync_metadata or {}).get("scan_mode"),
                    "scanned_at": (sync_metadata or {}).get("scanned_at"),
                    "requested_limit": (sync_metadata or {}).get("requested_limit"),
                    "fetched_message_count": fetched_count,
                    "db_message_count": db_message_count,
                    "sync_gap": sync_gap,
                    "relevant_message_count": (sync_metadata or {}).get(
                        "relevant_message_count"
                    ),
                    "first_fetched_message_at": (sync_metadata or {}).get(
                        "first_fetched_message_at"
                    ),
                    "last_fetched_message_at": (sync_metadata or {}).get(
                        "last_fetched_message_at"
                    ),
                    "possibly_truncated": bool(
                        (sync_metadata or {}).get("possibly_truncated")
                    ),
                    "coverage_note": (sync_metadata or {}).get("coverage_note"),
                    "status": (
                        "pending-db"
                        if sync_gap > 0
                        else "limited"
                        if (sync_metadata or {}).get("possibly_truncated")
                        else "synced"
                        if fetched_count
                        else "unknown"
                    ),
                },
                "historical_student_names": historical_student_names_by_group_id.get(
                    group.id, []
                ),
            }
            rows.append(
                {
                    **group_payload,
                    "validated_student": serialize_student_group_validation(
                        validations_by_group_id.get(group.id)
                    ),
                    "suggested_students": build_student_group_suggestions(
                        group_payload, students, limit=limit_per_group
                    ),
                    "last_message_at": (
                        group.last_message_at.isoformat() if group.last_message_at else None
                    ),
                }
            )

        rows.sort(
            key=lambda item: (
                -(item["suggested_students"][0]["confidence"] if item["suggested_students"] else 0),
                str(item.get("group_name") or "").lower(),
                str(item.get("whatsapp_group_id") or ""),
            )
        )
        return rows

    @staticmethod
    def ingest_sync_payload(payload: dict) -> dict:
        excluded_group_names = get_excluded_group_names()
        groups = [
            item
            for item in payload.get("groups", [])
            if item.get("whatsapp_group_id")
            and not is_excluded_group_name(item.get("name"), excluded_group_names)
        ]
        allowed_group_ids = {item["whatsapp_group_id"] for item in groups}
        memberships = [
            item
            for item in payload.get("memberships", [])
            if item.get("whatsapp_group_id") in allowed_group_ids
        ]
        messages = [
            item
            for item in payload.get("messages", [])
            if item.get("whatsapp_group_id") in allowed_group_ids
        ]
        allowed_contact_ids = {
            item["whatsapp_contact_id"]
            for item in memberships
            if item.get("whatsapp_contact_id")
        }
        allowed_contact_ids.update(
            item["whatsapp_contact_id"]
            for item in messages
            if item.get("whatsapp_contact_id")
        )
        contacts = [
            item
            for item in payload.get("contacts", [])
            if item.get("whatsapp_contact_id") in allowed_contact_ids
        ]

        group_map = {
            item["whatsapp_group_id"]: WhatsAppIngestService.upsert_group(item)
            for item in groups
            if item.get("whatsapp_group_id")
        }
        contact_map = {
            item["whatsapp_contact_id"]: WhatsAppIngestService.upsert_contact(item)
            for item in contacts
            if item.get("whatsapp_contact_id")
        }

        for item in memberships:
            WhatsAppIngestService.upsert_membership(item, group_map, contact_map)

        stored_messages = 0
        stored_evaluations = 0
        linked_attendance = 0

        for item in messages:
            message, evaluation_created, attendance_linked = (
                WhatsAppIngestService.upsert_message_and_evaluation(
                    item, group_map, contact_map
                )
            )
            if message is not None:
                stored_messages += 1
            if evaluation_created:
                stored_evaluations += 1
            if attendance_linked:
                linked_attendance += 1

        db.session.commit()
        return {
            "groups": len(group_map),
            "contacts": len(contact_map),
            "memberships": len(memberships),
            "messages": stored_messages,
            "evaluations": stored_evaluations,
            "linked_attendance": linked_attendance,
            "excluded_groups": excluded_group_names,
        }

    @staticmethod
    def list_group_contacts_with_tutor_suggestions(limit_per_contact: int = 3) -> list[dict]:
        excluded_group_names = get_excluded_group_names()
        students = WhatsAppIngestService.list_active_students()
        tutors = WhatsAppIngestService.list_active_tutors()

        contacts = (
            WhatsAppContact.query.filter_by(is_group=False)
            .order_by(WhatsAppContact.id.asc())
            .all()
        )
        historical_student_names_by_phone: dict[str, list[str]] = {}
        historical_tutor_names_by_phone: dict[str, list[str]] = {}
        for evaluation in WhatsAppEvaluation.query.all():
            if evaluation.message is None:
                continue
            phone_number = normalize_phone_number(evaluation.message.author_phone_number)
            if not phone_number:
                continue
            student_name = str(evaluation.student_name or "").strip()
            tutor_name = str(evaluation.tutor_name or "").strip()
            if student_name:
                historical_student_names_by_phone.setdefault(phone_number, [])
                if student_name not in historical_student_names_by_phone[phone_number]:
                    historical_student_names_by_phone[phone_number].append(student_name)
            if tutor_name:
                historical_tutor_names_by_phone.setdefault(phone_number, [])
                if tutor_name not in historical_tutor_names_by_phone[phone_number]:
                    historical_tutor_names_by_phone[phone_number].append(tutor_name)
        student_validations_by_contact_id = {
            item.contact_id: item
            for item in WhatsAppStudentValidation.query.all()
        }
        validations_by_contact_id = {
            item.contact_id: item
            for item in WhatsAppTutorValidation.query.all()
        }

        rows: list[dict] = []
        for contact in contacts:
            group_memberships, excluded_hits, membership_names = (
                build_contact_group_membership_snapshot(contact, excluded_group_names)
            )
            if not group_memberships:
                continue
            contact_payload = {
                "contact_id": contact.id,
                "whatsapp_contact_id": contact.whatsapp_contact_id,
                "phone_number": contact.phone_number,
                "display_name": contact.display_name,
                "push_name": contact.push_name,
                "short_name": contact.short_name,
                "membership_names": membership_names,
                "group_names": [
                    item["group_name"]
                    for item in group_memberships
                    if item.get("group_name")
                ],
                "historical_student_names": historical_student_names_by_phone.get(
                    normalize_phone_number(contact.phone_number), []
                ),
                "historical_tutor_names": historical_tutor_names_by_phone.get(
                    normalize_phone_number(contact.phone_number), []
                ),
                "group_memberships": group_memberships,
            }
            rows.append(
                {
                    **contact_payload,
                    "resolved_name": (
                        contact.display_name
                        or contact.push_name
                        or contact.short_name
                        or next(iter(membership_names), None)
                        or contact.phone_number
                        or contact.whatsapp_contact_id
                    ),
                    "group_names": [
                        item["group_name"]
                        for item in group_memberships
                        if item.get("group_name")
                    ],
                    "group_count": len(group_memberships),
                    "excluded_group_names": excluded_hits,
                    "validated_student": serialize_student_validation(
                        student_validations_by_contact_id.get(contact.id)
                    ),
                    "validated_tutor": serialize_tutor_validation(
                        validations_by_contact_id.get(contact.id)
                    ),
                    "suggested_students": build_student_contact_suggestions(
                        contact_payload, students, limit=limit_per_contact
                    ),
                    "suggested_tutors": build_tutor_contact_suggestions(
                        contact_payload, tutors, limit=limit_per_contact
                    ),
                }
            )

        rows.sort(
            key=lambda item: (
                -(item["suggested_tutors"][0]["confidence"] if item["suggested_tutors"] else 0),
                str(item.get("resolved_name") or "").lower(),
                str(item.get("phone_number") or ""),
            )
        )
        return rows

    @staticmethod
    def validate_contact_as_student(contact_id: int, student_id: int) -> dict:
        contact = db.session.get(WhatsAppContact, contact_id)
        student = db.session.get(Student, student_id)
        if contact is None:
            raise ValueError("Kontak WhatsApp tidak ditemukan.")
        if student is None:
            raise ValueError("Siswa tidak ditemukan.")

        normalized_phone = normalize_phone_number(contact.phone_number)
        if not normalized_phone:
            raise ValueError("Kontak ini belum memiliki nomor WhatsApp yang valid.")

        excluded_group_names = get_excluded_group_names()
        group_memberships, excluded_hits, _membership_names = (
            build_contact_group_membership_snapshot(contact, excluded_group_names)
        )
        if not group_memberships:
            raise ValueError("Kontak ini belum memiliki group aktif yang boleh dipakai.")

        existing_by_contact = WhatsAppStudentValidation.query.filter_by(
            contact_id=contact.id
        ).first()
        existing_by_student = WhatsAppStudentValidation.query.filter_by(
            student_id=student.id
        ).first()
        validation = existing_by_contact or existing_by_student
        if (
            existing_by_contact is not None
            and existing_by_student is not None
            and existing_by_contact.id != existing_by_student.id
        ):
            db.session.delete(existing_by_student)
        if validation is None:
            validation = WhatsAppStudentValidation(
                contact_id=contact.id, student_id=student.id
            )
            db.session.add(validation)

        updated_phone_field = "none"
        if not student.phone or phone_numbers_match(student.phone, normalized_phone):
            student.phone = normalized_phone
            updated_phone_field = "phone"
        elif not student.parent_phone or phone_numbers_match(
            student.parent_phone, normalized_phone
        ):
            student.parent_phone = normalized_phone
            updated_phone_field = "parent_phone"

        validation.contact_id = contact.id
        validation.student_id = student.id
        validation.validated_phone_number = normalized_phone
        validation.validated_contact_name = (
            contact.display_name
            or contact.push_name
            or contact.short_name
            or contact.phone_number
            or contact.whatsapp_contact_id
        )
        validation.group_memberships_json = group_memberships
        validation.excluded_group_names_json = excluded_hits
        validation.validation_source_json = {
            "source": "dashboard_whatsapp_management",
            "contact_name_variants": collect_contact_name_variants(
                {
                    "display_name": contact.display_name,
                    "push_name": contact.push_name,
                    "short_name": contact.short_name,
                    "membership_names": [
                        item.get("display_name") for item in group_memberships
                    ],
                }
            ),
            "updated_phone_field": updated_phone_field,
        }
        validation.validated_at = datetime.utcnow()
        db.session.commit()

        return {
            "validation_id": validation.id,
            "contact_id": contact.id,
            "student_id": student.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "phone_number": normalized_phone,
            "updated_phone_field": updated_phone_field,
            "group_names": [
                item.get("group_name")
                for item in group_memberships
                if item.get("group_name")
            ],
            "excluded_group_names": excluded_hits,
            "validated_at": validation.validated_at.isoformat(),
        }

    @staticmethod
    def validate_group_as_student(group_id: int, student_id: int) -> dict:
        group = db.session.get(WhatsAppGroup, group_id)
        student = db.session.get(Student, student_id)
        if group is None:
            raise ValueError("Group WhatsApp tidak ditemukan.")
        if student is None:
            raise ValueError("Siswa tidak ditemukan.")

        excluded_group_names = get_excluded_group_names()
        if is_excluded_group_name(group.name, excluded_group_names):
            raise ValueError("Group ini dikecualikan dari validasi siswa.")

        validation = WhatsAppStudentGroupValidation.query.filter_by(group_id=group.id).first()
        if validation is None:
            validation = WhatsAppStudentGroupValidation(
                group_id=group.id,
                student_id=student.id,
            )
            db.session.add(validation)

        student_group_memberships = merge_student_group_memberships(
            student.whatsapp_group_memberships_json,
            group,
        )
        student.whatsapp_group_memberships_json = student_group_memberships
        synced_enrollments = WhatsAppIngestService.sync_enrollments_for_student(student.id)

        validation.group_id = group.id
        validation.student_id = student.id
        validation.validation_source_json = {
            "source": "dashboard_whatsapp_management_group",
            "group_name": group.name,
            "whatsapp_group_id": group.whatsapp_group_id,
            "participant_count": group.participant_count,
            "historical_student_names": [
                str(item.student_name).strip()
                for item in WhatsAppEvaluation.query.filter_by(group_id=group.id).all()
                if str(item.student_name or "").strip()
            ],
        }
        validation.validated_at = datetime.utcnow()
        db.session.commit()

        return {
            "validation_id": validation.id,
            "group_id": group.id,
            "whatsapp_group_id": group.whatsapp_group_id,
            "group_name": group.name,
            "student_id": student.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "student_whatsapp_groups": student_group_memberships,
            "synced_enrollments": synced_enrollments,
            "validated_at": validation.validated_at.isoformat(),
        }

    @staticmethod
    def validate_contact_as_tutor(contact_id: int, tutor_id: int) -> dict:
        contact = db.session.get(WhatsAppContact, contact_id)
        tutor = db.session.get(Tutor, tutor_id)
        if contact is None:
            raise ValueError("Kontak WhatsApp tidak ditemukan.")
        if tutor is None:
            raise ValueError("Tutor tidak ditemukan.")

        normalized_phone = normalize_phone_number(contact.phone_number)
        if not normalized_phone:
            raise ValueError("Kontak ini belum memiliki nomor WhatsApp yang valid.")

        excluded_group_names = get_excluded_group_names()
        group_memberships, excluded_hits, _membership_names = (
            build_contact_group_membership_snapshot(contact, excluded_group_names)
        )
        if not group_memberships:
            raise ValueError("Kontak ini belum memiliki group aktif yang boleh dipakai.")

        existing_by_contact = WhatsAppTutorValidation.query.filter_by(
            contact_id=contact.id
        ).first()
        existing_by_tutor = WhatsAppTutorValidation.query.filter_by(
            tutor_id=tutor.id
        ).first()
        validation = existing_by_contact or existing_by_tutor
        if (
            existing_by_contact is not None
            and existing_by_tutor is not None
            and existing_by_contact.id != existing_by_tutor.id
        ):
            db.session.delete(existing_by_tutor)
        if validation is None:
            validation = WhatsAppTutorValidation(contact_id=contact.id, tutor_id=tutor.id)
            db.session.add(validation)

        validation.contact_id = contact.id
        validation.tutor_id = tutor.id
        validation.validated_phone_number = normalized_phone
        validation.validated_contact_name = (
            contact.display_name
            or contact.push_name
            or contact.short_name
            or contact.phone_number
            or contact.whatsapp_contact_id
        )
        validation.group_memberships_json = group_memberships
        validation.excluded_group_names_json = excluded_hits
        validation.validation_source_json = {
            "source": "dashboard_whatsapp_management",
            "contact_name_variants": collect_contact_name_variants(
                {
                    "display_name": contact.display_name,
                    "push_name": contact.push_name,
                    "short_name": contact.short_name,
                    "membership_names": [
                        item.get("display_name") for item in group_memberships
                    ],
                }
            ),
        }
        validation.validated_at = datetime.utcnow()

        tutor.phone = normalized_phone
        synced_enrollments = WhatsAppIngestService.sync_enrollments_for_tutor(tutor.id)
        db.session.commit()

        return {
            "validation_id": validation.id,
            "contact_id": contact.id,
            "tutor_id": tutor.id,
            "tutor_name": tutor.name,
            "phone_number": normalized_phone,
            "group_names": [
                item.get("group_name")
                for item in group_memberships
                if item.get("group_name")
            ],
            "excluded_group_names": excluded_hits,
            "synced_enrollments": synced_enrollments,
            "validated_at": validation.validated_at.isoformat(),
        }

    @staticmethod
    def upsert_group(item: dict) -> WhatsAppGroup:
        group = WhatsAppGroup.query.filter_by(
            whatsapp_group_id=item["whatsapp_group_id"]
        ).first()
        if group is None:
            group = WhatsAppGroup(whatsapp_group_id=item["whatsapp_group_id"])
            db.session.add(group)

        group.name = item.get("name") or group.name or item["whatsapp_group_id"]
        group.invite_link = item.get("invite_link")
        group.invite_code = item.get("invite_code") or extract_group_invite_code(
            group.invite_link
        )
        group.participant_count = int(item.get("participant_count") or 0)
        group.last_synced_at = datetime.utcnow()
        group.metadata_json = item.get("metadata") or {}
        if item.get("last_message_at"):
            group.last_message_at = WhatsAppIngestService.parse_datetime(
                item["last_message_at"]
            )
        return group

    @staticmethod
    def upsert_contact(item: dict) -> WhatsAppContact:
        contact = WhatsAppContact.query.filter_by(
            whatsapp_contact_id=item["whatsapp_contact_id"]
        ).first()
        if contact is None:
            contact = WhatsAppContact(whatsapp_contact_id=item["whatsapp_contact_id"])
            db.session.add(contact)

        contact.phone_number = normalize_phone_number(item.get("phone_number"))
        contact.display_name = item.get("display_name")
        contact.push_name = item.get("push_name")
        contact.short_name = item.get("short_name")
        contact.is_group = bool(item.get("is_group", False))
        contact.metadata_json = item.get("metadata") or {}
        return contact

    @staticmethod
    def upsert_membership(item: dict, group_map: dict, contact_map: dict) -> None:
        group = group_map.get(item.get("whatsapp_group_id"))
        contact = contact_map.get(item.get("whatsapp_contact_id"))
        if group is None or contact is None:
            return

        membership = WhatsAppGroupParticipant.query.filter_by(
            group_id=group.id, contact_id=contact.id
        ).first()
        if membership is None:
            membership = WhatsAppGroupParticipant(group=group, contact=contact)
            db.session.add(membership)

        membership.display_name = item.get("display_name") or contact.display_name
        membership.is_admin = bool(item.get("is_admin", False))
        membership.is_super_admin = bool(item.get("is_super_admin", False))

    @staticmethod
    def upsert_message_and_evaluation(item: dict, group_map: dict, contact_map: dict):
        group = group_map.get(item.get("whatsapp_group_id"))
        if group is None:
            return None, False, False

        message = WhatsAppMessage.query.filter_by(
            whatsapp_message_id=item["whatsapp_message_id"]
        ).first()
        created = False
        if message is None:
            message = WhatsAppMessage(whatsapp_message_id=item["whatsapp_message_id"])
            db.session.add(message)
            created = True

        author_contact = contact_map.get(item.get("whatsapp_contact_id"))
        sent_at = WhatsAppIngestService.parse_datetime(item.get("sent_at"))
        message.group = group
        message.author_contact = author_contact
        message.author_phone_number = normalize_phone_number(item.get("author_phone_number"))
        message.author_name = item.get("author_name")
        message.sent_at = sent_at
        message.body = item.get("body") or ""
        message.message_type = item.get("message_type") or "chat"
        message.from_me = bool(item.get("from_me", False))
        message.has_media = bool(item.get("has_media", False))
        message.filter_status = item.get("filter_status") or "relevant"
        message.relevance_reason = item.get("relevance_reason")
        message.raw_payload = item.get("raw_payload") or {}
        message.parsed_payload = item.get("parsed_payload") or {}

        evaluation_payload = item.get("evaluation")
        evaluation_created = False
        attendance_linked = False
        if evaluation_payload:
            evaluation, evaluation_created, attendance_linked = (
                WhatsAppIngestService.upsert_evaluation(
                    message,
                    group,
                    evaluation_payload,
                    item.get("author_phone_number"),
                )
            )
            message.parsed_payload = {
                **(message.parsed_payload or {}),
                "evaluation_id": evaluation.id if evaluation and evaluation.id else None,
            }

        return message, created or evaluation_created, attendance_linked

    @staticmethod
    def upsert_evaluation(
        message: WhatsAppMessage,
        group: WhatsAppGroup,
        payload: dict,
        author_phone_number: str | None,
    ):
        evaluation = WhatsAppEvaluation.query.filter_by(message_id=message.id).first()
        created = False
        if evaluation is None:
            evaluation = WhatsAppEvaluation(message=message, group=group)
            db.session.add(evaluation)
            created = True

        reported_lesson_date = WhatsAppIngestService.parse_date(
            payload.get("reported_lesson_date")
        )
        evaluation.student_name = payload.get("student_name")
        evaluation.tutor_name = payload.get("tutor_name")
        evaluation.subject_name = payload.get("subject_name")
        evaluation.focus_topic = payload.get("focus_topic")
        evaluation.summary_text = payload.get("summary_text")
        evaluation.source_language = payload.get("source_language")
        evaluation.reported_lesson_date = reported_lesson_date
        evaluation.reported_time_label = payload.get("reported_time_label")
        evaluation.attendance_date = resolve_attendance_date(
            message.sent_at, reported_lesson_date
        )

        matches = WhatsAppIngestService.match_entities_from_group_context(
            evaluation,
            author_phone_number,
        )
        evaluation.matched_student_id = matches["student"].id if matches["student"] else None
        evaluation.matched_tutor_id = matches["tutor"].id if matches["tutor"] else None
        evaluation.matched_subject_id = matches["subject"].id if matches["subject"] else None
        evaluation.matched_enrollment_id = (
            matches["enrollment"].id if matches["enrollment"] else None
        )
        evaluation.confidence_score = matches["confidence"]
        evaluation.match_status = matches["status"]
        evaluation.notes = matches["note"]

        attendance_linked = False
        if matches["enrollment"] is not None:
            attendance = WhatsAppIngestService.link_or_create_attendance(
                matches["enrollment"], evaluation, matched_tutor=matches["tutor"]
            )
            if attendance is not None:
                evaluation.attendance_session = attendance
                attendance_linked = True
                if evaluation.match_status == "matched":
                    evaluation.match_status = "attendance-linked"

        return evaluation, created, attendance_linked

    @staticmethod
    def match_entities(
        student_name: str | None,
        tutor_name: str | None,
        subject_name: str | None,
        author_phone_number: str | None,
    ) -> dict:
        student = WhatsAppIngestService.find_student(student_name)
        tutor = WhatsAppIngestService.find_tutor(tutor_name, author_phone_number)
        subject = WhatsAppIngestService.find_subject(subject_name)

        candidates = []
        if student is not None:
            query = Enrollment.query.filter_by(student_id=student.id, status="active")
            candidates = query.all()
            if tutor is not None:
                candidates = [item for item in candidates if item.tutor_id == tutor.id]
            if subject is not None:
                candidates = [item for item in candidates if item.subject_id == subject.id]

        if len(candidates) == 1:
            return {
                "student": student,
                "tutor": tutor or candidates[0].tutor,
                "subject": subject or candidates[0].subject,
                "enrollment": candidates[0],
                "confidence": 95,
                "status": "matched",
                "note": "Enrollment matched from evaluation payload.",
            }
        if len(candidates) > 1:
            return {
                "student": student,
                "tutor": tutor,
                "subject": subject,
                "enrollment": None,
                "confidence": 55,
                "status": "ambiguous",
                "note": "Multiple active enrollments matched the evaluation.",
            }
        return {
            "student": student,
            "tutor": tutor,
            "subject": subject,
            "enrollment": None,
            "confidence": 25 if student or tutor or subject else 0,
            "status": "unmatched",
            "note": "Could not resolve a single active enrollment from evaluation data.",
        }

    @staticmethod
    def link_or_create_attendance(
        enrollment: Enrollment,
        evaluation: WhatsAppEvaluation,
        matched_tutor: Tutor | None = None,
    ) -> AttendanceSession | None:
        actual_tutor = matched_tutor or enrollment.tutor
        actual_tutor_id = actual_tutor.id if actual_tutor is not None else enrollment.tutor_id
        existing = WhatsAppIngestService.find_existing_attendance_for_whatsapp_identity(
            enrollment,
            evaluation,
            actual_tutor,
        )
        if existing is not None:
            return existing

        author_phone_number = normalize_phone_number(
            evaluation.message.author_phone_number if evaluation.message else None
        )
        notes = (
            f"Auto-generated from WhatsApp evaluation message "
            f"{evaluation.message.whatsapp_message_id} in group {evaluation.group.whatsapp_group_id} "
            f"from tutor phone {author_phone_number or '-'}."
        )
        session = AttendanceSession(
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            tutor_id=actual_tutor_id,
            session_date=datetime.combine(evaluation.attendance_date, datetime.min.time()),
            status="attended",
            student_present=True,
            tutor_present=True,
            subject_id=enrollment.subject_id,
            tutor_fee_amount=enrollment.tutor_rate_per_meeting,
            notes=notes,
        )
        db.session.add(session)
        db.session.flush()
        return session

    @staticmethod
    def find_student(student_name: str | None):
        candidates = [
            {"id": student.id, "name": student.name, "obj": student}
            for student in Student.query.filter_by(is_active=True).all()
        ]
        match = find_best_name_match(student_name, candidates)
        return match["obj"] if match else None

    @staticmethod
    def find_tutor(tutor_name: str | None, author_phone_number: str | None):
        normalized_phone = normalize_phone_number(author_phone_number)
        tutors = Tutor.query.filter_by(is_active=True).all()
        if normalized_phone:
            for tutor in tutors:
                if phone_numbers_match(tutor.phone, normalized_phone):
                    return tutor

        candidates = [
            {"id": tutor.id, "name": tutor.name, "obj": tutor}
            for tutor in tutors
        ]
        match = find_best_name_match(tutor_name, candidates)
        return match["obj"] if match else None

    @staticmethod
    def find_subject(subject_name: str | None):
        normalized_target = normalize_person_name(subject_name)
        if not normalized_target:
            return None
        subjects = Subject.query.filter_by(is_active=True).all()
        for subject in subjects:
            normalized_subject = normalize_person_name(subject.name)
            if (
                normalized_subject == normalized_target
                or normalized_target in normalized_subject
                or normalized_subject in normalized_target
            ):
                return subject
            if normalized_target == "english" and normalized_subject == "bahasa inggris":
                return subject
        return None

    @staticmethod
    def parse_datetime(value: str | datetime | None) -> datetime:
        if isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return datetime.utcnow()
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.utcnow()

    @staticmethod
    def parse_date(value: str | date | None) -> date | None:
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
