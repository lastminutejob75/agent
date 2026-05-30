"""Stockage fichiers questionnaires V2 (disque local ; clé S3-ready)."""

from __future__ import annotations

import os
import uuid
from typing import Tuple

UPLOAD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "uploads",
    "questionnaire_v2",
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".txt"}


def _safe_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()[:10]
    return ext if ext in ALLOWED_EXTENSIONS else ""


def save_questionnaire_upload(
    tenant_id: int,
    patient_phone: str,
    request_id: str,
    content: bytes,
    original_name: str,
    mime_type: str,
) -> Tuple[str, str]:
    """Écrit le fichier et retourne (storage_key, stored_filename)."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Fichier trop volumineux (max 10 Mo).")
    ext = _safe_ext(original_name)
    if not ext:
        raise ValueError("Type de fichier non autorisé (PDF, images, Word, texte).")

    phone_norm = (patient_phone or "").strip()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_key = f"{tenant_id}/{phone_norm}/{request_id}/{stored_name}"
    filepath = os.path.join(UPLOAD_ROOT, storage_key)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(content)
    return storage_key, stored_name


def resolve_storage_path(storage_key: str) -> str:
    return os.path.join(UPLOAD_ROOT, storage_key)
