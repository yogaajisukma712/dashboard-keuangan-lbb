"""
Central Flask extensions for Dashboard Keuangan LBB Super Smart.

This module exists to avoid circular imports by keeping extension instances
separate from the application factory.
"""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
