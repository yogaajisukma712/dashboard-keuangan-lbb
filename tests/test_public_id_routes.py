from pathlib import Path


def _read(rel_path: str) -> str:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / rel_path).read_text(encoding="utf-8")


def test_target_models_expose_public_id_properties():
    master_models = _read("app/models/master.py")
    attendance_model = _read("app/models/attendance.py")
    pricing_model = _read("app/models/pricing.py")

    assert 'return encode_public_id("curriculum", self.id)' in master_models
    assert 'return encode_public_id("level", self.id)' in master_models
    assert 'return encode_public_id("subject", self.id)' in master_models
    assert 'return encode_public_id("attendance_session", self.id)' in attendance_model
    assert 'return encode_public_id("pricing_rule", self.id)' in pricing_model


def test_routes_decode_public_refs_for_master_attendance_and_payroll():
    attendance_routes = _read("app/routes/attendance.py")
    master_routes = _read("app/routes/master.py")
    payroll_routes = _read("app/routes/payroll.py")
    enrollment_routes = _read("app/routes/enrollments.py")

    assert '@attendance_bp.route("/<string:session_ref>/edit"' in attendance_routes
    assert '@attendance_bp.route("/<string:session_ref>/delete"' in attendance_routes
    assert 'decode_public_id(session_ref, "attendance_session")' in attendance_routes

    assert '@master_bp.route("/subjects/<string:subject_ref>/edit"' in master_routes
    assert '@master_bp.route("/subjects/<string:subject_ref>", methods=["GET"])' in master_routes
    assert '@master_bp.route("/curriculums/<string:curriculum_ref>/edit"' in master_routes
    assert '@master_bp.route("/pricing/<string:pricing_ref>/edit"' in master_routes
    assert '@master_bp.route("/pricing/api/<string:curriculum_ref>/<string:level_ref>"' in master_routes
    assert 'decode_public_id(subject_ref, "subject")' in master_routes
    assert 'decode_public_id(curriculum_ref, "curriculum")' in master_routes
    assert 'decode_public_id(level_ref, "level")' in master_routes
    assert 'decode_public_id(pricing_ref, "pricing_rule")' in master_routes

    assert '@payroll_bp.route("/api/tutor/<string:tutor_ref>/balance"' in payroll_routes
    assert 'decode_public_id(tutor_ref, "tutor")' in payroll_routes
    assert "tutor_public_ids" in payroll_routes

    assert "_build_pricing_public_id_maps()" in enrollment_routes

    assert '<int:session_id>' not in attendance_routes
    assert '<int:id>/edit' not in master_routes
    assert '<int:id>/delete' not in master_routes
    assert "/api/tutor/<int:tutor_id>/balance" not in payroll_routes


def test_templates_use_public_refs_in_links_and_browser_fetches():
    attendance_list = _read("app/templates/attendance/list.html")
    subjects_list = _read("app/templates/master/subjects_list.html")
    subject_detail = _read("app/templates/master/subject_detail.html")
    subject_form = _read("app/templates/master/subject_form.html")
    curriculums_list = _read("app/templates/master/curriculums_list.html")
    curriculum_form = _read("app/templates/master/curriculum_form.html")
    pricing_list = _read("app/templates/master/pricing_list.html")
    pricing_form = _read("app/templates/master/pricing_form.html")
    enrollment_form = _read("app/templates/enrollments/form.html")
    payout_form = _read("app/templates/payroll/payout_form.html")

    assert "session_ref=s.public_id" in attendance_list
    assert "subject_ref=subject.public_id" in subjects_list
    assert "master.subject_detail" in subjects_list
    assert "master.tutor_detail" in subject_detail
    assert "subject_ref=subject.public_id" in subject_form
    assert "curriculum_ref=curriculum.public_id" in curriculums_list
    assert "curriculum_ref=curriculum.public_id" in curriculum_form
    assert "pricing_ref=pricing.public_id" in pricing_list
    assert "pricing_ref=pricing.public_id" in pricing_form

    assert "const curriculumPublicIds =" in enrollment_form
    assert "const levelPublicIds =" in enrollment_form
    assert "const url = `/master/pricing/api/${curRef}/${levelRef}`;" in enrollment_form
    assert "/master/pricing/api/${curId}/${levelId}" not in enrollment_form

    assert "const tutorPublicIds =" in payout_form
    assert "const tutorRef = tutorId ? tutorPublicIds[tutorId] : null;" in payout_form
    assert "/payroll/api/tutor/${tutorRef}/balance" in payout_form
    assert "/payroll/api/tutor/${tutorId}/balance" not in payout_form
