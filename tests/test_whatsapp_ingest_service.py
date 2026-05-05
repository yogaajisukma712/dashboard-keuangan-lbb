from datetime import date, datetime

from flask import Flask

from app import db
from app.models import (
    AttendanceSession,
    Curriculum,
    Enrollment,
    Level,
    Student,
    Subject,
    Tutor,
    WhatsAppContact,
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppGroupParticipant,
    WhatsAppMessage,
    WhatsAppStudentGroupValidation,
    WhatsAppTutorValidation,
)
from app.services.whatsapp_ingest_service import (
    build_student_contact_suggestions,
    build_student_group_suggestions,
    build_tutor_contact_suggestions,
    extract_group_invite_code,
    find_best_name_match,
    get_excluded_group_names,
    normalize_phone_number,
    phone_numbers_match,
    resolve_attendance_date,
    WhatsAppIngestService,
)


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WHATSAPP_EXCLUDED_GROUP_NAMES="VPS / RDP MURAH III",
    )
    db.init_app(app)
    return app


def test_extract_group_invite_code_from_whatsapp_url():
    code = extract_group_invite_code(
        "https://chat.whatsapp.com/HlpYDEegpuk75gTaYar2JO"
    )

    assert code == "HlpYDEegpuk75gTaYar2JO"


def test_normalize_phone_number_keeps_digits_and_country_code():
    assert normalize_phone_number("+62 895-6359-07419") == "62895635907419"
    assert normalize_phone_number("0895 6359 07419") == "0895635907419"
    assert phone_numbers_match("+62 895-6359-07419", "0895 6359 07419") is True


def test_resolve_attendance_date_prefers_group_message_date():
    attendance_date = resolve_attendance_date(
        datetime(2026, 4, 10, 18, 5),
        date(2026, 4, 7),
    )

    assert attendance_date == date(2026, 4, 10)


def test_find_best_name_match_works_with_case_and_spacing_noise():
    match = find_best_name_match(
        "  Ratih  ",
        [
            {"id": 1, "name": "Nadine"},
            {"id": 2, "name": "Ratih"},
        ],
    )

    assert match == {"id": 2, "name": "Ratih"}


def test_build_tutor_contact_suggestions_prefers_exact_phone_match():
    suggestions = build_tutor_contact_suggestions(
        {
            "phone_number": "+62 812-3456-7890",
            "display_name": "Pak Budi",
            "push_name": None,
            "short_name": None,
            "membership_names": [],
        },
        [
            {"id": 1, "name": "Budi Santoso", "phone": "0812 3456 7890"},
            {"id": 2, "name": "Dinda", "phone": "0899 0000 1111"},
        ],
    )

    assert suggestions[0]["tutor_id"] == 1
    assert suggestions[0]["confidence"] == 100


def test_build_tutor_contact_suggestions_uses_name_similarity_when_phone_missing():
    suggestions = build_tutor_contact_suggestions(
        {
            "phone_number": None,
            "display_name": "Ms. Dinda",
            "push_name": None,
            "short_name": None,
            "membership_names": ["Teacher Dinda"],
        },
        [
            {"id": 1, "name": "Dinda", "phone": None},
            {"id": 2, "name": "Yoga Aji", "phone": None},
        ],
    )

    assert suggestions[0]["tutor_id"] == 1
    assert suggestions[0]["confidence"] >= 74


def test_build_tutor_contact_suggestions_uses_historical_tutor_names():
    suggestions = build_tutor_contact_suggestions(
        {
            "phone_number": "6281230000000",
            "display_name": None,
            "push_name": None,
            "short_name": None,
            "membership_names": [],
            "historical_tutor_names": ["Mona Dwi Fenska"],
        },
        [
            {"id": 1, "name": "Mona Dwi Fenska", "phone": None},
            {"id": 2, "name": "Yaumil Akmalia", "phone": None},
        ],
    )

    assert suggestions[0]["tutor_id"] == 1
    assert suggestions[0]["confidence"] >= 98


def test_build_student_contact_suggestions_uses_parent_phone_and_group_name():
    suggestions = build_student_contact_suggestions(
        {
            "phone_number": "081234567890",
            "display_name": "Ratih Parent",
            "push_name": None,
            "short_name": None,
            "membership_names": [],
            "group_names": ["English Ratih"],
            "historical_student_names": [],
        },
        [
            {
                "id": 1,
                "name": "Ratih",
                "student_code": "STD-001",
                "phone": None,
                "parent_phone": "0812 3456 7890",
            },
            {
                "id": 2,
                "name": "Nadine",
                "student_code": "STD-002",
                "phone": None,
                "parent_phone": None,
            },
        ],
    )

    assert suggestions[0]["student_id"] == 1
    assert suggestions[0]["confidence"] >= 96
    assert suggestions[0]["matched_group_names"] == ["English Ratih"]


def test_build_student_contact_suggestions_uses_historical_student_names():
    suggestions = build_student_contact_suggestions(
        {
            "phone_number": "6281230000000",
            "display_name": None,
            "push_name": None,
            "short_name": None,
            "membership_names": [],
            "group_names": [],
            "historical_student_names": ["Salsa"],
        },
        [
            {
                "id": 1,
                "name": "Salsa",
                "student_code": "STD-010",
                "phone": None,
                "parent_phone": None,
            },
            {
                "id": 2,
                "name": "Ratih",
                "student_code": "STD-011",
                "phone": None,
                "parent_phone": None,
            },
        ],
    )

    assert suggestions[0]["student_id"] == 1
    assert suggestions[0]["confidence"] >= 98


def test_build_student_group_suggestions_uses_group_name_and_history():
    suggestions = build_student_group_suggestions(
        {
            "group_name": "English Ratih",
            "historical_student_names": ["Ratih"],
        },
        [
            {
                "id": 1,
                "name": "Ratih",
                "student_code": "STD-001",
                "phone": None,
                "parent_phone": None,
            },
            {
                "id": 2,
                "name": "Nadine",
                "student_code": "STD-002",
                "phone": None,
                "parent_phone": None,
            },
        ],
    )

    assert suggestions[0]["student_id"] == 1
    assert suggestions[0]["confidence"] == 100
    assert suggestions[0]["matched_historical_names"] == ["Ratih"]


def test_get_excluded_group_names_supports_commas_and_newlines():
    groups = get_excluded_group_names(
        "VPS / RDP MURAH III, Grup A\nGrup B\n  Grup A  "
    )

    assert groups == ["VPS / RDP MURAH III", "Grup A", "Grup B"]


def test_list_active_tutors_sorts_by_name():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Tutor(tutor_code="TTR-003", name="Zidan", is_active=True),
                Tutor(tutor_code="TTR-004", name="Anisa", is_active=True),
                Tutor(tutor_code="TTR-005", name="Budi", is_active=False),
            ]
        )
        db.session.commit()

        tutors = WhatsAppIngestService.list_active_tutors()

        assert [item["name"] for item in tutors] == ["Anisa", "Zidan"]


def test_list_active_students_sorts_by_name():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Student(student_code="STD-002", name="Zidan", is_active=True),
                Student(student_code="STD-001", name="Anisa", is_active=True),
                Student(student_code="STD-003", name="Budi", is_active=False),
            ]
        )
        db.session.commit()

        students = WhatsAppIngestService.list_active_students()

        assert [item["name"] for item in students] == ["Anisa", "Zidan"]


def test_list_group_contacts_with_tutor_suggestions_excludes_configured_groups():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        tutor = Tutor(
            tutor_code="TTR-001",
            name="Dinda",
            phone=None,
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6281230000000@c.us",
            phone_number="6281230000000",
            display_name="Ms. Dinda",
            is_group=False,
        )
        included_group = WhatsAppGroup(
            whatsapp_group_id="group-allowed@g.us",
            name="English Ratih",
        )
        excluded_group = WhatsAppGroup(
            whatsapp_group_id="group-excluded@g.us",
            name="VPS / RDP MURAH III",
        )
        db.session.add_all([tutor, contact, included_group, excluded_group])
        db.session.flush()
        db.session.add_all(
            [
                WhatsAppGroupParticipant(
                    group_id=included_group.id,
                    contact_id=contact.id,
                    display_name="Ms. Dinda",
                ),
                WhatsAppGroupParticipant(
                    group_id=excluded_group.id,
                    contact_id=contact.id,
                    display_name="Ms. Dinda",
                ),
            ]
        )
        db.session.commit()

        contacts = WhatsAppIngestService.list_group_contacts_with_tutor_suggestions()

        assert len(contacts) == 1
        assert contacts[0]["group_names"] == ["English Ratih"]
        assert contacts[0]["excluded_group_names"] == ["VPS / RDP MURAH III"]
        assert contacts[0]["suggested_tutors"][0]["tutor_id"] == tutor.id


def test_validate_contact_as_tutor_updates_tutor_phone_and_group_snapshot():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        tutor = Tutor(
            tutor_code="TTR-002",
            name="Listya Gandhini",
            phone=None,
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6285550001111@c.us",
            phone_number="0855 5000 1111",
            display_name="Listya",
            is_group=False,
        )
        included_group = WhatsAppGroup(
            whatsapp_group_id="group-math@g.us",
            name="Math Ratih",
        )
        excluded_group = WhatsAppGroup(
            whatsapp_group_id="group-junk@g.us",
            name="VPS / RDP MURAH III",
        )
        db.session.add_all([tutor, contact, included_group, excluded_group])
        db.session.flush()
        db.session.add_all(
            [
                WhatsAppGroupParticipant(
                    group_id=included_group.id,
                    contact_id=contact.id,
                    display_name="Listya",
                ),
                WhatsAppGroupParticipant(
                    group_id=excluded_group.id,
                    contact_id=contact.id,
                    display_name="Listya",
                ),
            ]
        )
        db.session.commit()

        result = WhatsAppIngestService.validate_contact_as_tutor(contact.id, tutor.id)

        assert result["tutor_id"] == tutor.id
        assert result["contact_id"] == contact.id
        assert result["phone_number"] == "085550001111"
        assert result["group_names"] == ["Math Ratih"]
        assert result["excluded_group_names"] == ["VPS / RDP MURAH III"]
        assert tutor.phone == "085550001111"


def test_validate_contact_as_student_updates_student_phone_and_group_snapshot():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        student = Student(
            student_code="STD-100",
            name="Ratih",
            phone=None,
            parent_phone=None,
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6287770002222@c.us",
            phone_number="0877 7000 2222",
            display_name="Ratih Parent",
            is_group=False,
        )
        included_group = WhatsAppGroup(
            whatsapp_group_id="group-ratih@g.us",
            name="English Ratih",
        )
        excluded_group = WhatsAppGroup(
            whatsapp_group_id="group-junk@g.us",
            name="VPS / RDP MURAH III",
        )
        db.session.add_all([student, contact, included_group, excluded_group])
        db.session.flush()
        db.session.add_all(
            [
                WhatsAppGroupParticipant(
                    group_id=included_group.id,
                    contact_id=contact.id,
                    display_name="Ratih Parent",
                ),
                WhatsAppGroupParticipant(
                    group_id=excluded_group.id,
                    contact_id=contact.id,
                    display_name="Ratih Parent",
                ),
            ]
        )
        db.session.commit()

        result = WhatsAppIngestService.validate_contact_as_student(contact.id, student.id)

        assert result["student_id"] == student.id
        assert result["student_name"] == "Ratih"
        assert result["phone_number"] == "087770002222"
        assert result["updated_phone_field"] == "phone"
        assert result["group_names"] == ["English Ratih"]
        assert result["excluded_group_names"] == ["VPS / RDP MURAH III"]
        assert student.phone == "087770002222"


def test_list_groups_with_student_suggestions_excludes_configured_groups():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        student = Student(
            student_code="STD-101",
            name="Ratih",
            phone=None,
            parent_phone=None,
            is_active=True,
        )
        included_group = WhatsAppGroup(
            whatsapp_group_id="group-ratih@g.us",
            name="English Ratih",
            participant_count=4,
        )
        excluded_group = WhatsAppGroup(
            whatsapp_group_id="group-junk@g.us",
            name="VPS / RDP MURAH III",
            participant_count=20,
        )
        db.session.add_all([student, included_group, excluded_group])
        db.session.flush()
        message = WhatsAppMessage(
            whatsapp_message_id="msg-ratih-1",
            group_id=included_group.id,
            author_phone_number="628000000001",
            author_name="Ms. Dinda",
            sent_at=datetime(2026, 4, 10, 17, 0),
            body="Evaluasi Ratih",
        )
        db.session.add(message)
        db.session.flush()
        db.session.add(
            WhatsAppEvaluation(
                message_id=message.id,
                group_id=included_group.id,
                student_name="Ratih",
                tutor_name="Dinda",
                attendance_date=date(2026, 4, 10),
            )
        )
        db.session.commit()

        groups = WhatsAppIngestService.list_groups_with_student_suggestions()

        assert len(groups) == 1
        assert groups[0]["group_name"] == "English Ratih"
        assert groups[0]["suggested_students"][0]["student_id"] == student.id


def test_validate_group_as_student_persists_group_validation():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        student = Student(
            student_code="STD-102",
            name="Salsa",
            phone=None,
            parent_phone=None,
            is_active=True,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-salsa@g.us",
            name="English Salsa",
            participant_count=3,
        )
        db.session.add_all([student, group])
        db.session.flush()
        message = WhatsAppMessage(
            whatsapp_message_id="msg-salsa-1",
            group_id=group.id,
            author_phone_number="628000000002",
            author_name="Ms. Dinda",
            sent_at=datetime(2026, 4, 11, 17, 0),
            body="Evaluasi Salsa",
        )
        db.session.add(message)
        db.session.flush()
        db.session.add(
            WhatsAppEvaluation(
                message_id=message.id,
                group_id=group.id,
                student_name="Salsa",
                tutor_name="Ms. Dinda",
                attendance_date=date(2026, 4, 11),
            )
        )
        db.session.commit()

        result = WhatsAppIngestService.validate_group_as_student(group.id, student.id)
        groups = WhatsAppIngestService.list_groups_with_student_suggestions()

        assert result["student_id"] == student.id
        assert result["group_id"] == group.id
        assert result["student_whatsapp_groups"] == [
            {
                "group_id": group.id,
                "whatsapp_group_id": "group-salsa@g.us",
                "group_name": "English Salsa",
            }
        ]
        assert student.whatsapp_group_memberships_json == [
            {
                "group_id": group.id,
                "whatsapp_group_id": "group-salsa@g.us",
                "group_name": "English Salsa",
            }
        ]
        assert groups[0]["validated_student"]["student_id"] == student.id
        assert groups[0]["validated_student"]["student_name"] == "Salsa"


def test_validate_group_as_student_appends_new_group_to_student_snapshot():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        student = Student(
            student_code="STD-103",
            name="Nadine",
            phone=None,
            parent_phone=None,
            is_active=True,
            whatsapp_group_memberships_json=[
                {
                    "group_id": 8,
                    "whatsapp_group_id": "group-old@g.us",
                    "group_name": "Math Nadine",
                }
            ],
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-new@g.us",
            name="English Nadine",
            participant_count=4,
        )
        db.session.add_all([student, group])
        db.session.commit()

        result = WhatsAppIngestService.validate_group_as_student(group.id, student.id)

        assert result["student_id"] == student.id
        assert student.whatsapp_group_memberships_json == [
            {
                "group_id": group.id,
                "whatsapp_group_id": "group-new@g.us",
                "group_name": "English Nadine",
            },
            {
                "group_id": 8,
                "whatsapp_group_id": "group-old@g.us",
                "group_name": "Math Nadine",
            },
        ]


def test_validate_group_as_student_syncs_matching_enrollment():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMA")
        subject = Subject(name="Bahasa Inggris")
        student = Student(
            student_code="STD-104",
            name="Ratih",
            is_active=True,
        )
        tutor = Tutor(
            tutor_code="TTR-104",
            name="Dinda",
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6281000000104@c.us",
            phone_number="081000000104",
            display_name="Ms. Dinda",
            is_group=False,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-enroll@g.us",
            name="English Ratih",
        )
        enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="10",
            student_rate_per_meeting=50000,
            tutor_rate_per_meeting=30000,
            status="active",
        )
        db.session.add_all(
            [curriculum, level, subject, student, tutor, contact, group, enrollment]
        )
        db.session.flush()
        db.session.add(
            WhatsAppTutorValidation(
                contact_id=contact.id,
                tutor_id=tutor.id,
                validated_phone_number="0812",
                group_memberships_json=[
                    {
                        "group_id": group.id,
                        "whatsapp_group_id": "group-enroll@g.us",
                        "group_name": "English Ratih",
                    }
                ],
            )
        )
        db.session.commit()

        result = WhatsAppIngestService.validate_group_as_student(group.id, student.id)

        assert result["synced_enrollments"][0]["enrollment_id"] == enrollment.id
        assert enrollment.whatsapp_group_id == "group-enroll@g.us"
        assert enrollment.whatsapp_group_name == "English Ratih"
        assert enrollment.whatsapp_group_memberships_json == [
            {
                "group_id": group.id,
                "whatsapp_group_id": "group-enroll@g.us",
                "group_name": "English Ratih",
            }
        ]


def test_validate_contact_as_tutor_syncs_matching_enrollment_from_student_group():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Cambridge")
        level = Level(name="SMP")
        subject = Subject(name="Matematika")
        student = Student(
            student_code="STD-105",
            name="Salsa",
            is_active=True,
            whatsapp_group_memberships_json=[
                {
                    "group_id": 99,
                    "whatsapp_group_id": "group-salsa@g.us",
                    "group_name": "English Salsa",
                }
            ],
        )
        tutor = Tutor(
            tutor_code="TTR-105",
            name="Listya",
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6289990001111@c.us",
            phone_number="0899 9000 1111",
            display_name="Listya",
            is_group=False,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-salsa@g.us",
            name="English Salsa",
        )
        enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="8",
            student_rate_per_meeting=60000,
            tutor_rate_per_meeting=35000,
            status="active",
        )
        db.session.add_all(
            [curriculum, level, subject, student, tutor, contact, group, enrollment]
        )
        db.session.flush()
        db.session.add(
            WhatsAppGroupParticipant(
                group_id=group.id,
                contact_id=contact.id,
                display_name="Listya",
            )
        )
        db.session.commit()

        result = WhatsAppIngestService.validate_contact_as_tutor(contact.id, tutor.id)

        assert result["synced_enrollments"][0]["enrollment_id"] == enrollment.id
        assert enrollment.whatsapp_group_id == "group-salsa@g.us"
        assert enrollment.whatsapp_group_name == "English Salsa"
        assert enrollment.whatsapp_group_memberships_json == [
            {
                "group_id": 99,
                "whatsapp_group_id": "group-salsa@g.us",
                "group_name": "English Salsa",
            }
        ]


def test_sync_enrollment_whatsapp_group_keeps_multiple_shared_groups():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Merdeka")
        level = Level(name="SD")
        subject = Subject(name="IPA")
        student = Student(
            student_code="STD-106",
            name="Nadine",
            is_active=True,
            whatsapp_group_memberships_json=[
                {
                    "group_id": 10,
                    "whatsapp_group_id": "group-1@g.us",
                    "group_name": "English Nadine",
                },
                {
                    "group_id": 11,
                    "whatsapp_group_id": "group-2@g.us",
                    "group_name": "Math Nadine",
                },
            ],
        )
        tutor = Tutor(
            tutor_code="TTR-106",
            name="Mona",
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6281110000106@c.us",
            phone_number="081110000106",
            display_name="Mona",
            is_group=False,
        )
        enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="5",
            student_rate_per_meeting=70000,
            tutor_rate_per_meeting=40000,
            status="active",
        )
        db.session.add_all(
            [curriculum, level, subject, student, tutor, contact, enrollment]
        )
        db.session.flush()
        db.session.add(
            WhatsAppTutorValidation(
                contact_id=contact.id,
                tutor_id=tutor.id,
                validated_phone_number="0811",
                group_memberships_json=[
                    {
                        "group_id": 10,
                        "whatsapp_group_id": "group-1@g.us",
                        "group_name": "English Nadine",
                    },
                    {
                        "group_id": 11,
                        "whatsapp_group_id": "group-2@g.us",
                        "group_name": "Math Nadine",
                    },
                ],
            )
        )
        db.session.commit()

        result = WhatsAppIngestService.sync_enrollment_whatsapp_group(enrollment)

        assert result["matched"] is True
        assert enrollment.whatsapp_group_id == "group-1@g.us"
        assert enrollment.whatsapp_group_name == "English Nadine"
        assert enrollment.whatsapp_group_memberships_json == [
            {
                "group_id": 10,
                "whatsapp_group_id": "group-1@g.us",
                "group_name": "English Nadine",
            },
            {
                "group_id": 11,
                "whatsapp_group_id": "group-2@g.us",
                "group_name": "Math Nadine",
            },
        ]


def test_scan_attendance_for_month_uses_validated_tutor_and_group_context():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMP")
        subject = Subject(name="Bahasa Inggris")
        student = Student(student_code="STD-200", name="Ratih", is_active=True)
        tutor = Tutor(
            tutor_code="TTR-200",
            name="Ms. Dinda",
            phone="081234567890",
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6281234567890@c.us",
            phone_number="081234567890",
            display_name="Ms. Dinda",
            is_group=False,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-ratih@g.us",
            name="English Ratih",
        )
        enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="8",
            student_rate_per_meeting=80000,
            tutor_rate_per_meeting=45000,
            status="active",
            whatsapp_group_id="group-ratih@g.us",
            whatsapp_group_name="English Ratih",
            whatsapp_group_memberships_json=[
                {
                    "whatsapp_group_id": "group-ratih@g.us",
                    "group_name": "English Ratih",
                }
            ],
        )
        db.session.add_all(
            [curriculum, level, subject, student, tutor, contact, group, enrollment]
        )
        db.session.flush()
        db.session.add(
            WhatsAppTutorValidation(
                contact_id=contact.id,
                tutor_id=tutor.id,
                validated_phone_number="081234567890",
                group_memberships_json=[
                    {
                        "group_id": group.id,
                        "whatsapp_group_id": "group-ratih@g.us",
                        "group_name": "English Ratih",
                    }
                ],
            )
        )
        db.session.add(
            WhatsAppStudentGroupValidation(
                group_id=group.id,
                student_id=student.id,
            )
        )

        may_message = WhatsAppMessage(
            whatsapp_message_id="wamid-may-1",
            group=group,
            author_phone_number="081234567890",
            author_name="Ms. Dinda",
            sent_at=datetime(2026, 5, 10, 17, 0, 0),
            body="Evaluasi Mei",
        )
        may_evaluation = WhatsAppEvaluation(
            message=may_message,
            group=group,
            student_name="Ratih",
            tutor_name="Ms. Dinda",
            subject_name="Bahasa Inggris",
            attendance_date=date(2026, 5, 10),
        )
        april_message = WhatsAppMessage(
            whatsapp_message_id="wamid-apr-1",
            group=group,
            author_phone_number="081234567890",
            author_name="Ms. Dinda",
            sent_at=datetime(2026, 4, 10, 17, 0, 0),
            body="Evaluasi April",
        )
        april_evaluation = WhatsAppEvaluation(
            message=april_message,
            group=group,
            student_name="Ratih",
            tutor_name="Ms. Dinda",
            subject_name="Bahasa Inggris",
            attendance_date=date(2026, 4, 10),
        )
        db.session.add_all([may_message, may_evaluation, april_message, april_evaluation])
        db.session.commit()

        summary = WhatsAppIngestService.scan_attendance_for_month(5, 2026)

        assert summary["processed_evaluations"] == 1
        assert summary["linked_attendance"] == 1
        assert may_evaluation.attendance_session is not None
        assert may_evaluation.matched_enrollment_id == enrollment.id
        assert may_evaluation.match_status == "attendance-linked"
        assert april_evaluation.attendance_session is None
        assert AttendanceSession.query.count() == 1


def test_scan_attendance_for_month_is_idempotent_for_existing_links():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="Merdeka")
        level = Level(name="SD")
        subject = Subject(name="Matematika")
        student = Student(student_code="STD-201", name="Nadine", is_active=True)
        tutor = Tutor(
            tutor_code="TTR-201",
            name="Listya",
            phone="089990001111",
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6289990001111@c.us",
            phone_number="089990001111",
            display_name="Listya",
            is_group=False,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-nadine@g.us",
            name="Math Nadine",
        )
        enrollment = Enrollment(
            student=student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="5",
            student_rate_per_meeting=75000,
            tutor_rate_per_meeting=40000,
            status="active",
            whatsapp_group_id="group-nadine@g.us",
            whatsapp_group_name="Math Nadine",
            whatsapp_group_memberships_json=[
                {
                    "whatsapp_group_id": "group-nadine@g.us",
                    "group_name": "Math Nadine",
                }
            ],
        )
        db.session.add_all(
            [curriculum, level, subject, student, tutor, contact, group, enrollment]
        )
        db.session.flush()
        db.session.add(
            WhatsAppTutorValidation(
                contact_id=contact.id,
                tutor_id=tutor.id,
                validated_phone_number="089990001111",
                group_memberships_json=[
                    {
                        "group_id": group.id,
                        "whatsapp_group_id": "group-nadine@g.us",
                        "group_name": "Math Nadine",
                    }
                ],
            )
        )
        db.session.add(
            WhatsAppStudentGroupValidation(
                group_id=group.id,
                student_id=student.id,
            )
        )
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-may-2",
            group=group,
            author_phone_number="089990001111",
            author_name="Listya",
            sent_at=datetime(2026, 5, 11, 18, 0, 0),
            body="Evaluasi Mei",
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Nadine",
            tutor_name="Listya",
            subject_name="Matematika",
            attendance_date=date(2026, 5, 11),
        )
        db.session.add_all([message, evaluation])
        db.session.commit()

        first_summary = WhatsAppIngestService.scan_attendance_for_month(5, 2026)
        second_summary = WhatsAppIngestService.scan_attendance_for_month(5, 2026)

        assert first_summary["linked_attendance"] == 1
        assert second_summary["already_linked"] == 1
        assert AttendanceSession.query.count() == 1
        assert evaluation.attendance_session is not None


def test_list_groups_with_student_suggestions_includes_message_counts():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        student = Student(student_code="STD-202", name="Ratih", is_active=True)
        group = WhatsAppGroup(
            whatsapp_group_id="group-count@g.us",
            name="English Ratih",
            participant_count=5,
        )
        db.session.add_all([student, group])
        db.session.flush()
        message_one = WhatsAppMessage(
            whatsapp_message_id="wamid-count-1",
            group=group,
            author_phone_number="081234",
            author_name="Tutor A",
            sent_at=datetime(2026, 5, 1, 17, 0, 0),
            body="chat 1",
            filter_status="ignored",
        )
        message_two = WhatsAppMessage(
            whatsapp_message_id="wamid-count-2",
            group=group,
            author_phone_number="081234",
            author_name="Tutor A",
            sent_at=datetime(2026, 5, 2, 17, 0, 0),
            body="chat 2",
            filter_status="relevant",
        )
        evaluation = WhatsAppEvaluation(
            message=message_two,
            group=group,
            student_name="Ratih",
            attendance_date=date(2026, 5, 2),
            attendance_session_id=99,
        )
        db.session.add_all([message_one, message_two, evaluation])
        db.session.commit()

        groups = WhatsAppIngestService.list_groups_with_student_suggestions()

        assert groups[0]["message_count"] == 2
        assert groups[0]["evaluation_count"] == 1
        assert groups[0]["linked_attendance_count"] == 1


def test_scan_attendance_for_month_uses_sender_tutor_and_group_identity():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMP")
        subject = Subject(name="Bahasa Inggris")
        student = Student(student_code="STD-203", name="Ratih", is_active=True)
        permanent_tutor = Tutor(
            tutor_code="TTR-203A",
            name="Tutor Tetap",
            phone="081111111111",
            is_active=True,
        )
        substitute_tutor = Tutor(
            tutor_code="TTR-203B",
            name="Ms. Dinda",
            phone="081222222222",
            is_active=True,
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6281222222222@c.us",
            phone_number="081222222222",
            display_name="Ms. Dinda",
            is_group=False,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-ratih-sub@g.us",
            name="English Ratih",
        )
        enrollment = Enrollment(
            student=student,
            tutor=permanent_tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="8",
            student_rate_per_meeting=80000,
            tutor_rate_per_meeting=45000,
            status="active",
            whatsapp_group_id="group-ratih-sub@g.us",
            whatsapp_group_name="English Ratih",
            whatsapp_group_memberships_json=[
                {
                    "whatsapp_group_id": "group-ratih-sub@g.us",
                    "group_name": "English Ratih",
                }
            ],
        )
        db.session.add_all(
            [
                curriculum,
                level,
                subject,
                student,
                permanent_tutor,
                substitute_tutor,
                contact,
                group,
                enrollment,
            ]
        )
        db.session.flush()
        db.session.add(
            WhatsAppTutorValidation(
                contact_id=contact.id,
                tutor_id=substitute_tutor.id,
                validated_phone_number="081222222222",
                group_memberships_json=[
                    {
                        "group_id": group.id,
                        "whatsapp_group_id": "group-ratih-sub@g.us",
                        "group_name": "English Ratih",
                    }
                ],
            )
        )
        db.session.add(
            WhatsAppStudentGroupValidation(
                group_id=group.id,
                student_id=student.id,
            )
        )

        first_message = WhatsAppMessage(
            whatsapp_message_id="wamid-sub-1",
            group=group,
            author_phone_number="081222222222",
            author_name="Ms. Dinda",
            sent_at=datetime(2026, 5, 12, 17, 0, 0),
            body="Evaluasi 1",
        )
        first_evaluation = WhatsAppEvaluation(
            message=first_message,
            group=group,
            student_name="Ratih",
            tutor_name="Ms. Dinda",
            subject_name="Bahasa Inggris",
            attendance_date=date(2026, 5, 12),
        )
        second_message = WhatsAppMessage(
            whatsapp_message_id="wamid-sub-2",
            group=group,
            author_phone_number="081222222222",
            author_name="Ms. Dinda",
            sent_at=datetime(2026, 5, 12, 18, 30, 0),
            body="Evaluasi 2",
        )
        second_evaluation = WhatsAppEvaluation(
            message=second_message,
            group=group,
            student_name="Ratih",
            tutor_name="Ms. Dinda",
            subject_name="Bahasa Inggris",
            attendance_date=date(2026, 5, 12),
        )
        db.session.add_all([first_message, first_evaluation, second_message, second_evaluation])
        db.session.commit()

        summary = WhatsAppIngestService.scan_attendance_for_month(5, 2026)

        assert summary["linked_attendance"] == 2
        assert first_evaluation.attendance_session_id == second_evaluation.attendance_session_id
        assert AttendanceSession.query.count() == 1
        stored_session = AttendanceSession.query.first()
        assert stored_session.enrollment_id == enrollment.id
        assert stored_session.tutor_id == substitute_tutor.id
        assert first_evaluation.matched_tutor_id == substitute_tutor.id
        assert first_evaluation.matched_enrollment_id == enrollment.id


def test_upsert_evaluation_uses_validated_group_and_sender_not_payload_identity():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        curriculum = Curriculum(name="K13")
        level = Level(name="SMP")
        subject = Subject(name="Bahasa Inggris")
        wrong_subject = Subject(name="Matematika")
        validated_student = Student(
            student_code="STD-204",
            name="Ratih Validated",
            is_active=True,
        )
        payload_student = Student(
            student_code="STD-205",
            name="Nama Dari Pesan",
            is_active=True,
        )
        tutor = Tutor(
            tutor_code="TTR-204",
            name="Tutor Pengirim",
            phone="081333333333",
            is_active=True,
        )
        enrollment = Enrollment(
            student=validated_student,
            tutor=tutor,
            subject=subject,
            curriculum=curriculum,
            level=level,
            grade="8",
            student_rate_per_meeting=80000,
            tutor_rate_per_meeting=45000,
            status="active",
            whatsapp_group_id="group-authoritative@g.us",
            whatsapp_group_name="English Ratih",
            whatsapp_group_memberships_json=[
                {
                    "whatsapp_group_id": "group-authoritative@g.us",
                    "group_name": "English Ratih",
                }
            ],
        )
        contact = WhatsAppContact(
            whatsapp_contact_id="6281333333333@c.us",
            phone_number="081333333333",
            display_name="Tutor Pengirim",
            is_group=False,
        )
        group = WhatsAppGroup(
            whatsapp_group_id="group-authoritative@g.us",
            name="English Ratih",
        )
        db.session.add_all(
            [
                curriculum,
                level,
                subject,
                wrong_subject,
                validated_student,
                payload_student,
                tutor,
                contact,
                group,
                enrollment,
            ]
        )
        db.session.flush()
        db.session.add_all(
            [
                WhatsAppStudentGroupValidation(
                    group_id=group.id,
                    student_id=validated_student.id,
                ),
                WhatsAppTutorValidation(
                    contact_id=contact.id,
                    tutor_id=tutor.id,
                    validated_phone_number="081333333333",
                ),
            ]
        )
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-authoritative-identity",
            group=group,
            author_phone_number="081333333333",
            author_name="Tutor Pengirim",
            sent_at=datetime(2026, 5, 13, 18, 45, 0),
            body="Laporan evaluasi valid",
        )
        db.session.add(message)
        db.session.flush()

        evaluation, created, attendance_linked = WhatsAppIngestService.upsert_evaluation(
            message,
            group,
            {
                "student_name": "Nama Dari Pesan",
                "tutor_name": "Nama Tutor Dari Pesan",
                "subject_name": "Matematika",
                "reported_lesson_date": "2026-04-01",
                "summary_text": "Evaluasi valid.",
            },
            "081333333333",
        )
        db.session.commit()

        assert created is True
        assert attendance_linked is True
        assert evaluation.attendance_date == date(2026, 5, 13)
        assert evaluation.matched_student_id == validated_student.id
        assert evaluation.matched_tutor_id == tutor.id
        assert evaluation.matched_subject_id == subject.id
        assert evaluation.matched_enrollment_id == enrollment.id
        assert AttendanceSession.query.count() == 1
        session = AttendanceSession.query.first()
        assert session.student_id == validated_student.id
        assert session.tutor_id == tutor.id
        assert session.subject_id == subject.id


def test_ingest_sync_payload_avoids_duplicate_messages_but_keeps_distinct_tutor_posts():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        payload = {
            "groups": [
                {
                    "whatsapp_group_id": "group-ratih@g.us",
                    "name": "English Ratih",
                    "participant_count": 2,
                    "last_message_at": "2026-05-12T18:30:00",
                    "metadata": {},
                }
            ],
            "contacts": [
                {
                    "whatsapp_contact_id": "6281222222222@c.us",
                    "phone_number": "081222222222",
                    "display_name": "Ms. Dinda",
                    "push_name": "Ms. Dinda",
                    "short_name": "Dinda",
                    "metadata": {},
                }
            ],
            "memberships": [
                {
                    "whatsapp_group_id": "group-ratih@g.us",
                    "whatsapp_contact_id": "6281222222222@c.us",
                    "phone_number": "081222222222",
                    "display_name": "Ms. Dinda",
                    "is_admin": False,
                    "is_super_admin": False,
                }
            ],
            "messages": [
                {
                    "whatsapp_message_id": "wamid-duplicate-1",
                    "whatsapp_group_id": "group-ratih@g.us",
                    "whatsapp_contact_id": "6281222222222@c.us",
                    "author_phone_number": "081222222222",
                    "author_name": "Ms. Dinda",
                    "sent_at": "2026-05-12T17:00:00",
                    "body": "Evaluasi 1",
                    "message_type": "chat",
                    "from_me": False,
                    "has_media": False,
                    "filter_status": "ignored",
                    "relevance_reason": "not_evaluation",
                    "raw_payload": {},
                    "parsed_payload": {},
                    "evaluation": None,
                },
                {
                    "whatsapp_message_id": "wamid-duplicate-2",
                    "whatsapp_group_id": "group-ratih@g.us",
                    "whatsapp_contact_id": "6281222222222@c.us",
                    "author_phone_number": "081222222222",
                    "author_name": "Ms. Dinda",
                    "sent_at": "2026-05-12T18:30:00",
                    "body": "Evaluasi 2",
                    "message_type": "chat",
                    "from_me": False,
                    "has_media": False,
                    "filter_status": "ignored",
                    "relevance_reason": "not_evaluation",
                    "raw_payload": {},
                    "parsed_payload": {},
                    "evaluation": None,
                },
            ],
        }

        first_summary = WhatsAppIngestService.ingest_sync_payload(payload)
        second_summary = WhatsAppIngestService.ingest_sync_payload(payload)

        stored_messages = WhatsAppMessage.query.order_by(WhatsAppMessage.whatsapp_message_id).all()
        assert first_summary["messages"] == 2
        assert second_summary["messages"] == 2
        assert len(stored_messages) == 2
        assert [item.whatsapp_message_id for item in stored_messages] == [
            "wamid-duplicate-1",
            "wamid-duplicate-2",
        ]


def test_upsert_evaluation_truncates_long_varchar_payload_fields():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        group = WhatsAppGroup(whatsapp_group_id="group-long@g.us", name="Long Payload")
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-long-eval",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor",
            sent_at=datetime(2026, 5, 4, 18, 30, 0),
            body="Laporan panjang",
        )
        db.session.add_all([group, message])
        db.session.flush()
        payload = {
            "student_name": "Pembelajaran hari ini " * 30,
            "tutor_name": "Tutor " * 80,
            "subject_name": "Subject " * 80,
            "focus_topic": "Topic " * 80,
            "summary_text": "Isi evaluasi valid dan panjang.",
            "source_language": "id" * 40,
            "reported_lesson_date": "2026-05-04",
            "reported_time_label": "18:30 - 19:30 WITA " * 10,
        }

        evaluation, created, _attendance_linked = WhatsAppIngestService.upsert_evaluation(
            message,
            group,
            payload,
            "081234567890",
        )
        db.session.commit()

        assert created is True
        assert len(evaluation.student_name) == 255
        assert len(evaluation.tutor_name) == 255
        assert len(evaluation.subject_name) == 255
        assert len(evaluation.focus_topic) == 255
        assert len(evaluation.source_language) == 32
        assert len(evaluation.reported_time_label) == 64
