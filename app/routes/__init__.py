"""
Routes package for Dashboard Keuangan LBB Super Smart
This package contains all Flask blueprints for routing.
"""

from flask import Blueprint

from .attendance import attendance_bp

# Import blueprints
from .auth import auth_bp
from .closings import closings_bp
from .dashboard import dashboard_bp
from .data_manager import data_manager_bp
from .enrollments import enrollments_bp
from .expenses import expenses_bp
from .incomes import incomes_bp
from .master import master_bp
from .payments import payments_bp
from .payroll import payroll_bp
from .quota_invoice import quota_invoice_bp
from .reports import reports_bp
from .tutor_portal import tutor_portal_bp
from .whatsapp import whatsapp_bot_bp, whatsapp_bp

__all__ = [
    "auth_bp",
    "data_manager_bp",
    "master_bp",
    "enrollments_bp",
    "attendance_bp",
    "payments_bp",
    "incomes_bp",
    "expenses_bp",
    "payroll_bp",
    "dashboard_bp",
    "reports_bp",
    "tutor_portal_bp",
    "closings_bp",
    "quota_invoice_bp",
    "whatsapp_bp",
    "whatsapp_bot_bp",
]
