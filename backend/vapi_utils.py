"""
Utilitaires Vapi : création d'assistants, assignation numéros Twilio.
Utilisé par POST /api/admin/tenants/create.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

VAPI_API_URL = "https://api.vapi.ai"
FAQ_START_MARKER = "=== FAQ DU CABINET ==="
FAQ_END_MARKER = "=== FIN FAQ ==="

# Mapping assistant_id → voix Vapi (Azure)
ASSISTANT_VOICES: Dict[str, Dict[str, str]] = {
    "sophie": {"provider": "azure", "voiceId": "fr-FR-DeniseNeural"},
    "laura": {"provider": "azure", "voiceId": "fr-FR-YvetteNeural"},
    "emma": {"provider": "azure", "voiceId": "fr-FR-EloiseNeural"},
    "julie": {"provider": "azure", "voiceId": "fr-FR-CoralieNeural"},
    "clara": {"provider": "azure", "voiceId": "fr-FR-CelesteNeural"},
    "hugo": {"provider": "azure", "voiceId": "fr-FR-HenriNeural"},
    "julien": {"provider": "azure", "voiceId": "fr-FR-AlainNeural"},
    "nicolas": {"provider": "azure", "voiceId": "fr-FR-ClaudeNeural"},
    "alexandre": {"provider": "azure", "voiceId": "fr-FR-JeromeNeural"},
    "thomas": {"provider": "azure", "voiceId": "fr-FR-RemiNeural"},
}

# Mapping secteur → instructions système
SECTOR_PROMPTS: Dict[str, str] = {
    "medecin_generaliste": "Tu es l'assistante téléphonique du cabinet du Dr {name}. Tu réponds aux patients, gères les prises de rendez-vous et transfères les urgences.",
    "specialiste": "Tu es l'assistante téléphonique du cabinet spécialisé {name}. Tu gères les rendez-vous et renseignes les patients.",
    "kine": "Tu es l'assistante du cabinet de kinésithérapie {name}. Tu prends les rendez-vous et réponds aux questions courantes.",
    "dentiste": "Tu es l'assistante du cabinet dentaire {name}. Tu gères les rendez-vous et transfères les urgences dentaires.",
    "infirmier": "Tu es l'assistante du cabinet infirmier {name}. Tu gères les tournées et les rendez-vous de soins.",
}


def _vapi_api_key() -> str:
    key = (os.environ.get("VAPI_API_KEY") or "").strip()
    if not key:
        raise ValueError("VAPI_API_KEY non configuré")
    return key


def _looks_like_backend_base_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    host = (parsed.netloc or "").lower()
    if not host:
        return False
    if host.startswith("api."):
        return True
    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        return True
    if host.endswith(".up.railway.app") or host.endswith(".railway.app"):
        return True
    return False


def get_public_backend_base_url() -> str:
    for env_name in ("VAPI_PUBLIC_BACKEND_URL", "PUBLIC_API_BASE_URL", "API_BASE_URL"):
        value = (os.environ.get(env_name) or "").strip().rstrip("/")
        if value:
            return value

    app_base = (os.environ.get("APP_BASE_URL") or "").strip().rstrip("/")
    if app_base and _looks_like_backend_base_url(app_base):
        logger.warning("Using APP_BASE_URL as Vapi backend base URL; prefer VAPI_PUBLIC_BACKEND_URL")
        return app_base

    raise ValueError(
        "VAPI_PUBLIC_BACKEND_URL requis pour provisionner Vapi sur le bon backend public"
    )


def _vapi_webhook_url() -> str:
    base = get_public_backend_base_url()
    return f"{base}/api/vapi/webhook"


def _merge_prompt_with_faq(base_prompt: str, faq_text: str) -> str:
    base = (base_prompt or "").strip()
    if FAQ_START_MARKER in base and FAQ_END_MARKER in base:
        before = base.split(FAQ_START_MARKER, 1)[0].rstrip()
        base = before
    faq_text = (faq_text or "").strip()
    if not faq_text:
        return base
    if not base:
        return faq_text
    return f"{base}\n\n{faq_text}"


async def create_vapi_assistant(
    tenant_id: int,
    tenant_name: str,
    assistant_id: str,
    sector: str,
    phone: str,
) -> Dict[str, Any]:
    """
    Crée un assistant Vapi persistant pour le tenant.
    Retourne l'objet assistant (avec 'id').
    """
    voice = ASSISTANT_VOICES.get(assistant_id, ASSISTANT_VOICES["sophie"])
    prompt_tpl = SECTOR_PROMPTS.get(sector, SECTOR_PROMPTS["medecin_generaliste"])
    sys_msg = prompt_tpl.format(name=tenant_name)
    try:
        from backend.tenant_config import faq_to_prompt_text, get_faq

        sys_msg = _merge_prompt_with_faq(sys_msg, faq_to_prompt_text(get_faq(tenant_id)))
    except Exception as e:
        logger.warning("create_vapi_assistant faq merge failed tenant_id=%s: %s", tenant_id, e)

    webhook_url = _vapi_webhook_url()
    webhook_secret = (os.environ.get("VAPI_WEBHOOK_SECRET") or "").strip() or None
    credential_id = (os.environ.get("VAPI_WEBHOOK_CREDENTIAL_ID") or "").strip() or None

    server_config: Dict[str, Any] = {"url": webhook_url}
    if credential_id:
        server_config["credentialId"] = credential_id
    elif webhook_secret:
        server_config["secret"] = webhook_secret

    payload = {
        "name": f"UWI-{tenant_name[:30]}-{assistant_id}",
        "voice": voice,
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": sys_msg}],
        },
        "firstMessage": f"Cabinet {tenant_name}, bonjour ! Je suis {assistant_id.capitalize()}, comment puis-je vous aider ?",
        "endCallFunctionEnabled": True,
        "recordingEnabled": True,
        "server": server_config,
        "metadata": {
            "tenant_id": str(tenant_id),
            "assistant_id": assistant_id,
        },
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{VAPI_API_URL}/assistant",
            json=payload,
            headers={
                "Authorization": f"Bearer {_vapi_api_key()}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        res.raise_for_status()
        data = res.json()
        logger.info(
            "VAPI_ASSISTANT_CREATED tenant_id=%s assistant_id=%s vapi_id=%s",
            tenant_id,
            assistant_id,
            data.get("id", "")[:24],
        )
        return data


async def patch_vapi_assistant_system_prompt(assistant_id: str, faq_text: str) -> None:
    """Recharge le prompt système de l'assistant en remplaçant uniquement le bloc FAQ."""
    assistant_id = (assistant_id or "").strip()
    if not assistant_id:
        return
    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        current_res = await client.get(
            f"{VAPI_API_URL}/assistant/{assistant_id}",
            headers=headers,
            timeout=15,
        )
        current_res.raise_for_status()
        data = current_res.json() or {}
        model = data.get("model") or {}
        messages = model.get("messages") or []
        if not isinstance(messages, list):
            messages = []

        system_index = next(
            (idx for idx, message in enumerate(messages) if isinstance(message, dict) and message.get("role") == "system"),
            None,
        )
        if system_index is None:
            messages = [{"role": "system", "content": faq_text}] + [msg for msg in messages if isinstance(msg, dict)]
        else:
            current_message = messages[system_index] if isinstance(messages[system_index], dict) else {"role": "system", "content": ""}
            merged_prompt = _merge_prompt_with_faq(str(current_message.get("content") or ""), faq_text)
            messages[system_index] = {**current_message, "role": "system", "content": merged_prompt}

        patch_res = await client.patch(
            f"{VAPI_API_URL}/assistant/{assistant_id}",
            json={"model": {**model, "messages": messages}},
            headers=headers,
            timeout=15,
        )
        patch_res.raise_for_status()
        logger.info("VAPI_ASSISTANT_FAQ_UPDATED assistant_id=%s", assistant_id[:24])


async def update_vapi_assistant_faq(tenant_id: int) -> None:
    """Injecte la FAQ du tenant dans le system prompt Vapi, sans casser la sauvegarde locale si Vapi échoue."""
    from backend.tenant_config import faq_to_prompt_text, get_faq, get_params

    params = get_params(tenant_id)
    vapi_assistant_id = str(params.get("vapi_assistant_id") or "").strip()
    if not vapi_assistant_id:
        return
    faq = get_faq(tenant_id)
    faq_text = faq_to_prompt_text(faq)
    await patch_vapi_assistant_system_prompt(vapi_assistant_id, faq_text)


async def assign_twilio_to_vapi(assistant_id: str, twilio_number: str) -> None:
    """
    Assigne un numéro Twilio (déjà dans Vapi) à un assistant.
    Lève si le numéro n'est pas trouvé dans Vapi.
    """
    number_clean = twilio_number.strip().replace(" ", "")
    if number_clean.startswith("00"):
        number_clean = "+" + number_clean[2:]

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{VAPI_API_URL}/phone-number",
            headers={"Authorization": f"Bearer {_vapi_api_key()}"},
            timeout=10,
        )
        res.raise_for_status()
        numbers = res.json()
        if not isinstance(numbers, list):
            numbers = numbers.get("phoneNumbers", numbers) if isinstance(numbers, dict) else []

        vapi_number = None
        for n in numbers:
            num = n.get("number") or n.get("phoneNumber") or ""
            if num.replace(" ", "") == number_clean:
                vapi_number = n
                break
        if not vapi_number:
            raise ValueError(f"Numéro {twilio_number} non trouvé dans Vapi")

        vapi_id = vapi_number.get("id") or vapi_number.get("phoneNumberId")
        if not vapi_id:
            raise ValueError("ID du numéro Vapi introuvable")

        res2 = await client.patch(
            f"{VAPI_API_URL}/phone-number/{vapi_id}",
            json={"assistantId": assistant_id},
            headers={
                "Authorization": f"Bearer {_vapi_api_key()}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        res2.raise_for_status()
        logger.info(
            "VAPI_PHONE_ASSIGNED assistant_id=%s number=%s",
            assistant_id[:24],
            number_clean[:12],
        )


async def delete_vapi_assistant(assistant_id: str) -> bool:
    """Supprime un assistant Vapi (rollback compensatoire)."""
    assistant_id = (assistant_id or "").strip()
    if not assistant_id:
        return False
    try:
        async with httpx.AsyncClient() as client:
            res = await client.delete(
                f"{VAPI_API_URL}/assistant/{assistant_id}",
                headers={"Authorization": f"Bearer {_vapi_api_key()}"},
                timeout=15,
            )
            if res.status_code in (200, 204):
                logger.info("VAPI_ASSISTANT_DELETED assistant_id=%s", assistant_id[:24])
                return True
            logger.warning(
                "delete_vapi_assistant unexpected status assistant_id=%s status=%s",
                assistant_id[:24],
                res.status_code,
            )
            return False
    except Exception as e:
        logger.error("delete_vapi_assistant failed: %s", e)
        return False
