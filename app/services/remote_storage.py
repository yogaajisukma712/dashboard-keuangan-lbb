"""Remote file storage — simpan file upload di VM bot.

Vercel filesystem read-only: `file.save()` gagal. Helper ini mengalihkan
penyimpanan ke endpoint bot (`PUT /files/*` di WHATSAPP_BOT_INTERNAL_URL,
auth X-Bot-Token). Di lingkungan non-serverless, file tetap disimpan lokal
(container DO#1/DO2 memakai volume).
"""

import os

import requests
from flask import current_app


def _bot_base() -> str:
    return (os.getenv("WHATSAPP_BOT_INTERNAL_URL") or "").rstrip("/")


def _bot_token() -> str:
    return os.getenv("WHATSAPP_BOT_TOKEN") or ""


def is_remote_storage_enabled() -> bool:
    """Aktif hanya di Vercel (FS read-only). Di container, disk lokal dipakai."""
    return bool(os.getenv("VERCEL")) and bool(_bot_base())


def save_remote_file(relative_path: str, file_bytes: bytes) -> str:
    """Kirim file ke bot. Return relative_path (nilai yang disimpan ke DB)."""
    if not is_remote_storage_enabled():
        raise RuntimeError("Remote storage tidak aktif")
    url = f"{_bot_base()}/files/{relative_path}"
    resp = requests.put(
        url,
        data=file_bytes,
        headers={"X-Bot-Token": _bot_token(), "Content-Type": "application/octet-stream"},
        timeout=30,
    )
    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", resp.text[:120])
        except Exception:
            detail = resp.text[:120]
        raise RuntimeError(f"Gagal simpan file ke bot: {resp.status_code} {detail}")
    return relative_path


def fetch_remote_file(relative_path: str) -> bytes | None:
    """Ambil isi file dari bot (untuk streaming route). None jika tak ada."""
    if not is_remote_storage_enabled():
        return None
    url = f"{_bot_base()}/files/{relative_path}"
    try:
        resp = requests.get(
            url,
            headers={"X-Bot-Token": _bot_token()},
            timeout=30,
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    return resp.content
