# Guide de Migration Multi-Canal

## État actuel ✅

La migration de base est terminée :

```
backend/
├── channels/
│   ├── __init__.py      ✅ Créé
│   ├── base.py          ✅ BaseChannel (classe abstraite)
│   └── voice.py         ✅ VoiceChannel (Vapi)
├── models/
│   ├── __init__.py      ✅ Créé
│   └── message.py       ✅ ChannelMessage, ChannelResponse
├── routes/
│   ├── __init__.py      ✅ Créé
│   └── voice.py         ✅ Route /api/vapi/webhook
├── main.py              ✅ Modifié (utilise routes.voice)
├── vapi.py              ✅ Backup (ancien code)
└── engine.py            ✅ Non modifié (logique métier)
```

## Branches Git

- `main` - Production stable
- `backup-avant-refactoring` - Backup avant migration
- `feature/multi-canal` - Nouvelle architecture (actuelle)

---

## Prochaine étape : Ajouter WhatsApp

### Phase 1 : Créer WhatsAppChannel

Créer `backend/channels/whatsapp.py` :

```python
# backend/channels/whatsapp.py
"""
Canal WhatsApp via Twilio ou Meta API.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import logging

from backend.channels.base import BaseChannel
from backend.models.message import ChannelMessage, ChannelResponse, ChannelType
from backend.engine import ENGINE

logger = logging.getLogger(__name__)


class WhatsAppChannel(BaseChannel):
    """
    Implémentation du canal WhatsApp.
    
    Supporte :
    - Twilio WhatsApp API
    - Meta WhatsApp Business API (futur)
    """
    
    channel_type = ChannelType.WHATSAPP
    
    def parse_incoming(self, raw_payload: Dict[str, Any]) -> Optional[ChannelMessage]:
        """
        Parse un webhook Twilio WhatsApp.
        
        Format Twilio :
        - Body: texte du message
        - From: whatsapp:+33612345678
        - To: whatsapp:+33939240575
        - MessageSid: identifiant unique
        """
        # Extraire les données
        body = raw_payload.get("Body", "")
        from_number = raw_payload.get("From", "").replace("whatsapp:", "")
        to_number = raw_payload.get("To", "").replace("whatsapp:", "")
        message_sid = raw_payload.get("MessageSid", "")
        
        if not body or not from_number:
            logger.warning("WhatsAppChannel: Missing body or from_number")
            return None
        
        # Utiliser le numéro comme session_id
        session_id = f"wa_{from_number}"
        
        # Marquer la session
        session = ENGINE.session_store.get_or_create(session_id)
        session.channel = "whatsapp"
        
        return ChannelMessage(
            channel=self.channel_type,
            session_id=session_id,
            text=body,
            sender_id=from_number,
            raw_payload=raw_payload,
            metadata={
                "to": to_number,
                "message_sid": message_sid
            }
        )
    
    def format_response(self, response: ChannelResponse) -> Dict[str, Any]:
        """
        Formate pour TwiML (Twilio Messaging).
        
        Format TwiML :
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>Texte de réponse</Message>
        </Response>
        """
        # Pour Twilio, on retourne du TwiML
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response.text}</Message>
</Response>'''
        
        return {"twiml": twiml, "text": response.text}


# Instance singleton
whatsapp_channel = WhatsAppChannel()
```

### Phase 2 : Créer la route WhatsApp

Créer `backend/routes/whatsapp.py` :

```python
# backend/routes/whatsapp.py
"""
Routes API pour le canal WhatsApp (Twilio).
"""

from __future__ import annotations
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
import logging

from backend.channels.whatsapp import whatsapp_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(""),
    From: str = Form(""),
    To: str = Form(""),
    MessageSid: str = Form("")
):
    """
    Webhook pour Twilio WhatsApp.
    Reçoit les messages et répond en TwiML.
    """
    try:
        payload = {
            "Body": Body,
            "From": From,
            "To": To,
            "MessageSid": MessageSid
        }
        
        logger.info(f"WhatsApp webhook: from={From}, body={Body[:50]}...")
        
        response = whatsapp_channel.process_message(payload)
        
        # Retourner TwiML
        return Response(
            content=response.get("twiml", ""),
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        return Response(
            content='''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Désolé, une erreur s'est produite.</Message>
</Response>''',
            media_type="application/xml"
        )


@router.get("/health")
async def whatsapp_health():
    """Health check pour WhatsApp."""
    return {
        "status": "ok",
        "service": "whatsapp",
        "channel": "twilio"
    }
```

### Phase 3 : Modifier main.py

Ajouter dans `backend/main.py` :

```python
from backend.routes import voice, whatsapp

app.include_router(voice.router)
app.include_router(whatsapp.router)  # Ajouter cette ligne
```

### Phase 4 : Configurer Twilio WhatsApp

1. Dans Twilio Console → Messaging → Try it out → Send a WhatsApp message
2. Suivre les instructions pour activer WhatsApp Sandbox
3. Configurer le webhook : `https://agent-production-c246.up.railway.app/api/whatsapp/webhook`

---

## Commandes utiles

### Tester localement
```bash
cd /Users/actera/agent-accueil-pme
python -m uvicorn backend.main:app --reload --port 8000
```

### Tester les endpoints
```bash
# Health Voice
curl http://localhost:8000/api/vapi/health

# Health WhatsApp
curl http://localhost:8000/api/whatsapp/health

# Test webhook Voice
curl -X POST http://localhost:8000/api/vapi/webhook \
  -H "Content-Type: application/json" \
  -d '{"message":{"type":"user-message","content":"bonjour"},"call":{"id":"test"}}'
```

### Déployer
```bash
git add -A
git commit -m "feat: ajouter canal WhatsApp"
git push agent feature/multi-canal:main
```

---

## Fichiers à NE PAS modifier

- `backend/engine.py` - Logique métier, fonctionne bien
- `backend/prompts.py` - Messages utilisateur
- `backend/guards.py` - Validations
- `backend/tools_*.py` - Outils booking/FAQ
- `backend/db.py` - Base de données

---

## Architecture finale visée

```
                    ┌─────────────┐
                    │   main.py   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │routes/voice │ │routes/whatsapp│ │routes/web  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │VoiceChannel │ │WhatsAppChannel│ │WebChannel  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │   ENGINE    │
                    │ (engine.py) │
                    └─────────────┘
```

Tous les canaux utilisent le même ENGINE pour la logique métier.
