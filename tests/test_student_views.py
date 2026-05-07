from pathlib import Path


def test_students_list_route_supports_active_state_filter():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert 'active_state = request.args.get("active_state", "", type=str).strip().lower()' in route_text
    assert 'if active_state == "active":' in route_text
    assert 'query = query.filter(Student.is_active.is_(True))' in route_text
    assert 'elif active_state == "inactive":' in route_text
    assert 'query = query.filter(Student.is_active.is_(False))' in route_text
    assert "active_state=active_state" in route_text


def test_students_list_template_contains_active_filter_and_quick_search():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "students_list.html"
    ).read_text(encoding="utf-8")

    assert 'name="active_state"' in template_text
    assert "Siswa Aktif" in template_text
    assert "Siswa Nonaktif" in template_text
    assert 'id="quickStudentSearch"' in template_text
    assert "Pencarian Cepat Halaman Ini" in template_text
    assert "student-row" in template_text
    assert "data-student-search" in template_text
    assert "quickStudentSearchEmptyRow" in template_text


def test_student_detail_route_and_template_support_active_toggle_and_short_title():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )
    template_text = (
        project_root / "app" / "templates" / "master" / "student_detail.html"
    ).read_text(encoding="utf-8")

    assert '@master_bp.route("/students/<string:student_ref>/toggle-active", methods=["POST"])' in route_text
    assert "def toggle_student_active(student_ref):" in route_text
    assert "student.is_active = not bool(student.is_active)" in route_text
    assert 'student.status = "active"' in route_text
    assert 'student.status = "inactive"' in route_text
    assert "{% block title %}{{ student.name }}{% endblock %}" in template_text
    assert "toggle_student_active" in template_text
    assert "Deaktifkan" in template_text
    assert "Aktifkan" in template_text
    assert "Sesi dihitung kumulatif semua bulan" in template_text
    assert "Total Sesi Dibeli" in template_text
    assert "Total Terpakai" in template_text
    assert "Total Sisa Sesi" in template_text
    assert "Total Dibeli" in template_text
    assert "Sisa Total" in template_text
