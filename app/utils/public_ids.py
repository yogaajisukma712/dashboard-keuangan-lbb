"""
Public ID helpers for opaque URLs.
"""

from itsdangerous import BadSignature, URLSafeSerializer
from flask import current_app


PUBLIC_ID_SALT = "lbb-super-smart-public-id"


def _get_serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=PUBLIC_ID_SALT)


def encode_public_id(kind, raw_id):
    """Encode internal integer id into an opaque token."""
    return _get_serializer().dumps({"k": kind, "id": int(raw_id)})


def decode_public_id(token, expected_kind=None):
    """Decode opaque token back to integer id."""
    try:
        payload = _get_serializer().loads(token)
    except BadSignature as exc:
        raise ValueError("Invalid public id") from exc

    kind = payload.get("k")
    raw_id = payload.get("id")

    if expected_kind and kind != expected_kind:
        raise ValueError("Public id kind mismatch")

    try:
        return int(raw_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid public id payload") from exc
