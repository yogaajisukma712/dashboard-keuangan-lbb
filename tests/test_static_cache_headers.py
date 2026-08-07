"""Tests for Fix B: cacheable static assets with automatic cache busting.

The response hooks under test live in ``app/__init__.py::register_response_hooks``
(the ``@app.after_request`` cache-header hook and the ``@app.url_defaults``
static version helper). They are attached directly to a minimal Flask app that
points at the real ``app/static`` folder, so the tests exercise the actual code
without requiring the PostgreSQL driver that ``create_app("testing")`` needs.
"""

import os
from pathlib import Path

from flask import Flask, url_for

from app import register_response_hooks

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "app" / "static"


def _make_app():
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config.update(SECRET_KEY="test-secret", SERVER_NAME="localhost")
    register_response_hooks(app)

    @app.route("/page")
    def page():
        return "<html><body>hi</body></html>"

    return app


def _existing_static_filename(app):
    filename = "js/persistent-filters.js"
    assert os.path.isfile(os.path.join(app.static_folder, filename))
    return filename


def test_url_defaults_appends_version_for_existing_static_file():
    app = _make_app()
    filename = _existing_static_filename(app)
    expected = int(os.stat(os.path.join(app.static_folder, filename)).st_mtime)
    with app.test_request_context("/"):
        built = url_for("static", filename=filename)
    assert "v=" in built
    assert "v={}".format(expected) in built


def test_url_defaults_silently_skips_missing_static_file():
    app = _make_app()
    with app.test_request_context("/"):
        built = url_for("static", filename="js/does-not-exist-xyz.js")
    assert "v=" not in built


def test_url_defaults_does_not_override_explicit_version():
    app = _make_app()
    filename = _existing_static_filename(app)
    with app.test_request_context("/"):
        built = url_for("static", filename=filename, v="pinned")
    assert "v=pinned" in built


def test_static_asset_with_version_is_long_lived_immutable():
    app = _make_app()
    filename = _existing_static_filename(app)
    client = app.test_client()
    response = client.get("/static/{}?v=123".format(filename))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert "Pragma" not in response.headers
    assert "Expires" not in response.headers


def test_static_asset_without_version_is_short_lived():
    app = _make_app()
    filename = _existing_static_filename(app)
    client = app.test_client()
    response = client.get("/static/{}".format(filename))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=60"


def test_static_asset_is_not_no_store():
    app = _make_app()
    filename = _existing_static_filename(app)
    client = app.test_client()
    for path in ("/static/{}".format(filename), "/static/{}?v=1".format(filename)):
        response = client.get(path)
        assert "no-store" not in response.headers.get("Cache-Control", "")


def test_html_pages_stay_uncacheable():
    app = _make_app()
    client = app.test_client()
    response = client.get("/page")
    cache_control = response.headers.get("Cache-Control", "")
    assert "no-store" in cache_control
    assert "no-cache" in cache_control
