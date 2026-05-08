from pathlib import Path

from flask import Flask

from app.utils.pagination import (
    DEFAULT_PER_PAGE,
    PER_PAGE_OPTIONS,
    get_per_page,
    pagination_url,
)


def test_get_per_page_accepts_only_safe_options():
    app = Flask(__name__)

    with app.test_request_context("/students?per_page=50"):
        assert get_per_page() == 50

    with app.test_request_context("/students?per_page=999"):
        assert get_per_page() == DEFAULT_PER_PAGE

    with app.test_request_context("/students?per_page=abc"):
        assert get_per_page() == DEFAULT_PER_PAGE

    assert 250 in PER_PAGE_OPTIONS


def test_pagination_url_preserves_filters_and_per_page():
    app = Flask(__name__)

    @app.route("/items")
    def items():
        return "ok"

    with app.test_request_context("/items?search=salsa&active_state=active&per_page=50"):
        assert (
            pagination_url(3)
            == "/items?search=salsa&active_state=active&per_page=50&page=3"
        )


def test_large_table_templates_include_per_page_selector():
    project_root = Path(__file__).resolve().parents[1]
    template_paths = [
        "app/templates/master/students_list.html",
        "app/templates/master/tutors_list.html",
        "app/templates/master/subjects_list.html",
        "app/templates/master/curriculums_list.html",
        "app/templates/master/pricing_list.html",
        "app/templates/enrollments/list.html",
        "app/templates/attendance/list.html",
        "app/templates/expenses/list.html",
        "app/templates/incomes/list.html",
        "app/templates/payments/list.html",
        "app/templates/payments/student_payment_history.html",
        "app/templates/quota/invoice_list.html",
    ]

    for relative_path in template_paths:
        template_text = (project_root / relative_path).read_text(encoding="utf-8")
        assert "components/per_page_select.html" in template_text
        assert "pagination_url(" in template_text


def test_whatsapp_tables_have_client_side_page_size_selectors():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "whatsapp" / "management.html"
    ).read_text(encoding="utf-8")

    assert "groupsPageSizeSelect" in template_text
    assert "contactsPageSizeSelect" in template_text
    assert "readPageSize(" in template_text


def test_saved_filter_restore_does_not_force_page_reload():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (project_root / "app" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )

    assert "window.location.replace(currentUrl.toString())" not in template_text
    assert 'window.history.replaceState({}, "", currentUrl.toString())' in template_text
    assert "window.__lbbPendingFilterRestores.push" in template_text
    assert "processPendingFilterRestores();" in template_text


def test_payment_list_filter_uses_month_year_and_calendar_range():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payments" / "list.html"
    ).read_text(encoding="utf-8")
    route_text = (project_root / "app" / "routes" / "payments.py").read_text(
        encoding="utf-8"
    )

    assert 'name="month"' in template_text
    assert 'name="year"' in template_text
    assert 'id="paymentDateRangeButton"' in template_text
    assert 'id="paymentCalendarGrid"' in template_text
    assert "selectPaymentRangeDate" in template_text
    assert 'request.args.get("month", type=int)' in route_text
    assert 'request.args.get("year", type=int)' in route_text
    assert 'extract("month", StudentPayment.payment_date)' in route_text
    assert 'extract("year", StudentPayment.payment_date)' in route_text


def test_payment_list_has_verify_action():
    project_root = Path(__file__).resolve().parents[1]
    template_text = (
        project_root / "app" / "templates" / "payments" / "list.html"
    ).read_text(encoding="utf-8")
    route_text = (project_root / "app" / "routes" / "payments.py").read_text(
        encoding="utf-8"
    )

    assert "payments.verify_payment" in template_text
    assert 'name="is_verified" value="1"' in template_text
    assert 'name="is_verified" value="0"' in template_text
    assert 'name="next" value="{{ request.full_path }}"' in template_text
    assert 'def verify_payment(payment_ref):' in route_text
    assert 'payment.is_verified = target in {"1", "true"}' in route_text
