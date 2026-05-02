"""
Branding and QR helpers.
"""

from base64 import b64encode
from io import BytesIO
import mimetypes
import os
from pathlib import Path

from flask import current_app
import qrcode


def _file_to_data_uri(path, fallback_mimetype=None):
    """Return file content as a data URI if the file exists."""
    if not path or not os.path.exists(path):
        return None

    mimetype = fallback_mimetype or mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as fh:
        payload = b64encode(fh.read()).decode("ascii")
    return f"data:{mimetype};base64,{payload}"


def get_branding_logo_data_uri():
    """Load the preferred institution logo as a data URI."""
    for path, mimetype in _branding_asset_candidates(
        ("logo_panjang.png", "image/png"),
    ):
        data_uri = _file_to_data_uri(path, mimetype)
        if data_uri:
            return data_uri
    return None


def get_branding_logo_mark_data_uri():
    """Load the compact logo mark as a data URI."""
    for path, mimetype in _branding_asset_candidates(
        ("logo.png", "image/png"),
    ):
        data_uri = _file_to_data_uri(path, mimetype)
        if data_uri:
            return data_uri
    return None


def _branding_asset_candidates(*asset_specs):
    app_root = Path(current_app.root_path)
    project_root = app_root.parent
    for relative_path, mimetype in asset_specs:
        relative = Path(relative_path)
        for base_path in (project_root, app_root):
            candidate = base_path / relative
            yield str(candidate), mimetype


def build_qr_code_image_buffer(payload, box_size=6, border=1):
    """Build a QR code PNG in-memory for the given payload."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload or "-")
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def build_qr_code_data_uri(payload, box_size=6, border=1):
    """Build a QR code PNG data URI for HTML templates."""
    buffer = build_qr_code_image_buffer(payload, box_size=box_size, border=border)
    return f"data:image/png;base64,{b64encode(buffer.getvalue()).decode('ascii')}"
