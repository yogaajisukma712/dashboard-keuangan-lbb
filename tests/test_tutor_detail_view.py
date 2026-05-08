from pathlib import Path


def test_tutor_detail_route_precomputes_payout_queries():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )

    assert "recent_payouts = tutor.payouts.order_by(TutorPayout.id.desc()).limit(3).all()" in route_text
    assert "last_payout = recent_payouts[0] if recent_payouts else None" in route_text
    assert "whatsapp_tutor_validation = WhatsAppTutorValidation.query.filter_by(" in route_text
    assert "validated_group_memberships = list(" in route_text
    assert "excluded_group_names = list(" in route_text
    assert "from app.models import (" in route_text
    assert "    Enrollment," in route_text
    assert "teaching_schedule = _build_tutor_teaching_schedule(tutor.id)" in route_text
    assert "schedule_grid = _build_tutor_weekly_schedule_grid(tutor.id)" in route_text
    assert "taught_subjects = _build_tutor_subject_summary(tutor.id)" in route_text
    assert "recent_payouts=recent_payouts" in route_text
    assert "last_payout=last_payout" in route_text
    assert "teaching_schedule=teaching_schedule" in route_text
    assert "schedule_grid=schedule_grid" in route_text
    assert "taught_subjects=taught_subjects" in route_text
    assert "whatsapp_tutor_validation=whatsapp_tutor_validation" in route_text
    assert "validated_group_memberships=validated_group_memberships" in route_text
    assert "excluded_group_names=excluded_group_names" in route_text


def test_tutor_detail_template_does_not_use_textual_order_by():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "master" / "tutor_detail.html"
    ).read_text(encoding="utf-8")

    assert "order_by('id desc')" not in template_text
    assert 'order_by("id desc")' not in template_text
    assert "Validasi WhatsApp Tutor" in template_text
    assert "ID Group" in template_text
    assert "Nama Group" in template_text
    assert "Jadwal Mengajar" in template_text
    assert "08.00-21.00" in template_text
    assert "{% block title %}{{ tutor.name }}{% endblock %}" in template_text
    assert "schedule_grid.lesson_count" in template_text
    assert 'include "master/_tutor_schedule_grid.html"' in template_text
    assert "Mapel yang Diajarkan" in template_text
    assert "Enrollment aktif" in template_text
    assert "url_for('master.subject_detail', subject_ref=item.subject_ref)" in template_text
    assert "url_for('attendance.calendar_view', tutor_ref=tutor.public_id)" in template_text
    assert "url_for('master.tutor_schedule_view', tutor_ref=tutor.public_id)" in template_text


def test_tutor_weekly_schedule_route_and_templates_exist():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "master.py").read_text(
        encoding="utf-8"
    )
    schedule_template = (
        project_root / "app" / "templates" / "master" / "tutor_schedule.html"
    ).read_text(encoding="utf-8")
    grid_template = (
        project_root / "app" / "templates" / "master" / "_tutor_schedule_grid.html"
    ).read_text(encoding="utf-8")
    tutors_list_template = (
        project_root / "app" / "templates" / "master" / "tutors_list.html"
    ).read_text(encoding="utf-8")
    base_template = (project_root / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "def _build_tutor_weekly_schedule_grid(tutor_id: int | None):" in route_text
    assert "hour_slots = list(range(8, 22))" in route_text
    assert "EnrollmentSchedule.query.join(Enrollment)" in route_text
    assert "used_slots = {weekday: 17 for weekday in range(7)}" in route_text
    assert 'cell["availability"] = "filled" if cell["items"] else "unavailable" if cell["hour"] < 16 else "available"' in route_text
    assert "student_short_name" in route_text
    assert '@master_bp.route("/tutors/schedule", methods=["GET"])' in route_text
    assert "def tutor_schedule_view():" in route_text
    assert "Jadwal Tutor" in schedule_template
    assert 'name="tutor_ref"' in schedule_template
    assert 'include "master/_tutor_schedule_grid.html"' in schedule_template
    assert "schedule_grid.weekday_names" in grid_template
    assert "schedule_grid.rows" in grid_template
    assert "cell['items']" in grid_template
    assert "cell.items" not in grid_template
    assert "tutor-schedule-cell-latest" in grid_template
    assert "tutor-schedule-cell-available" in grid_template
    assert "tutor-schedule-cell-unavailable" in grid_template
    assert "tutor-schedule-cell-filled" in grid_template
    assert "tutor-schedule-copy-btn" in grid_template
    assert "navigator.clipboard.write" in grid_template
    assert "ClipboardItem({ 'image/png': blob })" in grid_template
    assert "--bs-table-bg: #fdba74;" in grid_template
    assert "--bs-table-bg: #86efac;" in grid_template
    assert "--bs-table-bg: #fca5a5;" in grid_template
    assert "Tutor tidak bisa" in grid_template
    assert "Tutor bisa" in grid_template
    assert ">Tidak bisa<" not in grid_template
    assert ">Bisa<" not in grid_template
    assert "{{ item.student_short_name }}" in grid_template
    assert "{{ item.subject_name }}" in grid_template
    assert "Tutor bisa, belum ada siswa" in schedule_template
    assert "Tutor tidak bisa" in schedule_template
    assert "background: #fdba74;" in schedule_template
    assert "tutor-schedule-legend-available" in schedule_template
    tutor_detail_template = (
        project_root / "app" / "templates" / "master" / "tutor_detail.html"
    ).read_text(encoding="utf-8")
    assert "tutor-detail-schedule-legend-available" in tutor_detail_template
    assert "background: #fdba74;" in tutor_detail_template
    assert "url_for('master.tutor_schedule_view')" in tutors_list_template
    assert "url_for('master.tutor_schedule_view')" in base_template
    assert "Jadwal Tutor" in base_template
