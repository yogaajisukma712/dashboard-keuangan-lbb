"""
Internal API endpoints for WhatsApp bot ingestion.
"""

from __future__ import annotations

import json
import os
from urllib import error, request as urllib_request

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.services import WhatsAppIngestService
from app.utils.decorators import admin_required

whatsapp_bp = Blueprint("whatsapp_api", __name__, url_prefix="/api/whatsapp")
whatsapp_bot_bp = Blueprint("whatsapp_bot", __name__, url_prefix="/whatsapp")


def _extract_token() -> str:
    bearer = request.headers.get("Authorization", "")
    if bearer.startswith("Bearer "):
        return bearer.split(" ", 1)[1].strip()
    return request.headers.get("X-WhatsApp-Bot-Token", "").strip()


def _require_bot_token():
    configured = os.getenv("WHATSAPP_BOT_TOKEN", "").strip()
    provided = _extract_token()
    if not configured or provided != configured:
        return jsonify({"error": "Unauthorized bot token"}), 401
    return None


def _bot_base_url() -> str:
    return current_app.config["WHATSAPP_BOT_INTERNAL_URL"].rstrip("/")


def _bot_request(method: str, path: str, payload: dict | None = None):
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib_request.Request(
        f"{_bot_base_url()}{path}",
        data=body,
        method=method.upper(),
        headers=headers,
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            data = json.loads(text) if text else {}
            return data, response.status
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            data = {"ok": False, "error": text or str(exc)}
        return data, exc.code
    except Exception as exc:
        return {"ok": False, "error": str(exc)}, 502


@whatsapp_bot_bp.route("/", methods=["GET"])
@login_required
@admin_required
def index():
    return redirect(url_for("whatsapp_bot.management"))


@whatsapp_bot_bp.route("/management", methods=["GET"])
@login_required
@admin_required
def management():
    return render_template(
        "whatsapp/management.html",
        excluded_group_names=WhatsAppIngestService.get_excluded_group_names(),
    )


@whatsapp_bot_bp.route("/api/session", methods=["GET"])
@login_required
@admin_required
def bot_session():
    payload, status_code = _bot_request("GET", "/session")
    return jsonify(payload), status_code


@whatsapp_bot_bp.route("/api/session/initialize", methods=["POST"])
@login_required
@admin_required
def bot_session_initialize():
    payload, status_code = _bot_request("POST", "/session/initialize", {})
    return jsonify(payload), status_code


@whatsapp_bot_bp.route("/api/session/logout", methods=["POST"])
@login_required
@admin_required
def bot_session_logout():
    payload, status_code = _bot_request("POST", "/session/logout", {})
    return jsonify(payload), status_code


@whatsapp_bot_bp.route("/api/groups", methods=["GET"])
@login_required
@admin_required
def bot_groups():
    payload, status_code = _bot_request("GET", "/groups")
    return jsonify(payload), status_code


@whatsapp_bot_bp.route("/api/group-directory", methods=["GET"])
@login_required
@admin_required
def bot_group_directory():
    limit = request.args.get("limit", default=3, type=int) or 3
    groups = WhatsAppIngestService.list_groups_with_student_suggestions(
        limit_per_group=max(1, min(limit, 10))
    )
    students = WhatsAppIngestService.list_active_students()
    return jsonify(
        {
            "ok": True,
            "groups": groups,
            "students": students,
            "excluded_groups": WhatsAppIngestService.get_excluded_group_names(),
        }
    )


@whatsapp_bot_bp.route("/api/contact-directory", methods=["GET"])
@login_required
@admin_required
def bot_contact_directory():
    limit = request.args.get("limit", default=3, type=int) or 3
    contacts = WhatsAppIngestService.list_group_contacts_with_tutor_suggestions(
        limit_per_contact=max(1, min(limit, 10))
    )
    students = WhatsAppIngestService.list_active_students()
    tutors = WhatsAppIngestService.list_active_tutors()
    return jsonify(
        {
            "ok": True,
            "contacts": contacts,
            "students": students,
            "tutors": tutors,
            "excluded_groups": WhatsAppIngestService.get_excluded_group_names(),
        }
    )


@whatsapp_bot_bp.route("/api/contact-directory/validate", methods=["POST"])
@login_required
@admin_required
def bot_contact_directory_validate():
    payload = request.get_json(silent=True) or {}
    contact_id = payload.get("contact_id")
    tutor_id = payload.get("tutor_id")
    if not contact_id or not tutor_id:
        return jsonify({"error": "contact_id dan tutor_id wajib diisi."}), 400

    try:
        result = WhatsAppIngestService.validate_contact_as_tutor(
            int(contact_id), int(tutor_id)
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "validation": result})


@whatsapp_bot_bp.route("/api/contact-directory/validate-student", methods=["POST"])
@login_required
@admin_required
def bot_contact_directory_validate_student():
    payload = request.get_json(silent=True) or {}
    contact_id = payload.get("contact_id")
    student_id = payload.get("student_id")
    if not contact_id or not student_id:
        return jsonify({"error": "contact_id dan student_id wajib diisi."}), 400

    try:
        result = WhatsAppIngestService.validate_contact_as_student(
            int(contact_id), int(student_id)
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "validation": result})


@whatsapp_bot_bp.route("/api/group-directory/validate-student", methods=["POST"])
@login_required
@admin_required
def bot_group_directory_validate_student():
    payload = request.get_json(silent=True) or {}
    group_id = payload.get("group_id")
    student_id = payload.get("student_id")
    if not group_id or not student_id:
        return jsonify({"error": "group_id dan student_id wajib diisi."}), 400

    try:
        result = WhatsAppIngestService.validate_group_as_student(
            int(group_id), int(student_id)
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "validation": result})


@whatsapp_bot_bp.route("/api/sync/groups", methods=["POST"])
@login_required
@admin_required
def bot_sync_groups():
    payload, status_code = _bot_request(
        "POST",
        "/sync/groups",
        request.get_json(silent=True) or {},
    )
    return jsonify(payload), status_code


@whatsapp_bot_bp.route("/api/sync/messages/full", methods=["POST"])
@login_required
@admin_required
def bot_sync_messages_full():
    payload, status_code = _bot_request(
        "POST",
        "/sync/messages/full",
        request.get_json(silent=True) or {},
    )
    return jsonify(payload), status_code


@whatsapp_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "whatsapp-ingest-api"})


@whatsapp_bp.route("/sync", methods=["POST"])
def sync():
    unauthorized = _require_bot_token()
    if unauthorized is not None:
        return unauthorized

    payload = request.get_json(silent=True) or {}
    result = WhatsAppIngestService.ingest_sync_payload(payload)
    return jsonify({"ok": True, "result": result})
