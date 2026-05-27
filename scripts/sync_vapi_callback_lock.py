from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.vapi_utils import VAPI_API_URL, patch_vapi_function_tool

CALLBACK_RULE_MARKER = "[RÈGLE ABSOLUE — ACCEPTATION DU RAPPEL]"
CALLBACK_RULE_ANCHOR = (
    'Dans ce cas précis, ne parle pas de transfert et ne reformule pas en "mise en relation".'
)
CALLBACK_RULE_SENTENCE = (
    "Je n'arrive pas à consulter l'agenda pour le moment. Souhaitez-vous qu'on vous rappelle ?"
)
CALLBACK_RULE_BLOCK = """

[RÈGLE ABSOLUE — ACCEPTATION DU RAPPEL]
Si tu viens de dire :
"Je n'arrive pas à consulter l'agenda pour le moment. Souhaitez-vous qu'on vous rappelle ?"
et que le client répond oui (exemples : "oui", "oui d'accord", "volontiers", "bien sûr", "pourquoi pas") :
Dire exactement :
"Très bien. Le cabinet vous rappellera dès que possible. Merci pour votre appel. Bonne journée."
Puis appeler immédiatement `endCall`.

Si le client répond non :
Dire exactement :
"Très bien. Vous pouvez rappeler plus tard. Bonne journée."
Puis appeler immédiatement `endCall`.

Dans ce sous-flow de rappel :
Ne pose aucune autre question.
Ne propose pas de transfert.
Ne reformule pas.
Ne continue pas la conversation après la phrase de clôture.
""".rstrip()


def _vapi_api_key() -> str:
    key = (os.environ.get("VAPI_API_KEY") or "").strip()
    if not key:
        raise ValueError("VAPI_API_KEY non configuré")
    return key


async def patch_assistant_callback_lock(assistant_id: str) -> None:
    headers = {
        "Authorization": f"Bearer {_vapi_api_key()}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(f"{VAPI_API_URL}/assistant/{assistant_id}", headers=headers)
        res.raise_for_status()
        data = res.json() or {}
        model = data.get("model") or {}
        messages = model.get("messages") or []
        if not isinstance(messages, list):
            raise ValueError("model.messages invalide")

        system_index = next(
            (
                idx
                for idx, message in enumerate(messages)
                if isinstance(message, dict) and message.get("role") == "system"
            ),
            None,
        )
        if system_index is None:
            raise ValueError("Message system introuvable")

        current_message = messages[system_index]
        content = str(current_message.get("content") or "")
        if CALLBACK_RULE_MARKER in content:
            print("ASSISTANT_CALLBACK_LOCK_ALREADY_PRESENT")
            return
        if CALLBACK_RULE_ANCHOR in content:
            updated_content = content.replace(
                CALLBACK_RULE_ANCHOR,
                f"{CALLBACK_RULE_ANCHOR}{CALLBACK_RULE_BLOCK}",
                1,
            )
        elif CALLBACK_RULE_SENTENCE in content:
            updated_content = content.replace(
                CALLBACK_RULE_SENTENCE,
                f"{CALLBACK_RULE_SENTENCE}{CALLBACK_RULE_BLOCK}",
                1,
            )
        else:
            raise ValueError("Fallback agenda introuvable dans le prompt assistant")
        messages[system_index] = {
            **current_message,
            "role": "system",
            "content": updated_content,
        }

        patch_payload: dict[str, Any] = {"model": {**model, "messages": messages}}
        patch_res = await client.patch(
            f"{VAPI_API_URL}/assistant/{assistant_id}",
            json=patch_payload,
            headers=headers,
        )
        patch_res.raise_for_status()
        print("ASSISTANT_CALLBACK_LOCK_PATCHED")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Verrouille le sous-flow Vapi de rappel apres echec agenda.")
    parser.add_argument("--assistant-id", required=True, help="ID de l'assistant Vapi a patcher.")
    parser.add_argument("--tool-id", help="ID du function tool Vapi a resynchroniser.")
    args = parser.parse_args()

    if args.tool_id:
        await patch_vapi_function_tool(args.tool_id)
        print("FUNCTION_TOOL_SYNCED")

    await patch_assistant_callback_lock(args.assistant_id)


if __name__ == "__main__":
    asyncio.run(main())
