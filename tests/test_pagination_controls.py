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


def test_saved_filter_restore_uses_pre_paint_contract_not_paint_then_reload():
    """Saved filters are restored by a blocking <head> script BEFORE first
    paint, keyed by an ``lbb:lastquery`` index, with a one-shot sessionStorage
    loop guard. The old paint-then-reload navigation inside
    ``persistent-filters.js`` must be gone."""
    project_root = Path(__file__).resolve().parents[1]
    script_text = (
        project_root / "app" / "static" / "js" / "persistent-filters.js"
    ).read_text(encoding="utf-8")
    base_text = (
        project_root / "app" / "templates" / "base.html"
    ).read_text(encoding="utf-8")
    tutor_base_text = (
        project_root / "app" / "templates" / "tutor_portal" / "base.html"
    ).read_text(encoding="utf-8")

    # The visible paint-then-reload restore navigation is removed: restoreFromStorage
    # no longer loads saved forms, merges them into the URL, and re-navigates.
    assert "mergeRestoredSearch(url.search, restorations)" not in script_text
    assert ".map(loadForm)" not in script_text

    # restoreFromStorage is now non-navigating (only performs reset_filters
    # cleanup) and the head script owns restoration instead.
    assert "function restoreFromStorage(_forms)" in script_text

    # The module now maintains the last-query index used by the head script.
    assert "lbb:lastquery:v1:" in script_text
    assert "function writeLastQuery(" in script_text

    # Both layouts own restoration via a pre-paint head script that:
    #  - reads/writes the lbb:lastquery index,
    #  - redirects with location.replace(pathname + storedQuery),
    #  - guards against redirect loops with a one-shot sessionStorage marker.
    for text in (base_text, tutor_base_text):
        assert "lbb:lastquery:v1:" in text
        assert "loc.replace(pathname + stored)" in text
        assert "lbb:lastquery-guard:" in text
        assert "window.sessionStorage" in text
        assert 'current.get("reset_filters") === "1"' in text


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
