from pathlib import Path


def test_tutors_list_route_defaults_to_active_filter_and_supports_toggle():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert 'active_state = request.args.get("active_state", "active", type=str).strip().lower()' in route_text
    assert 'if active_state == "active":' in route_text
    assert "query = query.filter(Tutor.is_active.is_(True))" in route_text
    assert 'elif active_state == "inactive":' in route_text
    assert "query = query.filter(Tutor.is_active.is_(False))" in route_text
    assert 'elif active_state != "all":' in route_text
    assert "active_state=active_state" in route_text
    assert '@master_bp.route("/tutors/<string:tutor_ref>/toggle-active", methods=["POST"])' in route_text
    assert "def toggle_tutor_active(tutor_ref):" in route_text
    assert "tutor.is_active = not bool(tutor.is_active)" in route_text
    assert 'tutor.status = "active"' in route_text
    assert 'tutor.status = "inactive"' in route_text


def test_tutors_list_template_contains_active_filter_and_toggle_button():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "tutors_list.html"
    ).read_text(encoding="utf-8")

    assert 'name="active_state"' in template_text
    assert "Tutor Aktif" in template_text
    assert "Tutor Nonaktif" in template_text
    assert "Semua Tutor" in template_text
    assert "active_state != 'active'" in template_text
    assert "master.toggle_tutor_active" in template_text
    assert "Nonaktifkan tutor" in template_text
    assert "Aktifkan tutor" in template_text
    assert 'name="next" value="{{ request.full_path }}"' in template_text
