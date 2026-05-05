from datetime import date
from pathlib import Path

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
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppMessage,
)
from app.routes.attendance import (
    WHATSAPP_REVIEW_START_DATE,
    _apply_attendance_list_sort,
    _build_attendance_list_query,
    _build_whatsapp_review_map,
    _set_whatsapp_attendance_manual_review,
    _sync_linked_whatsapp_evaluations,
    _unlink_whatsapp_evaluations_before_attendance_delete,
)


def _make_test_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _seed_attendance_sessions():
    curriculum = Curriculum(name="K13")
    level = Level(name="SMA")
    subject_math = Subject(name="Matematika")
    subject_english = Subject(name="Bahasa Inggris")
    student_nadine = Student(student_code="STD-301", name="Nadine")
    student_ratih = Student(student_code="STD-302", name="Ratih")
    tutor_dinda = Tutor(tutor_code="TTR-301", name="Dinda", is_active=True)
    tutor_listya = Tutor(tutor_code="TTR-302", name="Listya", is_active=True)
    db.session.add_all(
        [
            curriculum,
            level,
            subject_math,
            subject_english,
            student_nadine,
            student_ratih,
            tutor_dinda,
            tutor_listya,
        ]
    )
    db.session.flush()

    enrollment_math = Enrollment(
        student_id=student_nadine.id,
        subject_id=subject_math.id,
        tutor_id=tutor_dinda.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="10",
        student_rate_per_meeting=150000,
        tutor_rate_per_meeting=80000,
        status="active",
    )
    enrollment_english = Enrollment(
        student_id=student_ratih.id,
        subject_id=subject_english.id,
        tutor_id=tutor_listya.id,
        curriculum_id=curriculum.id,
        level_id=level.id,
        grade="9",
        student_rate_per_meeting=140000,
        tutor_rate_per_meeting=75000,
        status="active",
    )
    db.session.add_all([enrollment_math, enrollment_english])
    db.session.flush()

    april_session = AttendanceSession(
        enrollment_id=enrollment_math.id,
        student_id=student_nadine.id,
        tutor_id=tutor_dinda.id,
        subject_id=subject_math.id,
        session_date=date(2026, 4, 10),
        status="attended",
        student_present=True,
        tutor_present=True,
        tutor_fee_amount=80000,
    )
    may_session = AttendanceSession(
        enrollment_id=enrollment_english.id,
        student_id=student_ratih.id,
        tutor_id=tutor_dinda.id,
        subject_id=subject_english.id,
        session_date=date(2026, 5, 10),
        status="scheduled",
        student_present=False,
        tutor_present=False,
        tutor_fee_amount=75000,
    )
    db.session.add_all([april_session, may_session])
    db.session.commit()
    return {
        "april_session": april_session,
        "may_session": may_session,
        "tutor_dinda": tutor_dinda,
        "tutor_listya": tutor_listya,
    }


def test_build_attendance_list_query_filters_by_month_year_and_tutor():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()

        may_results = _build_attendance_list_query(month=5, year=2026).all()
        april_results = _build_attendance_list_query(month=4, year=2026).all()
        tutor_results = _build_attendance_list_query(
            tutor_id=seeded["tutor_dinda"].id,
            month=5,
            year=2026,
        ).all()

        assert [item.id for item in may_results] == [seeded["may_session"].id]
        assert [item.id for item in april_results] == [seeded["april_session"].id]
        assert [item.id for item in tutor_results] == [seeded["may_session"].id]


def test_attendance_list_sort_orders_by_student_name():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        _seed_attendance_sessions()

        base_query = _build_attendance_list_query()
        asc_results = _apply_attendance_list_sort(base_query, "student_asc").all()
        desc_results = _apply_attendance_list_sort(
            _build_attendance_list_query(),
            "student_desc",
        ).all()

        assert [item.student.name for item in asc_results] == ["Nadine", "Ratih"]
        assert [item.student.name for item in desc_results] == ["Ratih", "Nadine"]


def test_attendance_list_sort_orders_by_student_name_and_date_together():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        nadine_session = seeded["april_session"]
        older_nadine_session = AttendanceSession(
            enrollment_id=nadine_session.enrollment_id,
            student_id=nadine_session.student_id,
            tutor_id=nadine_session.tutor_id,
            subject_id=nadine_session.subject_id,
            session_date=date(2026, 4, 1),
            status="attended",
            student_present=True,
            tutor_present=True,
            tutor_fee_amount=80000,
        )
        db.session.add(older_nadine_session)
        db.session.commit()

        latest_first = _apply_attendance_list_sort(
            _build_attendance_list_query(),
            "student_asc_date_desc",
        ).all()
        oldest_first = _apply_attendance_list_sort(
            _build_attendance_list_query(),
            "student_asc_date_asc",
        ).all()

        assert [item.session_date for item in latest_first[:2]] == [
            date(2026, 4, 10),
            date(2026, 4, 1),
        ]
        assert [item.session_date for item in oldest_first[:2]] == [
            date(2026, 4, 1),
            date(2026, 4, 10),
        ]


def test_attendance_list_template_contains_whatsapp_scan_form_and_year_filter():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "attendance" / "list.html"
    ).read_text(encoding="utf-8")

    assert 'name="year"' in template_text
    assert 'id="scanWhatsappAttendanceForm"' in template_text
    assert "attendance.scan_whatsapp_attendance" in template_text
    assert "default_scan_year" in template_text
    assert "tutor pengganti mengajar" in template_text
    assert 'id="quickAttendanceSearch"' in template_text
    assert 'id="attendanceTableBody"' in template_text
    assert 'class="attendance-row"' in template_text
    assert 'data-attendance-search="' in template_text
    assert 'quickAttendanceSearchEmptyRow' in template_text
    assert 'Tidak ada sesi di halaman ini yang cocok dengan pencarian cepat.' in template_text
    assert 'quickAttendanceSearchInput.addEventListener("input"' in template_text
    assert 'name="enrollment_ref"' in template_text
    assert 'name="tutor_ref"' in template_text
    assert "enr.public_id" in template_text
    assert "t.public_id" in template_text
    assert "whatsapp_review_map" in template_text
    assert "Validasi Manual WA" in template_text
    assert "Sudah benar" in template_text
    assert "Perlu koreksi" in template_text
    assert "Belum crosscheck" in template_text
    assert "attendance.review_whatsapp_attendance" in template_text
    assert 'class="js-wa-review-form"' in template_text
    assert "spinner-border spinner-border-sm" in template_text
    assert '"X-Requested-With": "XMLHttpRequest"' in template_text
    assert "updateWaReviewUi(reviewBox, data)" in template_text
    assert 'name="sort"' in template_text
    assert 'value="student_asc"' in template_text
    assert "Siswa A-Z" in template_text
    assert "Siswa Z-A" in template_text
    assert 'value="student_asc_date_asc"' in template_text
    assert 'value="student_desc_date_asc"' in template_text
    assert "Siswa A-Z, tanggal terlama" in template_text
    assert "Siswa Z-A, tanggal terbaru" in template_text
    assert 'name="sort" value="{{ selected_sort or \'date_desc\' }}"' in template_text
    assert "sort=selected_sort or 'date_desc'" in template_text
    assert "reset_filters=1" in template_text
    assert "attendance.delete_attendance" in template_text


def test_attendance_form_template_contains_manual_tutor_selector():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "attendance" / "form.html"
    ).read_text(encoding="utf-8")

    assert "Tutor Pengajar" in template_text
    assert "attendance_tutor_map" in template_text
    assert "maybeSyncTutorFromEnrollment" in template_text
    assert "Tidak harus sama dengan tutor bawaan enrollment" in template_text


def test_attendance_routes_support_public_ref_filters_in_source():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "attendance.py").read_text(
        encoding="utf-8"
    )

    assert '_decode_optional_query_ref("enrollment_ref", "enrollment")' in route_text
    assert '_decode_optional_query_ref("tutor_ref", "tutor")' in route_text
    assert '"enrollment_ref": request.args.get("enrollment_ref") or stored_state.get("enrollment_ref") or ""' in route_text
    assert '"tutor_ref": request.args.get("tutor_ref") or stored_state.get("tutor_ref") or ""' in route_text
    assert '@attendance_bp.route("/<string:session_ref>/whatsapp-review"' in route_text
    assert "_set_whatsapp_attendance_manual_review" in route_text
    assert "_wants_json_response()" in route_text
    assert "_whatsapp_review_response_payload" in route_text
    assert 'return jsonify({"ok": False, "error": str(exc)}), 400' in route_text
    assert "_unlink_whatsapp_evaluations_before_attendance_delete(session)" in route_text
    assert 'ATTENDANCE_LIST_STATE_SESSION_KEY = "attendance_list_state"' in route_text
    assert "def _restore_attendance_list_state_if_needed():" in route_text
    assert 'request.args.get("reset_filters") == "1"' in route_text
    assert "session[ATTENDANCE_LIST_STATE_SESSION_KEY] = state" in route_text
    assert '"per_page": request.args.get("per_page") or stored_state.get("per_page") or ""' in route_text


def test_whatsapp_manual_review_marks_linked_evaluations_without_attendance_change():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        group = WhatsAppGroup(whatsapp_group_id="group-review@g.us", name="Review Ratih")
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-review-1",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor Pengganti",
            sent_at=seeded["may_session"].created_at,
            body="Evaluasi",
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Ratih",
            tutor_name="Tutor Pengganti",
            subject_name="Bahasa Inggris",
            attendance_date=seeded["may_session"].session_date,
            matched_student_id=seeded["may_session"].student_id,
            matched_tutor_id=seeded["tutor_listya"].id,
            matched_subject_id=seeded["may_session"].subject_id,
            matched_enrollment_id=seeded["may_session"].enrollment_id,
            attendance_session_id=seeded["may_session"].id,
            match_status="attendance-linked",
        )
        original_tutor_id = seeded["may_session"].tutor_id
        original_status = seeded["may_session"].status
        db.session.add_all([group, message, evaluation])
        db.session.flush()

        updated_count = _set_whatsapp_attendance_manual_review(
            seeded["may_session"],
            "valid",
            reviewer_id=7,
            notes="Sudah dicrosscheck manual",
        )

        assert updated_count == 1
        assert evaluation.manual_review_status == "valid"
        assert evaluation.manual_reviewed_by == 7
        assert evaluation.manual_review_notes == "Sudah dicrosscheck manual"
        assert evaluation.manual_reviewed_at is not None
        assert seeded["may_session"].tutor_id == original_tutor_id
        assert seeded["may_session"].status == original_status


def test_whatsapp_manual_review_only_applies_from_april_2026_onward():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        assert WHATSAPP_REVIEW_START_DATE == date(2026, 4, 1)

        group = WhatsAppGroup(whatsapp_group_id="group-old-review@g.us", name="Old")
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-old-review",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor",
            sent_at=seeded["april_session"].created_at,
            body="Evaluasi lama",
        )
        old_session = AttendanceSession(
            enrollment_id=seeded["april_session"].enrollment_id,
            student_id=seeded["april_session"].student_id,
            tutor_id=seeded["april_session"].tutor_id,
            subject_id=seeded["april_session"].subject_id,
            session_date=date(2026, 3, 31),
            status="attended",
            student_present=True,
            tutor_present=True,
            tutor_fee_amount=80000,
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Nadine",
            attendance_date=old_session.session_date,
            attendance_session=old_session,
        )
        db.session.add_all([group, message, old_session, evaluation])
        db.session.flush()

        updated_count = _set_whatsapp_attendance_manual_review(old_session, "valid")

        assert updated_count == 0
        assert evaluation.manual_review_status == "pending"


def test_build_whatsapp_review_map_aggregates_page_sessions():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        group = WhatsAppGroup(whatsapp_group_id="group-map-review@g.us", name="Map")
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-map-review",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor",
            sent_at=seeded["may_session"].created_at,
            body="Evaluasi",
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Ratih",
            attendance_date=seeded["may_session"].session_date,
            attendance_session_id=seeded["may_session"].id,
            manual_review_status="invalid",
        )
        db.session.add_all([group, message, evaluation])
        db.session.flush()

        review_map = _build_whatsapp_review_map([seeded["may_session"]])

        assert review_map[seeded["may_session"].id]["status"] == "invalid"
        assert review_map[seeded["may_session"].id]["count"] == 1
        assert review_map[seeded["may_session"].id]["requires_review"] is True


def test_delete_attendance_unlinks_whatsapp_evaluations_before_session_delete():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        session_id = seeded["may_session"].id
        group = WhatsAppGroup(
            whatsapp_group_id="group-delete-review@g.us",
            name="Delete Ratih",
        )
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-delete-review",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor",
            sent_at=seeded["may_session"].created_at,
            body="Evaluasi",
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Ratih",
            attendance_date=seeded["may_session"].session_date,
            attendance_session_id=session_id,
            match_status="attendance-linked",
            notes="Linked from WhatsApp scan.",
        )
        db.session.add_all([group, message, evaluation])
        db.session.flush()

        unlinked_count = _unlink_whatsapp_evaluations_before_attendance_delete(
            seeded["may_session"]
        )
        db.session.delete(seeded["may_session"])
        db.session.commit()

        assert unlinked_count == 1
        assert AttendanceSession.query.get(session_id) is None
        assert evaluation.attendance_session_id is None
        assert evaluation.match_status == "manual-unlinked"
        assert "Presensi terkait dihapus manual" in evaluation.notes


def test_sync_linked_whatsapp_evaluations_follows_manual_attendance_edit():
    app = _make_test_app()

    with app.app_context():
        db.create_all()
        seeded = _seed_attendance_sessions()
        group = WhatsAppGroup(whatsapp_group_id="group-ratih@g.us", name="English Ratih")
        message = WhatsAppMessage(
            whatsapp_message_id="wamid-manual-edit-1",
            group=group,
            author_phone_number="081234567890",
            author_name="Tutor Pengganti",
            sent_at=seeded["may_session"].created_at,
            body="Evaluasi",
        )
        evaluation = WhatsAppEvaluation(
            message=message,
            group=group,
            student_name="Ratih",
            tutor_name="Tutor Pengganti",
            subject_name="Bahasa Inggris",
            attendance_date=seeded["may_session"].session_date,
            matched_student_id=seeded["may_session"].student_id,
            matched_tutor_id=seeded["tutor_listya"].id,
            matched_subject_id=seeded["may_session"].subject_id,
            matched_enrollment_id=seeded["may_session"].enrollment_id,
            attendance_session_id=seeded["may_session"].id,
            match_status="attendance-linked",
        )
        db.session.add_all([group, message, evaluation])
        db.session.flush()

        seeded["may_session"].tutor_id = seeded["tutor_dinda"].id
        _sync_linked_whatsapp_evaluations(seeded["may_session"])

        assert evaluation.matched_tutor_id == seeded["tutor_dinda"].id
        assert evaluation.matched_enrollment_id == seeded["may_session"].enrollment_id
        assert evaluation.matched_student_id == seeded["may_session"].student_id
        assert evaluation.attendance_session_id == seeded["may_session"].id
        assert "Presensi dikoreksi manual" in evaluation.notes
