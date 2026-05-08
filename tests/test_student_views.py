from pathlib import Path


def test_students_list_route_supports_active_state_filter():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert 'active_state = request.args.get("active_state", "active", type=str).strip().lower()' in route_text
    assert 'elif active_state == "inactive":' in route_text
    assert 'query = query.filter(Student.is_active.is_(False))' in route_text
    assert 'elif active_state == "all":' in route_text
    assert 'active_state = "active"' in route_text
    assert 'query = query.filter(Student.is_active.is_(True))' in route_text
    assert "active_state=active_state" in route_text


def test_students_list_route_only_loads_quota_alerts_for_active_students():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert "active_student_ids = [" in route_text
    assert "student.id for student in students.items if bool(student.is_active)" in route_text
    assert "quota_alert_map = _get_student_quota_alert_map(active_student_ids, service_month)" in route_text


def test_quota_alert_routes_ignore_inactive_students():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "quota_invoice.py").read_text(
        encoding="utf-8"
    )

    assert "active_student_ids = {" in route_text
    assert ".filter(Student.id.in_(student_ids), Student.is_active.is_(True))" in route_text
    assert "for student_id in active_student_ids:" in route_text
    assert "Enrollment.query.join(Enrollment.student)" in route_text
    assert "Student.is_active.is_(True)" in route_text


def test_students_list_route_supports_last_activity_sorting():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert 'sort_by = request.args.get("sort", "name_asc", type=str).strip().lower()' in route_text
    assert "last_attendance_subquery" in route_text
    assert "AttendanceSession.student_id.label(\"student_id\")" in route_text
    assert "db.func.max(AttendanceSession.session_date).label(\"last_attendance_date\")" in route_text
    assert "last_payment_subquery" in route_text
    assert "StudentPayment.student_id.label(\"student_id\")" in route_text
    assert "db.func.max(StudentPayment.payment_date).label(\"last_payment_date\")" in route_text
    assert 'elif sort_by == "last_attendance_desc":' in route_text
    assert 'elif sort_by == "last_payment_desc":' in route_text
    assert "last_attendance_map=last_attendance_map" in route_text
    assert "last_payment_map=last_payment_map" in route_text
    assert "sort_by=sort_by" in route_text


def test_students_list_route_supports_bulk_status_update():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert '@master_bp.route("/students/bulk-status", methods=["POST"])' in route_text
    assert "def bulk_update_student_status():" in route_text
    assert 'student_refs = request.form.getlist("student_refs")' in route_text
    assert 'if bulk_action not in {"activate", "deactivate"}:' in route_text
    assert 'student_ids.append(decode_public_id(student_ref, "student"))' in route_text
    assert "Student.query.filter(Student.id.in_(student_ids))" in route_text
    assert "Student.is_active: target_active" in route_text
    assert "Student.status: target_status" in route_text


def test_students_list_template_contains_active_filter_and_quick_search():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "students_list.html"
    ).read_text(encoding="utf-8")

    assert 'name="active_state"' in template_text
    assert "Siswa Aktif" in template_text
    assert "Siswa Nonaktif" in template_text
    assert "Semua Siswa" in template_text
    assert "active_state != 'active'" in template_text
    assert 'id="quickStudentSearch"' in template_text
    assert "Pencarian Cepat Halaman Ini" in template_text
    assert "student-row" in template_text
    assert "data-student-search" in template_text
    assert "quickStudentSearchEmptyRow" in template_text


def test_students_list_template_contains_sort_dates_and_status_toggle():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "students_list.html"
    ).read_text(encoding="utf-8")

    assert 'name="sort"' in template_text
    assert "Presensi Terbaru" in template_text
    assert "Bayar Terbaru" in template_text
    assert "Presensi Terakhir" in template_text
    assert "Bayar Terakhir" in template_text
    assert "last_attendance_map.get(student.id)" in template_text
    assert "last_payment_map.get(student.id)" in template_text
    assert "toggle_student_active" in template_text
    assert 'name="next"' in template_text
    assert "bi-person-dash" in template_text
    assert "bi-person-check" in template_text
    assert 'colspan="11"' in template_text


def test_students_list_template_contains_bulk_selection_controls():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "students_list.html"
    ).read_text(encoding="utf-8")

    assert 'id="studentBulkStatusForm"' in template_text
    assert "bulk_update_student_status" in template_text
    assert 'id="selectAllStudents"' in template_text
    assert 'name="student_refs"' in template_text
    assert 'form="studentBulkStatusForm"' in template_text
    assert "student-bulk-checkbox" in template_text
    assert "Aktifkan Terpilih" in template_text
    assert "Nonaktifkan Terpilih" in template_text
    assert "updateStudentSelectAllState" in template_text
    assert "Pilih minimal satu siswa terlebih dahulu." in template_text


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
    assert "refresh_student_quota" in template_text
    assert "Refresh Sesi" in template_text
