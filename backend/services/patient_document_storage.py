"""Stockage fichiers questionnaires V2 — disque local ou S3/R2 (compatible API S3)."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)

UPLOAD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "uploads",
    "questionnaire_v2",
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".txt"}


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def s3_bucket() -> str:
    return _env("S3_BUCKET")


def use_s3_storage() -> bool:
    """True si bucket + credentials sont configurés."""
    if not s3_bucket():
        return False
    key = _env("AWS_ACCESS_KEY_ID") or _env("S3_ACCESS_KEY_ID")
    secret = _env("AWS_SECRET_ACCESS_KEY") or _env("S3_SECRET_ACCESS_KEY")
    return bool(key and secret)


def _object_key(storage_key: str) -> str:
    prefix = _env("S3_PREFIX").strip("/")
    key = (storage_key or "").lstrip("/")
    return f"{prefix}/{key}" if prefix else key


def _s3_client():
    import boto3

    endpoint = _env("S3_ENDPOINT_URL") or _env("AWS_ENDPOINT_URL")
    region = _env("S3_REGION") or _env("AWS_DEFAULT_REGION") or "eu-west-3"
    kwargs = {
        "service_name": "s3",
        "region_name": region,
        "aws_access_key_id": _env("AWS_ACCESS_KEY_ID") or _env("S3_ACCESS_KEY_ID"),
        "aws_secret_access_key": _env("AWS_SECRET_ACCESS_KEY") or _env("S3_SECRET_ACCESS_KEY"),
    }
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(**kwargs)


def _s3_put_object(storage_key: str, content: bytes, mime_type: str) -> None:
    client = _s3_client()
    client.put_object(
        Bucket=s3_bucket(),
        Key=_object_key(storage_key),
        Body=content,
        ContentType=mime_type or "application/octet-stream",
        ServerSideEncryption="AES256",
    )


def _s3_get_object(storage_key: str) -> bytes:
    client = _s3_client()
    resp = client.get_object(Bucket=s3_bucket(), Key=_object_key(storage_key))
    return resp["Body"].read()


def _s3_object_exists(storage_key: str) -> bool:
    client = _s3_client()
    try:
        client.head_object(Bucket=s3_bucket(), Key=_object_key(storage_key))
        return True
    except Exception as exc:
        code = ""
        try:
            code = str(getattr(exc, "response", {}).get("Error", {}).get("Code") or "")
        except Exception:
            pass
        if code in ("404", "NoSuchKey", "NotFound", "403"):
            return False
        logger.debug("s3 head_object failed for %s", storage_key, exc_info=True)
        return False


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
    """Écrit le fichier (S3 ou disque) et retourne (storage_key, stored_filename)."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Fichier trop volumineux (max 10 Mo).")
    ext = _safe_ext(original_name)
    if not ext:
        raise ValueError("Type de fichier non autorisé (PDF, images, Word, texte).")

    phone_norm = (patient_phone or "").strip()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_key = f"{tenant_id}/{phone_norm}/{request_id}/{stored_name}"

    if use_s3_storage():
        _s3_put_object(storage_key, content, mime_type)
        logger.info("questionnaire upload stored s3 key=%s", _object_key(storage_key))
    else:
        filepath = resolve_storage_path(storage_key)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(content)

    return storage_key, stored_name


def resolve_storage_path(storage_key: str) -> str:
    """Chemin local (mode disque uniquement)."""
    return os.path.join(UPLOAD_ROOT, storage_key)


def document_exists(storage_key: str) -> bool:
    if not storage_key:
        return False
    if use_s3_storage():
        return _s3_object_exists(storage_key)
    return os.path.isfile(resolve_storage_path(storage_key))


def read_document(storage_key: str) -> bytes:
    """Lit le contenu binaire (S3 ou disque)."""
    if use_s3_storage():
        return _s3_get_object(storage_key)
    filepath = resolve_storage_path(storage_key)
    with open(filepath, "rb") as f:
        return f.read()


def content_disposition_attachment(filename: str) -> str:
    name = (filename or "document").replace('"', "")
    encoded = quote(name)
    return f'attachment; filename="{name}"; filename*=UTF-8\'\'{encoded}'
