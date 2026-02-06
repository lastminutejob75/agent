# Ton vocal — agent moins sec, plus doux

L’agent vocal peut sembler froid ou sec à l’écoute. On peut agir sur **deux leviers** : le **texte** (prompts) et le **TTS** (voix / intonation).

---

## 1. Wording (déjà appliqué dans `backend/prompts.py`)

- **Formules d’adoucissement** : "s’il vous plaît", "vous pouvez", "prenez votre temps", "avec plaisir", "pas de souci".
- **Éviter l’impératif sec** : "Dites un, deux ou trois" → "Vous pouvez dire un, deux ou trois, s’il vous plaît."
- **Préférence pour l’invitation** : "Je vous propose trois créneaux" au lieu de "J’ai trois créneaux."
- **Transfert** : "Je vous mets en relation avec un conseiller qui pourra vous aider" (réassurance).
- **Silence / incompréhension** : "Pourriez-vous répéter, s’il vous plaît ?" plutôt que "Pouvez-vous répéter ?".

Toutes les constantes vocales (`VOCAL_*`, `MSG_*_VOCAL`) sont alignées sur ce ton dans `prompts.py`.

---

## 2. TTS / intonation (côté Vapi ou moteur de voix)

L’**intonation** perçue comme « froide » vient surtout du **moteur de synthèse** et de ses réglages.

### Réglages à vérifier dans Vapi (dashboard)

- **Vitesse (speech rate)** : une vitesse légèrement plus lente donne un ton moins sec (ex. 0.95–1.0 au lieu de 1.1).
- **Voix** : choisir une voix décrite comme « chaleureuse » ou « conversationnelle » (selon le fournisseur : ElevenLabs, PlayHT, etc.).
- **Stabilité (si disponible)** : un peu moins de stabilité peut donner plus de variation prosodique et un ton moins monotone.

### Option SSML (si supporté par Vapi)

Si le champ `content` renvoyé au TTS accepte le SSML, on peut adoucir le rythme côté backend, par exemple :

```xml
<speak>
  <prosody rate="slow" pitch="medium">
    Bonjour, vous êtes bien chez Cabinet Dupont. Je vous écoute avec plaisir.
  </prosody>
</speak>
```

À implémenter uniquement si la doc Vapi confirme que le TTS utilisé interprète le SSML dans la réponse du webhook.

---

## 3. Résumé

| Levier        | Où agir              | Effet                          |
|---------------|----------------------|---------------------------------|
| Formulations  | `backend/prompts.py` | Ton plus poli, invitant, doux  |
| Vitesse / voix| Dashboard Vapi       | Intonation moins sèche         |
| SSML          | Réponse webhook      | Rythme plus posé (si supporté) |

En priorité : **wording** (déjà en place) + **réglages voix/vitesse dans Vapi**.
