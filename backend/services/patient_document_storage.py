"""Stockage fichiers questionnaires V2 — disque local ou S3-compatible (AWS, R2, OVH)."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Dict, Tuple
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


def _access_key() -> str:
    return (
        _env("AWS_ACCESS_KEY_ID")
        or _env("S3_ACCESS_KEY_ID")
        or _env("OVH_ACCESS_KEY_ID")
    )


def _secret_key() -> str:
    return (
        _env("AWS_SECRET_ACCESS_KEY")
        or _env("S3_SECRET_ACCESS_KEY")
        or _env("OVH_SECRET_ACCESS_KEY")
    )


def s3_bucket() -> str:
    return _env("S3_BUCKET") or _env("OVH_S3_BUCKET")


def _provider() -> str:
    return _env("S3_PROVIDER").lower()


def _endpoint_url() -> str:
    """URL S3-compatible (AWS, Cloudflare R2, OVH Object Storage, MinIO…)."""
    explicit = (
        _env("S3_ENDPOINT_URL")
        or _env("AWS_ENDPOINT_URL")
        or _env("OVH_S3_ENDPOINT")
    )
    if explicit:
        url = explicit if "://" in explicit else f"https://{explicit}"
        return url.rstrip("/")

    if _provider() == "ovh" or _env("OVH_S3_REGION"):
        region = (_env("OVH_S3_REGION") or "gra").lower()
        return f"https://s3.{region}.io.cloud.ovh.net"

    return ""


def _region_name() -> str:
    return (
        _env("S3_REGION")
        or _env("AWS_DEFAULT_REGION")
        or _env("OVH_S3_REGION")
        or "eu-west-3"
    ).lower()


def storage_backend_label() -> str:
    if not use_s3_storage():
        return "local"
    endpoint = _endpoint_url()
    if _provider() == "ovh" or _env("OVH_S3_REGION") or ".io.cloud.ovh.net" in endpoint:
        return "ovh"
    if "r2.cloudflarestorage.com" in endpoint:
        return "r2"
    return "s3"


def use_s3_storage() -> bool:
    """True si bucket + credentials sont configurés."""
    if not s3_bucket():
        return False
    return bool(_access_key() and _secret_key())


def _object_key(storage_key: str) -> str:
    prefix = _env("S3_PREFIX").strip("/")
    key = (storage_key or "").lstrip("/")
    return f"{prefix}/{key}" if prefix else key


def _s3_boto_config():
    from botocore.config import Config

    style = _env("S3_ADDRESSING_STYLE").lower()
    if not style:
        # OVH et la plupart des endpoints non-AWS : path-style plus fiable.
        style = "path" if _endpoint_url() else "auto"
    config_kwargs: Dict[str, object] = {"signature_version": "s3v4"}
    if style in ("path", "virtual"):
        config_kwargs["s3"] = {"addressing_style": style}
    return Config(**config_kwargs)


def _s3_client():
    import boto3

    kwargs = {
        "service_name": "s3",
        "region_name": _region_name(),
        "aws_access_key_id": _access_key(),
        "aws_secret_access_key": _secret_key(),
        "config": _s3_boto_config(),
    }
    endpoint = _endpoint_url()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(**kwargs)


def _put_object_extra() -> Dict[str, str]:
    """Chiffrement côté serveur (AWS oui ; OVH/R2 : désactivable via S3_SERVER_SIDE_ENCRYPTION=none)."""
    sse = _env("S3_SERVER_SIDE_ENCRYPTION", "AES256")
    if sse.lower() in ("0", "false", "no", "off", "none", "disabled"):
        return {}
    return {"ServerSideEncryption": sse}


def _s3_put_object(storage_key: str, content: bytes, mime_type: str) -> None:
    client = _s3_client()
    params = {
        "Bucket": s3_bucket(),
        "Key": _object_key(storage_key),
        "Body": content,
        "ContentType": mime_type or "application/octet-stream",
        **_put_object_extra(),
    }
    client.put_object(**params)


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
    """Écrit le fichier (S3-compatible ou disque) et retourne (storage_key, stored_filename)."""
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
        logger.info(
            "questionnaire upload stored backend=%s key=%s",
            storage_backend_label(),
            _object_key(storage_key),
        )
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
    """Lit le contenu binaire (S3-compatible ou disque)."""
    if use_s3_storage():
        return _s3_get_object(storage_key)
    filepath = resolve_storage_path(storage_key)
    with open(filepath, "rb") as f:
        return f.read()


def content_disposition_attachment(filename: str) -> str:
    name = (filename or "document").replace('"', "")
    encoded = quote(name)
    return f'attachment; filename="{name}"; filename*=UTF-8\'\'{encoded}'
