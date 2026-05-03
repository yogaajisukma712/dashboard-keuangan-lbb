from decimal import Decimal
from pathlib import Path

from flask import Flask

from app import register_template_filters
from app.routes.enrollments import _normalize_rate_form_value


def test_normalize_rate_form_value_removes_trailing_decimal_places():
    assert _normalize_rate_form_value(Decimal("43750.00")) == 43750
    assert _normalize_rate_form_value(Decimal("30000.00")) == 30000
    assert _normalize_rate_form_value(None) is None


def test_enrollment_form_template_uses_whole_number_steps_for_rate_fields():
    project_root = Path(__file__).resolve().parents[1]
    route_text = (project_root / "app" / "routes" / "enrollments.py").read_text(
        encoding="utf-8"
    )
    template_text = (
        project_root / "app" / "templates" / "enrollments" / "form.html"
    ).read_text(encoding="utf-8")

    assert "_normalize_rate_form_value(" in route_text
    assert 'form.student_rate_per_meeting(class_="form-control"' in template_text
    assert 'form.tutor_rate_per_meeting(class_="form-control"' in template_text
    assert "step=1" in template_text


def test_enrollment_detail_notes_filter_is_registered_and_escapes_html():
    app = Flask(__name__)
    register_template_filters(app)

    rendered = app.jinja_env.filters["nl2br"]("<b>Baris 1</b>\nBaris 2")

    assert "nl2br" in app.jinja_env.filters
    assert "&lt;b&gt;Baris 1&lt;/b&gt;<br>Baris 2" == str(rendered)
