#!/usr/bin/env python3
"""Remove duplicate WhatsApp rows created by timestamp-based fallback IDs."""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import or_

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app, db  # noqa: E402
from app.models import AttendanceSession, WhatsAppEvaluation, WhatsAppMessage  # noqa: E402


FALLBACK_ID_PATTERN = r"@g\.us-[0-9]+$"


def same_author(left, right):
    if left.author_contact_id and right.author_contact_id:
        return left.author_contact_id == right.author_contact_id
    if left.author_phone_number and right.author_phone_number:
        return left.author_phone_number == right.author_phone_number
    return bool(left.author_name and left.author_name == right.author_name)


def same_evaluation(left, right):
    if not left or not right:
        return False
    return (
        left.attendance_date == right.attendance_date
        and left.reported_lesson_date == right.reported_lesson_date
        and left.reported_time_label == right.reported_time_label
        and left.matched_enrollment_id == right.matched_enrollment_id
        and left.matched_tutor_id == right.matched_tutor_id
    )


def same_attendance(left, right):
    if not left or not right:
        return False
    fields = (
        "enrollment_id",
        "student_id",
        "tutor_id",
        "session_date",
        "status",
        "student_present",
        "tutor_present",
        "subject_id",
        "tutor_fee_amount",
    )
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def candidate_score(fallback, candidate):
    score = 0
    if fallback.body == candidate.body:
        score += 40
    if same_author(fallback, candidate):
        score += 20
    if same_evaluation(fallback.evaluation, candidate.evaluation):
        score += 80
    return score


def select_canonical(fallback, candidates):
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            candidate_score(fallback, candidate),
            -candidate.id,
        ),
        reverse=True,
    )
    return ranked[0]


def copy_evaluation_message_payload(source, target):
    fields = (
        "author_contact",
        "author_phone_number",
        "author_name",
        "body",
        "message_type",
        "from_me",
        "has_media",
        "filter_status",
        "relevance_reason",
        "raw_payload",
        "parsed_payload",
    )
    for field in fields:
        setattr(target, field, getattr(source, field))


def build_cleanup_plan():
    fallback_messages = (
        WhatsAppMessage.query.filter(
            WhatsAppMessage.whatsapp_message_id.op("~")(FALLBACK_ID_PATTERN)
        )
        .order_by(WhatsAppMessage.id.asc())
        .all()
    )
    canonical_messages = (
        WhatsAppMessage.query.filter(
            or_(
                WhatsAppMessage.whatsapp_message_id.startswith("false_"),
                WhatsAppMessage.whatsapp_message_id.startswith("true_"),
            )
        )
        .order_by(WhatsAppMessage.id.asc())
        .all()
    )
    canonical_by_moment = defaultdict(list)
    for message in canonical_messages:
        canonical_by_moment[(message.group_id, message.sent_at)].append(message)

    plan = []
    conflicts = []
    for fallback in fallback_messages:
        candidates = canonical_by_moment.get((fallback.group_id, fallback.sent_at), [])
        canonical = select_canonical(fallback, candidates)
        if canonical is None:
            conflicts.append(
                {
                    "fallback_message_id": fallback.id,
                    "reason": "canonical-message-not-found",
                }
            )
            continue

        fallback_evaluation = fallback.evaluation
        canonical_evaluation = canonical.evaluation
        action = "delete-message"
        attendance_to_delete = None

        if fallback_evaluation and not canonical_evaluation:
            action = "transfer-evaluation"
        elif fallback_evaluation and canonical_evaluation:
            if not same_evaluation(fallback_evaluation, canonical_evaluation):
                conflicts.append(
                    {
                        "fallback_message_id": fallback.id,
                        "canonical_message_id": canonical.id,
                        "reason": "evaluation-mismatch",
                    }
                )
                continue

            fallback_attendance = fallback_evaluation.attendance_session
            canonical_attendance = canonical_evaluation.attendance_session
            if fallback_attendance and canonical_attendance:
                if fallback_attendance.id != canonical_attendance.id:
                    if not same_attendance(fallback_attendance, canonical_attendance):
                        conflicts.append(
                            {
                                "fallback_message_id": fallback.id,
                                "canonical_message_id": canonical.id,
                                "reason": "attendance-mismatch",
                            }
                        )
                        continue
                    reference_count = WhatsAppEvaluation.query.filter_by(
                        attendance_session_id=fallback_attendance.id
                    ).count()
                    if reference_count != 1:
                        conflicts.append(
                            {
                                "fallback_message_id": fallback.id,
                                "canonical_message_id": canonical.id,
                                "reason": "attendance-has-extra-references",
                            }
                        )
                        continue
                    attendance_to_delete = fallback_attendance
            elif fallback_attendance and not canonical_attendance:
                canonical_evaluation.attendance_session = fallback_attendance

            action = "delete-duplicate-evaluation"

        plan.append(
            {
                "fallback": fallback,
                "canonical": canonical,
                "action": action,
                "attendance_to_delete": attendance_to_delete,
            }
        )

    return plan, conflicts


def summarize_plan(plan, conflicts):
    summary = {
        "fallback_messages": len(plan) + len(conflicts),
        "planned_message_deletes": len(plan),
        "duplicate_evaluations": 0,
        "evaluation_transfers": 0,
        "attendance_deletes": 0,
        "conflicts": len(conflicts),
        "conflict_examples": conflicts[:10],
    }
    for item in plan:
        if item["action"] == "delete-duplicate-evaluation":
            summary["duplicate_evaluations"] += 1
        elif item["action"] == "transfer-evaluation":
            summary["evaluation_transfers"] += 1
        if item["attendance_to_delete"] is not None:
            summary["attendance_deletes"] += 1
    return summary


def execute_plan(plan):
    for item in plan:
        fallback = item["fallback"]
        canonical = item["canonical"]
        fallback_evaluation = fallback.evaluation

        if item["action"] == "transfer-evaluation":
            copy_evaluation_message_payload(fallback, canonical)
            fallback_evaluation.message = canonical
            db.session.flush()
        elif item["action"] == "delete-duplicate-evaluation":
            db.session.delete(fallback_evaluation)
            db.session.flush()

        attendance = item["attendance_to_delete"]
        if attendance is not None:
            db.session.delete(attendance)
            db.session.flush()

        db.session.delete(fallback)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Commit the cleanup. Without this flag the command is read-only.",
    )
    args = parser.parse_args()

    app = create_app(os.getenv("FLASK_ENV", "production"))
    with app.app_context():
        plan, conflicts = build_cleanup_plan()
        summary = summarize_plan(plan, conflicts)
        summary["mode"] = "execute" if args.execute else "dry-run"
        print(json.dumps(summary, indent=2, default=str))

        if not args.execute:
            db.session.rollback()
            return
        if conflicts:
            db.session.rollback()
            raise SystemExit("Cleanup aborted: resolve all conflicts first.")

        execute_plan(plan)
        db.session.commit()


if __name__ == "__main__":
    main()
