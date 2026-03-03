"""
Utilitaires Vapi : création d'assistants, assignation numéros Twilio.
Utilisé par POST /api/admin/tenants/create.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

VAPI_API_URL = "https://api.vapi.ai"

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


def _vapi_webhook_url() -> str:
    base = (
        os.environ.get("VAPI_PUBLIC_BACKEND_URL")
        or os.environ.get("APP_BASE_URL")
        or ""
    ).rstrip("/")
    if not base:
        raise ValueError("VAPI_PUBLIC_BACKEND_URL ou APP_BASE_URL requis")
    return f"{base}/api/vapi/webhook"


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
