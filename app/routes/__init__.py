"""
Routes package for Dashboard Keuangan LBB Super Smart
This package contains all Flask blueprints for routing.
"""

from flask import Blueprint

# Import blueprints
from .auth import auth_bp
from .master import master_bp
from .enrollments import enrollments_bp
from .attendance import attendance_bp
from .payments import payments_bp
from .incomes import incomes_bp
from .expenses import expenses_bp
from .payroll import payroll_bp
from .dashboard import dashboard_bp
from .reports import reports_bp
from .closings import closings_bp

__all__ = [
    'auth_bp',
    'master_bp',
    'enrollments_bp',
    'attendance_bp',
    'payments_bp',
    'incomes_bp',
    'expenses_bp',
    'payroll_bp',
    'dashboard_bp',
    'reports_bp',
    'closings_bp'
]
