import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect
from markupsafe import Markup, escape

from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    """Application factory"""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan login terlebih dahulu"

    # Configure logging
    setup_logging(app)

    # Register blueprints
    register_blueprints(app)

    # Exempt selected JSON/AJAX endpoints that currently post without CSRF token
    if "payroll.api_quick_pay" in app.view_functions:
        csrf.exempt(app.view_functions["payroll.api_quick_pay"])
    if "whatsapp_api.sync" in app.view_functions:
        csrf.exempt(app.view_functions["whatsapp_api.sync"])

    # Exempt data_manager write/API endpoints (JSON only, protected by login_required)
    _dm_exempt = [
        "data_manager.delete_row",
        "data_manager.update_row",
        "data_manager.insert_row",
        "data_manager.restore_sql",
    ]
    for _vf in _dm_exempt:
        if _vf in app.view_functions:
            csrf.exempt(app.view_functions[_vf])

    # Register context processors
    register_context_processors(app)

    # Register template filters
    register_template_filters(app)

    # Register response hooks
    register_response_hooks(app)

    # Register error handlers
    register_error_handlers(app)

    # Create shell context for flask shell
    @app.shell_context_processor
    def make_shell_context():
        from app.models import (
            AttendanceSession,
            Curriculum,
            Enrollment,
            EnrollmentSchedule,
            Expense,
            Level,
            MonthlyClosing,
            OtherIncome,
            PricingRule,
            Student,
            StudentPayment,
            StudentPaymentLine,
            Subject,
            Tutor,
            TutorPayout,
            TutorPayoutLine,
            User,
        )

        return {
            "db": db,
            "User": User,
            "Student": Student,
            "Tutor": Tutor,
            "Subject": Subject,
            "Curriculum": Curriculum,
            "Level": Level,
            "PricingRule": PricingRule,
            "Enrollment": Enrollment,
            "EnrollmentSchedule": EnrollmentSchedule,
            "AttendanceSession": AttendanceSession,
            "StudentPayment": StudentPayment,
            "StudentPaymentLine": StudentPaymentLine,
            "OtherIncome": OtherIncome,
            "Expense": Expense,
            "TutorPayout": TutorPayout,
            "TutorPayoutLine": TutorPayoutLine,
            "MonthlyClosing": MonthlyClosing,
        }

    return app


def register_template_filters(app):
    """Register small presentation helpers used by templates."""

    @app.template_filter("nl2br")
    def nl2br(value):
        if value is None:
            return ""
        return Markup("<br>".join(str(escape(value)).splitlines()))


def register_blueprints(app):
    """Register all blueprints"""
    from app.routes import (
        attendance_bp,
        auth_bp,
        closings_bp,
        dashboard_bp,
        data_manager_bp,
        enrollments_bp,
        expenses_bp,
        incomes_bp,
        master_bp,
        payments_bp,
        payroll_bp,
        reports_bp,
        whatsapp_bot_bp,
        whatsapp_bp,
    )
    from app.routes.quota_invoice import quota_invoice_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(data_manager_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(enrollments_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(incomes_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(closings_bp)
    app.register_blueprint(quota_invoice_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(whatsapp_bot_bp)


def register_context_processors(app):
    """Register context processors for templates"""

    from app.utils import (
        DEFAULT_PER_PAGE,
        PER_PAGE_OPTIONS,
        get_branding_logo_data_uri,
        get_branding_logo_mark_data_uri,
        pagination_url,
    )

    @app.context_processor
    def inject_config():
        return {
            "app_name": "Dashboard Keuangan LBB Super Smart",
            "pagination_per_page": app.config["PAGINATION_PER_PAGE"],
            "per_page_options": PER_PAGE_OPTIONS,
            "default_per_page": DEFAULT_PER_PAGE,
            "pagination_url": pagination_url,
            "branding_logo_data_uri": get_branding_logo_data_uri(),
            "branding_logo_mark_data_uri": get_branding_logo_mark_data_uri(),
        }

    @app.context_processor
    def inject_quota_alert_count():
        """Inject jumlah quota alert ke semua template untuk badge di navbar."""
        from flask_login import current_user

        if not current_user.is_authenticated:
            return {"quota_alert_count": 0}
        try:
            from app.routes.quota_invoice import count_quota_alerts

            return {"quota_alert_count": count_quota_alerts()}
        except Exception:
            return {"quota_alert_count": 0}


def register_response_hooks(app):
    """Register response hooks such as anti-cache headers for HTML pages."""

    @app.after_request
    def apply_no_cache_headers(response):
        content_type = (response.content_type or "").lower()
        if (
            content_type.startswith("text/html")
            or content_type.startswith("text/css")
            or "javascript" in content_type
            or request.path.startswith("/static/")
        ):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0, private"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


def _request_wants_json():
    """Return True if the current request expects a JSON response."""
    if request.path.startswith("/dashboard/api") or request.path.startswith("/api/"):
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    if (
        best == "application/json"
        and request.accept_mimetypes["application/json"]
        > request.accept_mimetypes["text/html"]
    ):
        return True
    if request.is_json:
        return True
    return False


def register_error_handlers(app):
    """Register error handlers"""

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        db.session.rollback()
        if _request_wants_json():
            return jsonify(
                {"error": "CSRF token tidak valid atau sudah kedaluwarsa"}
            ), 400
        try:
            return render_template("errors/403.html", error=str(error)), 400
        except Exception:
            return jsonify(
                {"error": "CSRF token tidak valid atau sudah kedaluwarsa"}
            ), 400

    @app.errorhandler(404)
    def not_found(error):
        if _request_wants_json():
            return jsonify({"error": "Halaman tidak ditemukan"}), 404
        try:
            return render_template("errors/404.html", error=error), 404
        except Exception:
            return jsonify({"error": "Halaman tidak ditemukan"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        import traceback

        db.session.rollback()
        app.logger.error(f"Server error: {error}\n{traceback.format_exc()}")
        if _request_wants_json():
            return jsonify({"error": "Terjadi kesalahan pada server"}), 500
        try:
            return render_template("errors/500.html", error=str(error)), 500
        except Exception:
            return jsonify({"error": "Terjadi kesalahan pada server"}), 500

    @app.errorhandler(403)
    def forbidden(error):
        if _request_wants_json():
            return jsonify({"error": "Anda tidak memiliki akses ke halaman ini"}), 403
        try:
            return render_template("errors/403.html", error=error), 403
        except Exception:
            return jsonify({"error": "Anda tidak memiliki akses ke halaman ini"}), 403


def setup_logging(app):
    """Setup application logging"""
    if not app.debug:
        if not os.path.exists("logs"):
            os.mkdir("logs")

        file_handler = RotatingFileHandler(
            app.config["LOG_FILE"], maxBytes=10240000, backupCount=10
        )

        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )

        file_handler.setLevel(getattr(logging, app.config["LOG_LEVEL"]))
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, app.config["LOG_LEVEL"]))
        app.logger.info("Dashboard Keuangan LBB Super Smart startup")
