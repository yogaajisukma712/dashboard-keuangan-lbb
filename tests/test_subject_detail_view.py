from pathlib import Path


def test_subject_detail_route_builds_tutor_summary_and_renders_template():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert '@master_bp.route("/subjects/<string:subject_ref>", methods=["GET"])' in route_text
    assert "def subject_detail(subject_ref):" in route_text
    assert "subject = _get_subject_by_ref_or_404(subject_ref)" in route_text
    assert "tutor_summary = _build_subject_tutor_summary(subject.id)" in route_text
    assert '"master/subject_detail.html"' in route_text
    assert "tutor_summary=tutor_summary" in route_text


def test_subject_detail_template_and_subject_list_link_exist():
    project_root = Path(__file__).resolve().parents[1]
    detail_template = (
        project_root / "app" / "templates" / "master" / "subject_detail.html"
    ).read_text(encoding="utf-8")
    list_template = (
        project_root / "app" / "templates" / "master" / "subjects_list.html"
    ).read_text(encoding="utf-8")

    assert "{% block title %}{{ subject.name }}{% endblock %}" in detail_template
    assert "Tutor Pengajar" in detail_template
    assert "Enrollment aktif" in detail_template
    assert "Presensi" in detail_template
    assert "Enrollment Terkait" in detail_template
    assert "url_for('master.tutor_detail', tutor_ref=item.tutor_ref)" in detail_template
    assert "url_for('enrollments.enrollment_detail', enrollment_ref=enrollment.public_id)" in detail_template
    assert "url_for('master.subject_detail', subject_ref=subject.public_id)" in list_template
