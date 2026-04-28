"""
Authentication routes for Dashboard Keuangan LBB Super Smart
Handles login, logout, and registration
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.forms import LoginForm, RegisterForm
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login route"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.owner_dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user is None or not user.check_password(form.password.data):
            flash("Username atau password salah", "danger")
            return redirect(url_for("auth.login"))

        if not user.is_active:
            flash("User tidak aktif", "warning")
            return redirect(url_for("auth.login"))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")

        if not next_page or not url_has_allowed_host_and_scheme(next_page):
            next_page = url_for("dashboard.owner_dashboard")

        return redirect(next_page)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    """Logout route"""
    logout_user()
    flash("Anda telah logout", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register route - untuk setup awal atau admin only"""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.owner_dashboard"))

    if User.query.count() > 0:
        flash(
            "Registrasi publik sudah ditutup. Hubungi admin untuk pembuatan akun.",
            "warning",
        )
        return redirect(url_for("auth.login"))

    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(username=form.username.data).first():
            flash("Username sudah digunakan", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=form.email.data).first():
            flash("Email sudah didaftarkan", "danger")
            return redirect(url_for("auth.register"))

        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            role="user",
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Registrasi berhasil! Silakan login", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


def url_has_allowed_host_and_scheme(url, allowed_hosts=None):
    """
    Check if URL is safe for redirect
    """
    if allowed_hosts is None:
        allowed_hosts = {"localhost", "127.0.0.1"}

    if url.startswith(("http://", "https://", "//")):
        return False

    if url.startswith("/"):
        return True

    return False
