# Schéma du function_tool Vapi (OpenAI direct)

À coller dans Vapi Composer pour que le LLM appelle le backend avec les bonnes actions.

## Règle dans le prompt

```
RÈGLE ABSOLUE — CRÉNEAUX :
Tu ne dois JAMAIS inventer ou proposer de créneaux toi-même.
Quand le patient a donné nom, motif et préférence (matin/après-midi),
tu DOIS appeler le tool function_tool avec action "get_slots".
Tu annonces uniquement les créneaux retournés par le tool (champ "slots").
```

## Définition du tool (JSON)

```json
{
  "type": "function",
  "function": {
    "name": "function_tool",
    "description": "Outil OBLIGATOIRE pour créneaux (get_slots), réservation (book), annulation (cancel), modification (modify), FAQ (faq). Ne JAMAIS proposer de créneaux sans appeler get_slots.",
    "parameters": {
      "type": "object",
      "properties": {
        "action": {
          "type": "string",
          "enum": ["get_slots", "book", "cancel", "modify", "faq"],
          "description": "Action à effectuer"
        },
        "patient_name": {
          "type": "string",
          "description": "Nom du patient"
        },
        "motif": {
          "type": "string",
          "description": "Motif de consultation"
        },
        "preference": {
          "type": "string",
          "enum": ["matin", "après-midi"],
          "description": "Préférence horaire"
        },
        "selected_slot": {
          "type": "string",
          "description": "Créneau choisi : 1, 2, 3 ou libellé (ex. jeudi 20 février à 14 heures)"
        },
        "user_message": {
          "type": "string",
          "description": "Message brut du patient (pour faq ou contexte)"
        }
      },
      "required": ["action"]
    }
  }
}
```

## Réponses du backend

- **get_slots** : `result` = JSON string `{"slots": ["jeudi 20 février à 14 heures", ...], "source": "google_calendar"}`. En cas d’erreur : `error` = message string.
- **book** : `result` = JSON string `{"status": "confirmed", "slot": "...", "patient": "...", "motif": "..."}` ou `error` = message.
- **cancel / modify / faq** : `result` = JSON string `{"message": "..."}` (texte à dire au client).

Le backend renvoie toujours HTTP 200 et `results: [{ toolCallId, result | error }]`.
