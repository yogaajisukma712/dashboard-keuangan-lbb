from app import create_app


def _make_app():
    app = create_app("testing")
    app.config.update(
        APP_BASE_URL="https://app.supersmart.click",
        MAIN_APP_HOSTS=("app.supersmart.click", "billing.supersmart.click"),
        TUTOR_PORTAL_BASE_URL="https://tutor.supersmart.click",
        TUTOR_PORTAL_HOST="tutor.supersmart.click",
        WTF_CSRF_ENABLED=False,
    )
    return app


def test_tutor_domain_redirects_main_dashboard_routes_to_tutor_portal():
    app = _make_app()

    response = app.test_client().get(
        "/dashboard/",
        headers={"Host": "tutor.supersmart.click"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/tutor/"


def test_main_domain_redirects_tutor_routes_to_tutor_domain():
    app = _make_app()

    response = app.test_client().get(
        "/tutor/login",
        headers={"Host": "app.supersmart.click"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "https://tutor.supersmart.click/tutor/login"


def test_tutor_domain_keeps_admin_login_available():
    app = _make_app()

    response = app.test_client().get(
        "/auth/login",
        headers={"Host": "tutor.supersmart.click"},
    )

    assert response.status_code == 200
