import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name=None):
    """Application factory"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('logs', exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu'

    # Configure logging
    setup_logging(app)

    # Register blueprints
    register_blueprints(app)

    # Register context processors
    register_context_processors(app)

    # Register error handlers
    register_error_handlers(app)

    # Create shell context for flask shell
    @app.shell_context_processor
    def make_shell_context():
        from app.models import (
            User, Student, Tutor, Subject, Curriculum, Level,
            PricingRule, Enrollment, EnrollmentSchedule,
            AttendanceSession, StudentPayment, StudentPaymentLine,
            OtherIncome, Expense, TutorPayout, TutorPayoutLine, MonthlyClosing
        )
        return {
            'db': db,
            'User': User, 'Student': Student, 'Tutor': Tutor,
            'Subject': Subject, 'Curriculum': Curriculum, 'Level': Level,
            'PricingRule': PricingRule, 'Enrollment': Enrollment,
            'EnrollmentSchedule': EnrollmentSchedule,
            'AttendanceSession': AttendanceSession,
            'StudentPayment': StudentPayment, 'StudentPaymentLine': StudentPaymentLine,
            'OtherIncome': OtherIncome, 'Expense': Expense,
            'TutorPayout': TutorPayout, 'TutorPayoutLine': TutorPayoutLine,
            'MonthlyClosing': MonthlyClosing
        }

    return app

def register_blueprints(app):
    """Register all blueprints"""
    from app.routes import (
        auth_bp, master_bp, enrollments_bp, attendance_bp,
        payments_bp, incomes_bp, expenses_bp, payroll_bp,
        dashboard_bp, reports_bp, closings_bp
    )

    app.register_blueprint(auth_bp)
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

def register_context_processors(app):
    """Register context processors for templates"""
    @app.context_processor
    def inject_config():
        return {
            'app_name': 'Dashboard Keuangan LBB Super Smart',
            'pagination_per_page': app.config['PAGINATION_PER_PAGE']
        }

def register_error_handlers(app):
    """Register error handlers"""
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Halaman tidak ditemukan'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Server error: {error}')
        return {'error': 'Terjadi kesalahan pada server'}, 500

    @app.errorhandler(403)
    def forbidden(error):
        return {'error': 'Anda tidak memiliki akses ke halaman ini'}, 403

def setup_logging(app):
    """Setup application logging"""
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')

        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=10240000,
            backupCount=10
        )

        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))

        file_handler.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))
        app.logger.info('Dashboard Keuangan LBB Super Smart startup')
