# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - DEBUG COMPLET + TIMERS
"""

from fastapi import APIRouter, Request
import logging
import json
import time

from backend.engine import ENGINE
from backend import prompts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_timer(label: str, start: float) -> float:
    """Log le temps écoulé et retourne le nouveau timestamp."""
    now = time.time()
    elapsed_ms = (now - start) * 1000
    print(f"⏱️ {label}: {elapsed_ms:.0f}ms")
    return now

router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - DEBUG COMPLET + TIMERS
    """
    t_start = time.time()
    
    try:
        payload = await request.json()
        t1 = log_timer("Payload parsed", t_start)
        
        message = payload.get("message", {})
        message_type = message.get("type", "NO_TYPE")
        call_id = payload.get("call", {}).get("id", "unknown")
        
        print(f"🔔 WEBHOOK | type={message_type} | call={call_id}")
        
        # assistant-request
        if message_type == "assistant-request":
            print("✅ Returning {} for assistant-request")
            return {}
        
        # ACCEPTE TOUS LES MESSAGES AVEC DU TEXTE
        user_text = message.get("content") or message.get("transcript") or ""
        t2 = log_timer("Message extracted", t1)
        
        if user_text and user_text.strip():
            print(f"💬 User: '{user_text}'")
            
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            t3 = log_timer("Session loaded", t2)
            
            events = ENGINE.handle_message(call_id, user_text)
            t4 = log_timer("ENGINE processed", t3)
            
            response_text = events[0].text if events else "Je n'ai pas compris"
            
            # ⏱️ TIMING TOTAL
            total_ms = (time.time() - t_start) * 1000
            print(f"✅ TOTAL: {total_ms:.0f}ms | Response: '{response_text[:50]}...'")
            
            return {"content": response_text}
        
        print(f"⚠️ No user text found")
        return {}
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"content": "Désolé, une erreur est survenue."}


@router.post("/tool")
async def vapi_tool(request: Request):
    """
    Endpoint pour Vapi Tools/Functions.
    Claude appelle ce tool pour obtenir les réponses.
    """
    try:
        payload = await request.json()
        
        print(f"🔧🔧🔧 TOOL APPELÉ 🔧🔧🔧")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # Extraire le message utilisateur
        user_message = payload.get("parameters", {}).get("user_message", "")
        call_id = payload.get("call", {}).get("id", "unknown")
        
        print(f"📝 User message: '{user_message}'")
        print(f"📞 Call ID: {call_id}")
        
        if not user_message:
            return {"result": "Je n'ai pas compris. Pouvez-vous répéter ?"}
        
        # Session vocale
        session = ENGINE.session_store.get_or_create(call_id)
        session.channel = "vocal"
        
        # Traiter
        events = ENGINE.handle_message(call_id, user_message)
        response_text = events[0].text if events else "Je n'ai pas compris"
        
        print(f"✅ Tool response: '{response_text}'")
        
        return {"result": response_text}
        
    except Exception as e:
        print(f"❌ Tool error: {e}")
        import traceback
        traceback.print_exc()
        return {"result": "Désolé, une erreur est survenue."}


@router.post("/chat/completions")
async def vapi_custom_llm(request: Request):
    """
    Vapi Custom LLM endpoint
    Vapi envoie les messages ici au lieu d'utiliser Claude/GPT
    Supporte le streaming (SSE) quand stream=true
    """
    from fastapi.responses import StreamingResponse
    
    # ⏱️ TIMING START
    t_start = time.time()
    
    try:
        payload = await request.json()
        t1 = log_timer("Payload parsed", t_start)
        
        print(f"🤖 CUSTOM LLM | Payload size: {len(str(payload))} chars")
        
        # Vapi envoie un tableau de messages
        messages = payload.get("messages", [])
        call_id = payload.get("call", {}).get("id") or payload.get("call_id", "unknown")
        is_streaming = payload.get("stream", False)
        
        print(f"📞 Call ID: {call_id} | Messages: {len(messages)} | Stream: {is_streaming}")
        
        # Récupère le dernier message utilisateur
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content")
                break
        
        t2 = log_timer("Message extracted", t1)
        print(f"💬 User: '{user_message}'")
        
        if not user_message:
            # Premier message ou pas de message user
            response_text = prompts.MSG_WELCOME
            print(f"✅ Welcome message")
        else:
            # Traiter via ENGINE
            session = ENGINE.session_store.get_or_create(call_id)
            session.channel = "vocal"
            t3 = log_timer("Session loaded", t2)
            
            events = ENGINE.handle_message(call_id, user_message)
            t4 = log_timer("ENGINE processed", t3)
            
            response_text = events[0].text if events else "Je n'ai pas compris"
            print(f"✅ Response: '{response_text[:50]}...' ({len(response_text)} chars)")
        
        # ⏱️ TIMING TOTAL
        total_ms = (time.time() - t_start) * 1000
        print(f"✅ TOTAL LATENCY: {total_ms:.0f}ms")
        
        # Si streaming demandé, retourner SSE
        if is_streaming:
            async def generate_stream():
                import asyncio
                
                # Premier chunk : rôle assistant
                chunk_role = {
                    "id": f"chatcmpl-{call_id}",
                    "object": "chat.completion.chunk",
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk_role)}\n\n"
                
                # Envoyer le contenu mot par mot
                words = response_text.split()
                for i, word in enumerate(words):
                    # Ajouter espace sauf pour le premier mot
                    content = f" {word}" if i > 0 else word
                    chunk = {
                        "id": f"chatcmpl-{call_id}",
                        "object": "chat.completion.chunk",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": content},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                # Chunk final
                chunk_final = {
                    "id": f"chatcmpl-{call_id}",
                    "object": "chat.completion.chunk",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(chunk_final)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        
        # Format OpenAI-compatible (non-streaming)
        return {
            "id": f"chatcmpl-{call_id}",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }]
        }
        
    except Exception as e:
        print(f"❌ Custom LLM error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Désolé, une erreur est survenue."
                }
            }]
        }


@router.get("/health")
async def vapi_health():
    return {"status": "ok", "service": "voice"}


@router.get("/test")
async def vapi_test():
    try:
        events = ENGINE.handle_message("test", "bonjour")
        if events:
            return {"status": "ok", "response": events[0].text}
        return {"status": "error"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
