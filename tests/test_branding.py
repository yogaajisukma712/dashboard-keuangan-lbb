from pathlib import Path

from flask import Flask

from app.utils.branding import get_branding_logo_data_uri, get_branding_logo_mark_data_uri


def _make_app(tmp_path):
    app_root = tmp_path / "app_root"
    (app_root / "static" / "branding").mkdir(parents=True)
    app = Flask(__name__, root_path=str(app_root))
    return app, app_root


def test_logo_data_uri_prefers_root_png(tmp_path):
    app, app_root = _make_app(tmp_path)
    (app_root.parent / "logo_panjang.png").write_bytes(b"png-binary")

    with app.app_context():
        data_uri = get_branding_logo_data_uri()

    assert data_uri == "data:image/png;base64,cG5nLWJpbmFyeQ=="


def test_logo_data_uri_returns_none_without_png_asset(tmp_path):
    app, _app_root = _make_app(tmp_path)

    with app.app_context():
        data_uri = get_branding_logo_data_uri()

    assert data_uri is None


def test_logo_mark_data_uri_prefers_root_png(tmp_path):
    app, _app_root = _make_app(tmp_path)
    (tmp_path / "logo.png").write_bytes(b"mark-binary")

    with app.app_context():
        data_uri = get_branding_logo_mark_data_uri()

    assert data_uri == "data:image/png;base64,bWFyay1iaW5hcnk="


def test_login_template_uses_branding_logo_data_uri():
    template_path = Path(__file__).resolve().parents[1] / "app" / "templates" / "auth" / "login.html"
    template_text = template_path.read_text(encoding="utf-8")

    assert "branding_logo_data_uri or ''" in template_text
    assert "branding_logo_mark_data_uri or ''" in template_text
    assert "logo_super_smart.svg" not in template_text
    assert "logo_mark_super_smart.svg" not in template_text


def test_invoice_templates_use_branding_logo_data_uri():
    project_root = Path(__file__).resolve().parents[1]
    payment_template = (project_root / "app" / "templates" / "payments" / "invoice.html").read_text(encoding="utf-8")
    quota_template = (project_root / "app" / "templates" / "quota" / "invoice_print.html").read_text(encoding="utf-8")
    fee_slip_template = (project_root / "app" / "templates" / "payroll" / "fee_slip.html").read_text(encoding="utf-8")

    assert payment_template.count("branding_logo_mark_data_uri or ''") == 1
    assert quota_template.count("branding_logo_mark_data_uri or ''") == 1
    assert "{% if branding_logo_mark_data_uri %}" in fee_slip_template
    assert '{{ branding_logo_mark_data_uri }}' in fee_slip_template
    assert "inv-illus" not in payment_template
    assert "inv-illus" not in quota_template
    assert "branding_logo_data_uri" not in payment_template
    assert "branding_logo_data_uri" not in quota_template
    assert "branding_logo_data_uri" not in fee_slip_template
    assert "logo_super_smart.svg" not in payment_template
    assert "logo_super_smart.svg" not in quota_template


def test_print_routes_use_logo_mark_helper():
    project_root = Path(__file__).resolve().parents[1]
    payments_route = (project_root / "app" / "routes" / "payments.py").read_text(encoding="utf-8")
    quota_route = (project_root / "app" / "routes" / "quota_invoice.py").read_text(encoding="utf-8")
    payroll_route = (project_root / "app" / "routes" / "payroll.py").read_text(encoding="utf-8")

    assert "get_branding_logo_mark_data_uri" in payments_route
    assert "branding_logo_mark_data_uri=get_branding_logo_mark_data_uri()" in payments_route
    assert "get_branding_logo_mark_data_uri" in quota_route
    assert "branding_logo_mark_data_uri=get_branding_logo_mark_data_uri()" in quota_route
    assert "get_branding_logo_mark_data_uri" in payroll_route
    assert "branding_logo_mark_data_uri=get_branding_logo_mark_data_uri()" in payroll_route
