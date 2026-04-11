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

# Mapping secteur → instructions système (legacy, utilisé par create_vapi_assistant)
SECTOR_PROMPTS: Dict[str, str] = {
    "medecin_generaliste": "Tu es l'assistante téléphonique du cabinet du Dr {name}. Tu réponds aux patients, gères les prises de rendez-vous et transfères les urgences.",
    "specialiste": "Tu es l'assistante téléphonique du cabinet spécialisé {name}. Tu gères les rendez-vous et renseignes les patients.",
    "kine": "Tu es l'assistante du cabinet de kinésithérapie {name}. Tu prends les rendez-vous et réponds aux questions courantes.",
    "dentiste": "Tu es l'assistante du cabinet dentaire {name}. Tu gères les rendez-vous et transfères les urgences dentaires.",
    "infirmier": "Tu es l'assistante du cabinet infirmier {name}. Tu gères les tournées et les rendez-vous de soins.",
}

VAPI_SYSTEM_PROMPT_V1 = """Tu es {assistant_name}, l'assistante vocale professionnelle du {cabinet_name}.
Tu gères uniquement l'accueil téléphonique et la prise de rendez-vous.

[STYLE OBLIGATOIRE]
Ton professionnel, courtois et rassurant
Chaleureux mais jamais familier
Phrases COURTES (maximum 2 phrases)
Une seule question à la fois
Jamais de listes longues
Jamais de références ou de sources
Jamais de conseils médicaux

[RÈGLE ABSOLUE — FAQ / INFORMATIONS]
Pour toute question d'information (horaires, tarifs, adresse, vacances, fermetures, moyens de paiement, etc.) :
→ Répondre DIRECTEMENT depuis la section FAQ ci-dessous.
→ Ne JAMAIS appeler function_tool pour une question d'information.
→ Ne JAMAIS inventer de réponse. Utiliser UNIQUEMENT les informations de la FAQ.
→ Si l'information n'est pas dans la FAQ : "Je n'ai pas cette information. Souhaitez-vous que je vous mette en relation avec le cabinet ?"

[CONTRAT TOOL — OBLIGATOIRE]
Tu as un tool function_tool.

Actions possibles (args.action)
get_slots : obtenir des créneaux disponibles
book : réserver un créneau
cancel : annuler un rendez-vous
modify : modifier un rendez-vous
transfer : transférer vers un humain / la ligne du cabinet selon décision backend

Règle de remplissage des arguments
Quand tu appelles le tool, envoie toujours un maximum d'infos déjà connues.
Si une info manque, pose une question pour la collecter, puis appelle le tool.

Modèles d'appels (exemples)
get_slots ⇒ envoyer toujours: patient_name, motif, preference
Si le patient précise une heure souhaitée, ajouter aussi preferred_time au format HH:MM et preferred_time_type selon ce mapping :
- "à partir de 16h30", "pas avant 16h30" ⇒ preferred_time_type = "min"
- "avant 16h30", "au plus tard 16h30" ⇒ preferred_time_type = "max"
- "vers 16h30", "plutôt vers 16h30" ⇒ preferred_time_type = "around"
- "à 16h30", "16h30 pile" ⇒ preferred_time_type = "exact"
book ⇒ envoyer toujours: patient_name, motif, selected_slot
cancel/modify ⇒ envoyer toujours: patient_name + user_message (le message brut du patient)
transfer ⇒ envoyer toujours: transfer_reason, et inclure patient_name si connu, et user_message si utile

[RÈGLE RGPD — NUMÉRO]
Si {{{{customer.number}}}} est disponible et non vide : ne JAMAIS redemander le numéro.
Pour confirmer le numéro déjà connu, dis simplement :
"J'ai bien votre numéro de téléphone. Est-ce bien cela ?"
Ne JAMAIS prononcer de placeholder, de variable technique, ni de texte comme "number minus two" ou "customer.number".
Si le client dit que ce n'est pas le bon numéro : demander le bon numéro, puis le confirmer simplement.
Si le numéro n'est pas disponible, demande-le poliment.

[RÈGLE ABSOLUE — CRÉNEAUX]
Tu ne dois JAMAIS inventer de créneaux.

Après avoir reçu :
- le nom (patient_name)
- le motif (motif)
- la préférence (preference: matin / après-midi)
- si le patient donne aussi une heure précise, preferred_time au format HH:MM
- et preferred_time_type si le sens est clair (min / max / around / exact)
→ Tu DOIS appeler function_tool avec action: "get_slots" en incluant patient_name, motif, preference, preferred_time et preferred_time_type si disponibles.

Si le patient demande une heure qui ne correspond pas exactement à un des créneaux proposés, ne corrige pas toi-même le calendrier.
Soit tu rappelles les créneaux proposés et demandes d'en choisir un, soit tu rappelles get_slots avec preferred_time si le patient exprime une nouvelle préférence horaire précise.
Tu n'as jamais le droit d'inventer qu'un jour "n'existe pas".

Tu annonces uniquement les créneaux retournés.
Le résultat du tool `function_tool` est toujours un JSON stringifié.
Tu dois prendre tes décisions UNIQUEMENT à partir de `status`, `slots` et `reason`.
Tu n'as pas le droit de déduire une action à partir d'une chaîne libre.

Format obligatoire : jour complet + date complète + heure complète.
Exemple : "Jeudi 20 février à 14 heures"

Contrat de lecture OBLIGATOIRE pour `get_slots` :
- si `status = "ok"` : annonce uniquement les éléments de `slots[].label`, sans rien inventer ;
- si `status = "no_slots"` : dire exactement :
"Je n'ai pas de créneau disponible pour cette demande. Souhaitez-vous que je recherche une autre heure ou un autre jour ?"
- si `status = "agenda_unavailable"` : dire exactement :
"Je n'arrive pas à consulter l'agenda pour le moment. Souhaitez-vous qu'on vous rappelle ?"

Règles absolues :
- ne JAMAIS traiter `no_slots` comme une panne agenda ;
- ne JAMAIS traiter `agenda_unavailable` comme un simple manque de disponibilité ;
- ne JAMAIS prendre une décision à partir du texte brut du tool.

[RÈGLE ABSOLUE — ACCEPTATION DU RAPPEL]
Si tu viens de dire :
"Je n'arrive pas à consulter l'agenda pour le moment. Souhaitez-vous qu'on vous rappelle ?"
et que le client répond oui (exemples : "oui", "oui d'accord", "volontiers", "bien sûr", "pourquoi pas") :
Dire exactement :
"Très bien. Le cabinet vous rappellera dès que possible. Merci pour votre appel. Bonne journée."
Puis appeler immédiatement `endCall`.

Si le client répond non :
Dire exactement :
"Très bien. N'hésitez pas à rappeler. Bonne journée."
Puis appeler immédiatement `endCall`.

Dans ce sous-flow de rappel :
Ne pose aucune autre question.
Ne propose pas de transfert.
Ne reformule pas.
Ne continue pas la conversation après la phrase de clôture.

[RÈGLE ABSOLUE — AUCUN CRÉNEAU DISPONIBLE]
Si le dernier résultat tool `get_slots` a `status = "no_slots"` et que tu viens de dire qu'aucun créneau n'est disponible pour la demande courante :
tu dois proposer une autre heure ou un autre jour.
Si le patient demande "pourquoi" après cette réponse, dire exactement :
"Je n'ai pas de disponibilité correspondant à cette demande dans l'agenda actuel. Souhaitez-vous une autre heure ou un autre jour ?"
Ne transfère pas. Ne parle pas de panne agenda. Ne reformule pas en échec technique.

[RÈGLE ABSOLUE — RÉSERVATION]
Quand le client choisit un créneau :
→ Appeler function_tool avec action: "book" en incluant patient_name, motif, selected_slot.

Contrat de lecture OBLIGATOIRE pour `book` :
- si `status = "confirmed"` :
- ne lis PAS le contenu du tool,
- ne prononce aucun texte libre,
- appelle immédiatement le tool natif `endCall`.
Le message vocal de clôture est déjà géré par `endCallMessage`.
Après un `book` confirmé, tu n'as PAS le droit de dire "Un instant.", "Au revoir.", ni aucune autre phrase.

Après avoir appelé `endCall`, ignore totalement le contenu de retour du tool `endCall`,
y compris s'il contient des textes comme :
"Tool Result Still Pending But Proceed Further If Possible."
ou
"Success."
Après l'appel de `endCall`, tu n'as plus le droit de produire un nouveau message.

- si `status = "failed"` :
Dire exactement :
"Je n'ai pas pu valider la réservation. Souhaitez-vous réessayer ?"

[FLOW DE PRISE DE RENDEZ-VOUS]
Demander le nom.
Demander le motif.
Si refus (exemples: "je préfère ne pas dire", "c'est personnel") → noter "consultation générale".
Demander matin ou après-midi.
Appeler get_slots.
Annoncer les créneaux (sans en inventer).
Si choix → appeler book.
Si "confirmed" → passer à la clôture.

[RÈGLE ABSOLUE — FIN DE CONVERSATION]
⚠️ IMPORTANT — AUCUNE HÉSITATION POSSIBLE

Après confirmation `book.status = "confirmed"` :
N'énonce AUCUN texte toi-même.
N'essaie PAS de lire le résultat tool.
Appelle UNIQUEMENT `endCall`.
Le message "Votre rendez-vous est confirmé. Merci pour votre appel. Bonne journée." est déjà géré par `endCallMessage`.
Si `endCall` est déjà appelé, tu ne dois plus rien dire du tout, même si Vapi t'envoie ensuite un résultat tool.

NE PAS :
relancer la conversation
poser une nouvelle question
proposer autre chose
reformuler
continuer à parler
prononcer un placeholder technique de numéro

[AUTRES CAS — FAQ (horaires, adresse, tarifs, vacances, fermetures…)]
Réponds DIRECTEMENT à partir du bloc "FAQ DU CABINET" ci-dessous.
- Ne JAMAIS appeler function_tool pour la FAQ.
- Ne JAMAIS inventer d'information qui n'est pas dans la FAQ.
- Si l'information n'est pas dans la FAQ, dire exactement :
"Je n'ai pas cette information. Souhaitez-vous qu'on vous rappelle ?"
Après une réponse FAQ, demande : "Souhaitez-vous autre chose ?"

Annulation / modification :
Demander le nom, puis appeler function_tool (action: "cancel" ou "modify") avec patient_name et user_message.
Si plusieurs rendez-vous possibles, demander la date et l'heure.

[GESTION SILENCE / CONFUSION]
Si silence prolongé :
"Êtes-vous toujours là ?"

Si réponse confuse :
Poser une question simple et courte.

[TRANSFERT D'APPEL — AUTORISÉ VIA BACKEND]
Si le client demande un humain, si situation urgente, ou si blocage technique :
Dire exactement : "Je vous transfère maintenant."
Appeler function_tool avec :
action: "transfer"
transfer_reason (ex: "demande_humain", "urgence", "probleme_agenda", "probleme_reservation", "autre")
inclure patient_name si connu, et user_message si utile
Ne pas inventer de numéro de transfert : le backend décide selon ses règles.
Pour un simple échec de consultation agenda, utiliser le message de rappel exact ci-dessus et ne pas transférer automatiquement.
Pour un cas "aucun créneau disponible", ne jamais transférer automatiquement."""


def _build_base_prompt(tenant_id: int = 1) -> str:
    """Construit le prompt de base V2 avec les infos tenant."""
    from backend import config as _cfg
    try:
        from backend.tenant_config import get_params
        params = get_params(tenant_id)
    except Exception:
        params = {}
    cabinet_name = (
        str(params.get("business_name") or "").strip()
        or str(params.get("name") or "").strip()
        or _cfg.BUSINESS_NAME
    )
    assistant_name = (
        str(params.get("assistant_name") or "").strip()
        or "Chloé"
    )
    return VAPI_SYSTEM_PROMPT_V1.format(
        cabinet_name=cabinet_name,
        assistant_name=assistant_name,
    )


def _vapi_api_key() -> str:
    key = (os.environ.get("VAPI_API_KEY") or "").strip()
    if not key:
        raise ValueError("VAPI_API_KEY non configuré")
    return key


def _vapi_function_tool_id() -> str:
    """Retourne l'ID du tool persisté Vapi (model.toolIds strategy)."""
    tid = (os.environ.get("VAPI_FUNCTION_TOOL_ID") or "").strip()
    if not tid:
        raise ValueError("VAPI_FUNCTION_TOOL_ID non configuré — requis pour attacher le tool aux assistants")
    return tid


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


def _vapi_tool_url() -> str:
    base = get_public_backend_base_url()
    return f"{base}/api/vapi/tool"


def _build_function_tool_messages() -> list[Dict[str, Any]]:
    """Messages Vapi du function tool: courts et neutres pour éviter une répétition lourde."""
    return [
        {"type": "request-start", "content": "Un instant.", "blocking": True},
        {"type": "request-response-delayed", "content": "Encore une seconde."},
        {
            "type": "request-failed",
            "content": "Je n'arrive pas à consulter l'agenda pour le moment. Souhaitez-vous qu'on vous rappelle ?",
            "endCallAfterSpokenEnabled": False,
        },
    ]


def _build_function_tool_definition() -> Dict[str, Any]:
    """
    Définition du tool function_tool pour Vapi (server-side).
    FAQ n'est PAS dans le tool : le LLM répond aux questions FAQ directement
    depuis son system prompt (qui contient la FAQ du cabinet, y compris
    les fermetures exceptionnelles, vacances, etc.).
    Le tool ne gère que les actions qui nécessitent le backend.
    """
    return {
        "type": "function",
        "function": {
            "name": "function_tool",
            "description": (
                "Outil backend pour les ACTIONS uniquement. "
                "Utilise cet outil SEULEMENT quand le patient veut : "
                "consulter les créneaux disponibles (get_slots), "
                    "valider le numéro de téléphone avant réservation (validate_contact), "
                "réserver un rendez-vous (book), "
                "annuler un rendez-vous (cancel), "
                "modifier un rendez-vous (modify), "
                "ou être transféré vers un humain (transfer). "
                "Le backend renvoie toujours un JSON stringifié avec un champ status. "
                "Tu dois interpréter le résultat uniquement via status, slots et reason. "
                "Pour les questions d'information (horaires, tarifs, adresse, vacances, etc.), "
                "réponds DIRECTEMENT depuis tes instructions sans appeler cet outil."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get_slots", "validate_contact", "book", "cancel", "modify", "transfer"],
                        "description": "L'action à exécuter.",
                    },
                    "user_message": {
                        "type": "string",
                        "description": "Le message de l'utilisateur, retranscrit tel quel.",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Nom du patient (si connu).",
                    },
                    "motif": {
                        "type": "string",
                        "description": "Motif du rendez-vous (si mentionné).",
                    },
                    "preference": {
                        "type": "string",
                        "description": "Préférence horaire du patient (matin, après-midi, jour spécifique).",
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Heure souhaitée précise au format HH:MM (ex: 16:00) si le patient demande un horaire comme 'vers 16h'.",
                    },
                    "preferred_time_type": {
                        "type": "string",
                        "enum": ["exact", "min", "max", "around"],
                        "description": "Sens de la contrainte horaire: exact (= a 16h30), min (= a partir de 16h30), max (= avant / au plus tard 16h30), around (= vers 16h30).",
                    },
                    "selected_slot": {
                        "type": "string",
                        "description": "Créneau sélectionné pour la réservation (format ISO ou texte).",
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Numéro de téléphone fourni ou corrigé par le patient. Ne jamais le relire intégralement à voix haute.",
                    },
                    "confirmation_last4": {
                        "type": "string",
                        "description": "4 derniers chiffres confirmés par le patient pour valider un numéro déjà connu.",
                    },
                },
                "required": ["action"],
            },
        },
        "server": {
            "url": _vapi_tool_url(),
        },
        "messages": _build_function_tool_messages(),
        "async": False,
    }


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

        sys_msg = _merge_prompt_with_faq(sys_msg, faq_to_prompt_text(get_faq(tenant_id), tenant_id=tenant_id))
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

    model_config: Dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": sys_msg}],
    }
    try:
        function_tool_id = _vapi_function_tool_id()
        model_config["toolIds"] = [function_tool_id]
    except ValueError:
        logger.warning("create_vapi_assistant: VAPI_FUNCTION_TOOL_ID non configuré, assistant créé sans tool")

    payload = {
        "name": f"UWI-{tenant_name[:30]}-{assistant_id}",
        "voice": voice,
        "model": model_config,
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


async def patch_vapi_assistant_system_prompt(
    assistant_id: str,
    faq_text: str,
    base_prompt: str | None = None,
) -> None:
    """
    Recharge le prompt système de l'assistant.
    Si base_prompt est fourni, remplace intégralement la partie avant la FAQ.
    Sinon, conserve la partie existante (comportement legacy).
    """
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

        if base_prompt:
            full_prompt = _merge_prompt_with_faq(base_prompt, faq_text)
        else:
            system_index = next(
                (idx for idx, message in enumerate(messages) if isinstance(message, dict) and message.get("role") == "system"),
                None,
            )
            existing_base = ""
            if system_index is not None:
                current_message = messages[system_index] if isinstance(messages[system_index], dict) else {"role": "system", "content": ""}
                existing_base = str(current_message.get("content") or "")
            full_prompt = _merge_prompt_with_faq(existing_base, faq_text)

        system_index = next(
            (idx for idx, message in enumerate(messages) if isinstance(message, dict) and message.get("role") == "system"),
            None,
        )
        if system_index is None:
            messages = [{"role": "system", "content": full_prompt}] + [msg for msg in messages if isinstance(msg, dict)]
        else:
            current_message = messages[system_index] if isinstance(messages[system_index], dict) else {"role": "system", "content": ""}
            messages[system_index] = {**current_message, "role": "system", "content": full_prompt}

        patch_payload: Dict[str, Any] = {"model": {**model, "messages": messages}}
        if base_prompt:
            patch_payload["silenceTimeoutSeconds"] = 45
        patch_res = await client.patch(
            f"{VAPI_API_URL}/assistant/{assistant_id}",
            json=patch_payload,
            headers=headers,
            timeout=15,
        )
        patch_res.raise_for_status()
        logger.info("VAPI_ASSISTANT_PROMPT_UPDATED assistant_id=%s base=%s len=%d silence=%s",
                     assistant_id[:24], "v2" if base_prompt else "legacy", len(full_prompt),
                     "45s" if base_prompt else "unchanged")


async def update_vapi_assistant_faq(tenant_id: int) -> None:
    """Injecte le prompt V2 complet (base + FAQ) dans l'assistant Vapi."""
    from backend.tenant_config import faq_to_prompt_text, get_faq, get_params

    params = get_params(tenant_id)
    vapi_assistant_id = str(params.get("vapi_assistant_id") or "").strip()
    if not vapi_assistant_id:
        return
    faq = get_faq(tenant_id)
    faq_text = faq_to_prompt_text(faq, tenant_id=tenant_id)
    base = _build_base_prompt(tenant_id)
    await patch_vapi_assistant_system_prompt(vapi_assistant_id, faq_text, base_prompt=base)


async def patch_vapi_assistant_add_tool(vapi_assistant_id: str) -> Dict[str, Any]:
    """
    PATCH un assistant Vapi existant :
    1. Garantir que VAPI_FUNCTION_TOOL_ID est dans model.toolIds
    2. Supprimer tout function tool inline de model.tools (éviter les conflits)
    Retourne la réponse Vapi ou lève en cas d'erreur.
    """
    vapi_assistant_id = (vapi_assistant_id or "").strip()
    if not vapi_assistant_id:
        raise ValueError("vapi_assistant_id requis")

    function_tool_id = _vapi_function_tool_id()

    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        current_res = await client.get(
            f"{VAPI_API_URL}/assistant/{vapi_assistant_id}",
            headers=headers,
            timeout=15,
        )
        current_res.raise_for_status()
        data = current_res.json() or {}

        model = data.get("model") or {}
        existing_tool_ids = set(model.get("toolIds") or [])
        existing_inline_tools = model.get("tools") or []

        needs_patch = False
        patch_model = {**model}

        if function_tool_id not in existing_tool_ids:
            existing_tool_ids.add(function_tool_id)
            needs_patch = True
        patch_model["toolIds"] = list(existing_tool_ids)

        kept_inline = [t for t in existing_inline_tools if t.get("type") != "function"]
        removed_inline_count = len(existing_inline_tools) - len(kept_inline)
        if removed_inline_count > 0:
            needs_patch = True
        patch_model["tools"] = kept_inline

        if not needs_patch:
            logger.info(
                "VAPI_ASSISTANT_ALREADY_CLEAN assistant_id=%s toolIds=%s",
                vapi_assistant_id[:24],
                list(existing_tool_ids),
            )
            return data

        patch_res = await client.patch(
            f"{VAPI_API_URL}/assistant/{vapi_assistant_id}",
            json={"model": patch_model},
            headers=headers,
            timeout=15,
        )
        patch_res.raise_for_status()
        result = patch_res.json()
        new_model = result.get("model") or {}
        logger.info(
            "VAPI_ASSISTANT_TOOL_SYNCED assistant_id=%s toolIds=%s inline_removed=%d inline_remaining=%d",
            vapi_assistant_id[:24],
            new_model.get("toolIds") or [],
            removed_inline_count,
            len(new_model.get("tools") or []),
        )
        return result


async def patch_vapi_function_tool(tool_id: str | None = None) -> Dict[str, Any]:
    """Synchronise le tool persistant Vapi avec des messages de maintien courts."""
    target_tool_id = (tool_id or "").strip() or _vapi_function_tool_id()
    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        current_res = await client.get(
            f"{VAPI_API_URL}/tool/{target_tool_id}",
            headers=headers,
            timeout=15,
        )
        current_res.raise_for_status()
        current = current_res.json() or {}
        patch_payload = {
            "messages": _build_function_tool_messages(),
            "async": False,
        }
        patch_res = await client.patch(
            f"{VAPI_API_URL}/tool/{target_tool_id}",
            json=patch_payload,
            headers=headers,
            timeout=15,
        )
        patch_res.raise_for_status()
        result = patch_res.json() or {}
        logger.info(
            "VAPI_FUNCTION_TOOL_SYNCED tool_id=%s request_start=%s delayed=%s",
            target_tool_id[:24],
            ((result.get("messages") or [{}])[0].get("content") if isinstance(result.get("messages"), list) and result.get("messages") else ""),
            ((result.get("messages") or [{}, {}])[1].get("content") if isinstance(result.get("messages"), list) and len(result.get("messages") or []) > 1 else ""),
        )
        return {"before": current, "after": result}


async def patch_vapi_function_tool_server(tool_id: str, server_url: str) -> Dict[str, Any]:
    """Met à jour uniquement l'URL server d'un tool Vapi existant."""
    target_tool_id = (tool_id or "").strip()
    target_server_url = (server_url or "").strip()
    if not target_tool_id:
        raise ValueError("tool_id requis")
    if not target_server_url:
        raise ValueError("server_url requis")

    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        current_res = await client.get(
            f"{VAPI_API_URL}/tool/{target_tool_id}",
            headers=headers,
            timeout=15,
        )
        current_res.raise_for_status()
        current = current_res.json() or {}
        patch_payload = {
            "server": {"url": target_server_url},
        }
        patch_res = await client.patch(
            f"{VAPI_API_URL}/tool/{target_tool_id}",
            json=patch_payload,
            headers=headers,
            timeout=15,
        )
        patch_res.raise_for_status()
        result = patch_res.json() or {}
        logger.info(
            "VAPI_FUNCTION_TOOL_SERVER_UPDATED tool_id=%s server_url=%s",
            target_tool_id[:24],
            target_server_url[:80],
        )
        return {"before": current, "after": result}


async def create_vapi_function_tool_clone(source_tool_id: str) -> Dict[str, Any]:
    """Crée un nouveau tool Vapi dédié à partir d'un tool existant."""
    source_tool_id = (source_tool_id or "").strip()
    if not source_tool_id:
        raise ValueError("source_tool_id requis")
    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        current_res = await client.get(
            f"{VAPI_API_URL}/tool/{source_tool_id}",
            headers=headers,
            timeout=15,
        )
        current_res.raise_for_status()
        source = current_res.json() or {}
        payload = {
            "type": source.get("type") or "function",
            "function": source.get("function") or _build_function_tool_definition().get("function"),
            "server": source.get("server") or {"url": _vapi_tool_url()},
            "messages": source.get("messages") or _build_function_tool_messages(),
            "async": bool(source.get("async", False)),
        }
        create_res = await client.post(
            f"{VAPI_API_URL}/tool",
            json=payload,
            headers=headers,
            timeout=15,
        )
        create_res.raise_for_status()
        created = create_res.json() or {}
        logger.info(
            "VAPI_FUNCTION_TOOL_CLONED source_tool_id=%s new_tool_id=%s",
            source_tool_id[:24],
            str(created.get("id") or "")[:24],
        )
        return {"source": source, "created": created}


async def patch_vapi_assistant_set_function_tool(vapi_assistant_id: str, function_tool_id: str) -> Dict[str, Any]:
    """Remplace le function tool persistant d'un assistant par un tool dédié."""
    vapi_assistant_id = (vapi_assistant_id or "").strip()
    function_tool_id = (function_tool_id or "").strip()
    if not vapi_assistant_id:
        raise ValueError("vapi_assistant_id requis")
    if not function_tool_id:
        raise ValueError("function_tool_id requis")

    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        current_res = await client.get(
            f"{VAPI_API_URL}/assistant/{vapi_assistant_id}",
            headers=headers,
            timeout=15,
        )
        current_res.raise_for_status()
        data = current_res.json() or {}
        model = data.get("model") or {}
        inline_tools = model.get("tools") or []
        kept_inline = [t for t in inline_tools if t.get("type") != "function"]
        patch_model = {**model, "toolIds": [function_tool_id], "tools": kept_inline}

        patch_res = await client.patch(
            f"{VAPI_API_URL}/assistant/{vapi_assistant_id}",
            json={"model": patch_model},
            headers=headers,
            timeout=15,
        )
        patch_res.raise_for_status()
        result = patch_res.json() or {}
        logger.info(
            "VAPI_ASSISTANT_SET_FUNCTION_TOOL assistant_id=%s function_tool_id=%s",
            vapi_assistant_id[:24],
            function_tool_id[:24],
        )
        return {"before": data, "after": result}


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
