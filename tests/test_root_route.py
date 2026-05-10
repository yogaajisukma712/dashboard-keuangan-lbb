from pathlib import Path


def test_root_route_redirects_to_login():
    project_root = Path(__file__).resolve().parents[1]
    app_text = (project_root / "app" / "__init__.py").read_text(encoding="utf-8")

    assert '@app.route("/", methods=["GET"])' in app_text
    assert "def root():" in app_text
    assert "def enforce_domain_route_boundaries():" in app_text
    assert "MAIN_APP_HOSTS" in app_text
    assert 'allowed_prefixes = ("/tutor", "/auth/login", "/auth/logout", "/static/")' in app_text
    assert 'return redirect(url_for("auth.login"))' in app_text
