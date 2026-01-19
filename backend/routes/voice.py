# backend/routes/voice.py
"""
Route complète pour le canal Voix (Vapi).

Ce fichier remplace l'ancien backend/vapi.py en utilisant
la nouvelle architecture multi-canal.

Copy-paste ready : Tu peux copier ce fichier directement dans ton projet.
"""

from fastapi import APIRouter, Request, HTTPException
import logging

from backend.channels.voice import VoiceChannel, create_vapi_fallback_response
from backend.models.message import AgentResponse

# Import de l'engine existant (ne change pas)
from backend.engine import ENGINE

logger = logging.getLogger(__name__)

# Créer le router FastAPI
router = APIRouter(prefix="/api/vapi", tags=["voice"])

# Créer l'instance du VoiceChannel
voice_channel = VoiceChannel()


@router.post("/webhook")
async def vapi_webhook(request: Request):
    """
    Webhook Vapi - Point d'entrée pour tous les appels vocaux.
    
    Gère différents types de messages Vapi :
    - assistant-request : Vapi demande la config assistant
    - user-message : Message de l'utilisateur (on traite)
    - status-update, end-of-call-report, etc. : On ignore
    
    Returns:
        dict : Réponse formatée pour Vapi
    """
    try:
        # 1. Parser le message entrant via VoiceChannel
        channel_message = await voice_channel.parse_incoming(request)
        
        # Si None, c'est un message à ignorer ou un assistant-request
        if channel_message is None:
            # Lire le payload pour déterminer le type
            try:
                payload = await request.json()
                message_type = payload.get("message", {}).get("type", "")
                
                # assistant-request : Retourner {} (utilise assistant configuré dans Vapi)
                if message_type == "assistant-request":
                    logger.info("Assistant request - returning empty config")
                    return {}
                
                # Autres types : Ignorer silencieusement
                logger.debug(f"Ignoring Vapi message type: {message_type}")
                return {"status": "ok"}
                
            except Exception as e:
                logger.error(f"Error parsing Vapi payload: {e}")
                return {"status": "ok"}
        
        # 2. On a un user-message valide → Passer au moteur
        logger.info(
            f"Processing user message: "
            f"conv_id={channel_message.conversation_id}, "
            f"text='{channel_message.user_text}'"
        )
        
        # Appeler l'engine (ton code existant, aucun changement)
        events = ENGINE.handle_message(
            channel_message.conversation_id,
            channel_message.user_text
        )
        
        # 3. Transformer le premier event en réponse
        if events and len(events) > 0:
            event = events[0]
            
            # Créer une AgentResponse à partir de l'Event
            response = AgentResponse(
                text=event.text,
                conversation_id=channel_message.conversation_id,
                state=event.conv_state or "START",
                event_type=event.type,
                transfer_reason=event.transfer_reason,
                silent=event.silent
            )
            
            # 4. Formater pour Vapi et retourner
            vapi_response = await voice_channel.format_response(response)
            
            logger.info(
                f"Responding to Vapi: "
                f"text='{response.text[:50]}...', "
                f"state={response.state}"
            )
            
            return vapi_response
        
        # Fallback si pas d'events (ne devrait pas arriver)
        logger.warning("No events returned from engine")
        return create_vapi_fallback_response()
        
    except Exception as e:
        # Erreur inattendue : Logger et retourner message d'erreur
        logger.error(f"Vapi webhook error: {e}", exc_info=True)
        return create_vapi_fallback_response(
            error_message="Désolé, une erreur est survenue. Veuillez réessayer."
        )


@router.get("/health")
async def vapi_health():
    """
    Health check pour vérifier que le canal Vapi est opérationnel.
    
    Utile pour :
    - Monitoring (uptime)
    - Tests automatisés
    - Debug
    
    Returns:
        dict : Status et infos
    """
    return {
        "status": "ok",
        "service": "voice",
        "channel": "vapi",
        "message": "Voice channel is ready"
    }


@router.get("/test")
async def vapi_test():
    """
    Endpoint de test pour vérifier le fonctionnement complet.
    
    Simule un message utilisateur et vérifie que l'engine répond.
    Utile pour valider le déploiement.
    
    Returns:
        dict : Résultat du test
    """
    try:
        # Créer un message de test
        test_conv_id = "test_vapi_voice"
        test_message = "bonjour"
        
        # Appeler l'engine
        events = ENGINE.handle_message(test_conv_id, test_message)
        
        # Vérifier qu'on a une réponse
        if events and len(events) > 0:
            return {
                "status": "ok",
                "test_input": test_message,
                "test_response": events[0].text,
                "message": "Voice channel is working correctly"
            }
        else:
            return {
                "status": "error",
                "error": "No response from engine",
                "test_input": test_message
            }
            
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# =====================================
# Routes additionnelles (optionnel)
# =====================================

@router.post("/call-started")
async def vapi_call_started(request: Request):
    """
    Callback Vapi quand un appel démarre.
    Optionnel : Permet de tracker les appels.
    """
    try:
        payload = await request.json()
        call_id = payload.get("call", {}).get("id", "")
        
        logger.info(f"Call started: call_id={call_id}")
        
        # Tu peux logger dans ta DB si tu veux
        # db.log_call_started(call_id, timestamp=datetime.utcnow())
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error in call-started callback: {e}")
        return {"status": "error"}


@router.post("/call-ended")
async def vapi_call_ended(request: Request):
    """
    Callback Vapi quand un appel se termine.
    Optionnel : Permet de collecter des métriques.
    """
    try:
        payload = await request.json()
        call_id = payload.get("call", {}).get("id", "")
        duration = payload.get("call", {}).get("duration", 0)
        
        logger.info(f"Call ended: call_id={call_id}, duration={duration}s")
        
        # Analytics : tracker durée, coût, etc.
        # analytics.track_call(call_id, duration, cost=duration * 0.08)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error in call-ended callback: {e}")
        return {"status": "error"}


# =====================================
# Utilitaires (pour debug)
# =====================================

@router.get("/stats")
async def vapi_stats():
    """
    Statistiques du canal vocal (optionnel).
    Utile pour monitoring.
    """
    try:
        # Récupérer stats depuis ton engine/db
        total_conversations = len(ENGINE.session_store.sessions)
        active_conversations = sum(
            1 for session in ENGINE.session_store.sessions.values()
            if session.channel == "vocal" and not session.is_expired()
        )
        
        return {
            "channel": "vocal",
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "status": "ok"
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
