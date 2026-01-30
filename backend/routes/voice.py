# backend/routes/voice.py
"""
Route pour le canal Voix (Vapi) - DEBUG COMPLET + TIMERS
Avec mémoire client et stats pour rapports.
"""

from fastapi import APIRouter, Request
import logging
import json
import time

from backend.engine import ENGINE
from backend import prompts
from backend.client_memory import get_client_memory
from backend.reports import get_report_generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instances singleton
client_memory = get_client_memory()
report_generator = get_report_generator()


def _reconstruct_session_from_history(session, messages: list):
    """
    Reconstruit l'état de la session depuis l'historique des messages.
    Nécessaire si la session en mémoire a été perdue (redémarrage Railway).
    
    STRATÉGIE: Extraire TOUTES les données depuis l'historique
    """
    from backend.guards import clean_name_from_vocal
    
    # Patterns pour détecter l'état
    patterns = {
        "QUALIF_NAME": ["c'est à quel nom", "quel nom", "votre nom"],
        "QUALIF_PREF": ["matin ou l'après-midi", "matin ou après-midi", "préférez"],
        "QUALIF_CONTACT": ["numéro de téléphone", "téléphone pour vous rappeler", "redonner votre numéro"],
        "CONTACT_CONFIRM": ["votre numéro est bien", "j'ai noté le", "c'est bien ça", "est-ce correct"],
        "WAIT_CONFIRM": ["j'ai trois créneaux", "j'ai deux créneaux", "j'ai un créneau", "dites un, deux ou trois", "dites un ou deux"],
        "CONFIRMED": ["rendez-vous est confirmé", "c'est confirmé"],
    }
    
    print(f"🔄 Reconstructing session from {len(messages)} messages")
    
    # Parcourir TOUS les messages pour extraire les données
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "").lower()
            
            # Extraire le nom
            if any(p in content for p in patterns["QUALIF_NAME"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_name = messages[i + 1].get("content", "").strip()
                    if (len(potential_name) >= 2 and 
                        len(potential_name) <= 50 and
                        "matin" not in potential_name.lower() and
                        "après" not in potential_name.lower()):
                        cleaned_name = clean_name_from_vocal(potential_name)
                        if len(cleaned_name) >= 2:
                            session.qualif_data.name = cleaned_name
                            print(f"🔄 Name: '{potential_name}' → '{cleaned_name}'")
            
            # Extraire la préférence
            if any(p in content for p in patterns["QUALIF_PREF"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_pref = messages[i + 1].get("content", "").strip()
                    if potential_pref and len(potential_pref) <= 50:
                        session.qualif_data.pref = potential_pref
                        print(f"🔄 Pref: {potential_pref}")
            
            # Extraire le contact
            if any(p in content for p in patterns["QUALIF_CONTACT"]):
                if i + 1 < len(messages) and messages[i + 1].get("role") == "user":
                    potential_contact = messages[i + 1].get("content", "").strip()
                    if potential_contact:
                        session.qualif_data.contact = potential_contact
                        print(f"🔄 Contact: {potential_contact}")
    
    # Déterminer l'état ACTUEL basé sur le dernier message assistant
    last_assistant_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "").lower()
            break
    
    detected_state = None
    for state, state_patterns in patterns.items():
        if any(p in last_assistant_msg for p in state_patterns):
            detected_state = state
            break
    
    # Si état détecté
    if detected_state:
        session.state = detected_state
        print(f"🔄 State: {detected_state} (from: '{last_assistant_msg[:60]}...')")
        
        # Si WAIT_CONFIRM → on doit reproposer les créneaux (on ne peut pas les reconstruire)
        if detected_state == "WAIT_CONFIRM":
            print(f"⚠️ WAIT_CONFIRM detected - slots will be re-fetched on next handler call")
    else:
        print(f"⚠️ Could not detect state from: '{last_assistant_msg[:60]}...'")
    
    print(f"🔄 Reconstruction complete: state={session.state}, name={session.qualif_data.name}, pref={session.qualif_data.pref}")
    
    return session


def log_timer(label: str, start: float) -> float:
    """Log le temps écoulé et retourne le nouveau timestamp."""
    now = time.time()
    elapsed_ms = (now - start) * 1000
    print(f"⏱️ {label}: {elapsed_ms:.0f}ms")
    return now

router = APIRouter(prefix="/api/vapi", tags=["voice"])


@router.get("/test-calendar")
async def test_calendar_connection():
    """Test de connexion Google Calendar"""
    from backend import tools_booking
    from backend import config
    
    try:
        # Test 1: Config
        result = {
            "calendar_id": config.GOOGLE_CALENDAR_ID,
            "service_account_file": config.GOOGLE_SERVICE_ACCOUNT_FILE,
            "file_exists": False,
            "slots_available": False,
            "error": None
        }
        
        # Test 2: Fichier existe ?
        import os
        if config.GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
            result["file_exists"] = True
        
        # Test 3: Récupérer des créneaux
        slots = tools_booking.get_slots_for_display(limit=3)
        if slots and len(slots) > 0:
            result["slots_available"] = True
            result["slots"] = [{"idx": s.idx, "label": s.label} for s in slots]
        
        return result
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }




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
    
    Intégrations:
    - Mémoire client (reconnaissance clients récurrents)
    - Stats pour rapports quotidiens
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
        
        # 📱 Extraire le numéro de téléphone du client (Vapi le fournit)
        customer_phone = payload.get("call", {}).get("customer", {}).get("number")
        if not customer_phone:
            customer_phone = payload.get("customer", {}).get("number")
        
        print(f"📞 Call ID: {call_id} | Messages: {len(messages)} | Stream: {is_streaming}")
        if customer_phone:
            print(f"📱 Customer phone: {customer_phone}")
        
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
            
            # 🧠 Stocker le téléphone dans la session pour plus tard
            if customer_phone:
                session.customer_phone = customer_phone
            
            # 🔄 RECONSTRUCTION DE L'ÉTAT depuis l'historique des messages
            # NOTE: Avec SQLite, cette reconstruction ne devrait plus être nécessaire
            # On la garde en fallback si SQLite échoue
            if session.state == "START" and len(messages) > 1 and not session.qualif_data.name:
                print(f"⚠️ Session in START with history but no data → reconstruction needed")
                session = _reconstruct_session_from_history(session, messages)
                print(f"🔄 Session reconstructed: state={session.state}, name={session.qualif_data.name}")
            else:
                print(f"✅ Session loaded OK: state={session.state}, name={session.qualif_data.name}")
            
            t3 = log_timer("Session loaded", t2)
            
            # 🧠 Check si client récurrent (avant le premier message traité)
            if customer_phone and session.state == "START" and len(messages) <= 1:
                try:
                    existing_client = client_memory.get_by_phone(customer_phone)
                    if existing_client and existing_client.total_bookings > 0:
                        # Client récurrent détecté !
                        greeting = client_memory.get_personalized_greeting(existing_client, channel="vocal")
                        if greeting:
                            print(f"🧠 Returning client detected: {existing_client.name}")
                            # On pourrait utiliser ce greeting, mais pour l'instant on log juste
                            # Le flow normal continue
                except Exception as e:
                    print(f"⚠️ Client memory error: {e}")
            
            try:
                events = ENGINE.handle_message(call_id, user_message)
                t4 = log_timer("ENGINE processed", t3)
                
                response_text = events[0].text if events else "Je n'ai pas compris"
            except Exception as e:
                print(f"❌ ENGINE ERROR: {e}")
                import traceback
                traceback.print_exc()
                response_text = "Excusez-moi, j'ai un petit souci technique. Je vous transfère à un collègue."
            print(f"✅ Response: '{response_text[:50]}...' ({len(response_text)} chars)")
            
            # 📊 Enregistrer stats pour rapport (si conversation terminée)
            try:
                if session.state in ["CONFIRMED", "TRANSFERRED"]:
                    intent = "BOOKING" if session.state == "CONFIRMED" else "TRANSFER"
                    outcome = "confirmed" if session.state == "CONFIRMED" else "transferred"
                    duration_ms = int((time.time() - t_start) * 1000)
                    
                    report_generator.record_interaction(
                        call_id=call_id,
                        intent=intent,
                        outcome=outcome,
                        channel="vocal",
                        duration_ms=duration_ms,
                        motif=session.qualif_data.motif if hasattr(session, 'qualif_data') else None,
                        client_name=session.qualif_data.name if hasattr(session, 'qualif_data') else None,
                        client_phone=customer_phone
                    )
                    print(f"📊 Stats recorded: {intent} → {outcome}")
                    
                    # 🧠 Enregistrer le client si booking confirmé
                    if session.state == "CONFIRMED" and session.qualif_data.name:
                        try:
                            client = client_memory.get_or_create(
                                phone=customer_phone,
                                name=session.qualif_data.name,
                                email=session.qualif_data.contact if session.qualif_data.contact_type == "email" else None
                            )
                            # Enregistrer le booking dans l'historique client
                            slot_label = session.pending_slot_labels[0] if session.pending_slot_labels else "RDV"
                            client_memory.record_booking(
                                client_id=client.id,
                                slot_label=slot_label,
                                motif=session.qualif_data.motif or "consultation"
                            )
                            print(f"🧠 Client saved: {client.name} (id={client.id})")
                        except Exception as e:
                            print(f"⚠️ Client save error: {e}")
            except Exception as e:
                print(f"⚠️ Stats recording error: {e}")
        
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
