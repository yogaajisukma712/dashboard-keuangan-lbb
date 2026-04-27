"""
Decorators utilities for Dashboard Keuangan LBB Super Smart
Custom decorators for authentication, authorization, and validation
"""

from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    """Decorator to require admin role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Anda harus login terlebih dahulu", "warning")
            return redirect(url_for("auth.login"))

        if current_user.role != "admin":
            flash("Anda tidak memiliki akses ke halaman ini", "danger")
            abort(403)

        return f(*args, **kwargs)

    return decorated_function


def manager_required(f):
    """Decorator to require manager or admin role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Anda harus login terlebih dahulu", "warning")
            return redirect(url_for("auth.login"))

        if current_user.role not in ["admin", "manager"]:
            flash("Anda tidak memiliki akses ke halaman ini", "danger")
            abort(403)

        return f(*args, **kwargs)

    return decorated_function


def login_required_custom(f):
    """Custom login required decorator"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Anda harus login terlebih dahulu", "warning")
            return redirect(url_for("auth.login", next=request.url))

        return f(*args, **kwargs)

    return decorated_function
