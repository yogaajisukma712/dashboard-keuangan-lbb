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
    assert "taught_subjects = _build_tutor_subject_summary(tutor.id)" in route_text
    assert "recent_payouts=recent_payouts" in route_text
    assert "last_payout=last_payout" in route_text
    assert "teaching_schedule=teaching_schedule" in route_text
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
    assert "Presensi Sesi Les" in template_text
    assert "Detail enrollment" in template_text
    assert "{% block title %}{{ tutor.name }}{% endblock %}" in template_text
    assert "day_bucket['items']" in template_text
    assert "day_bucket.items" not in template_text
    assert "Mapel yang Diajarkan" in template_text
    assert "Enrollment aktif" in template_text
    assert "url_for('master.subject_detail', subject_ref=item.subject_ref)" in template_text
    assert "url_for('attendance.calendar_view', tutor_ref=tutor.public_id)" in template_text
