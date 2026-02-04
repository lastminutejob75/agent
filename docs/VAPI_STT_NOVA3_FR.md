# Vapi STT : nova-3 en français (recommandé)

## Contexte

- **nova-2-phonecall** n’existe pas en français → ne pas l’utiliser pour des appels FR.
- **nova-3** est le bon choix pour le français aujourd’hui.
- Les soucis (transcripts type "Believe you would have...", "oui" non reconnu) venaient du **combo langue + pipeline** (STT en anglais), pas du moteur.

## Configuration recommandée (Vapi Dashboard)

**STT / Speech-to-Text :**

| Paramètre   | Valeur     |
|------------|------------|
| Provider   | Deepgram   |
| Model      | **nova-3** |
| Language   | **fr** (pas auto en prod) |
| Smart format | ON  |
| Punctuation  | ON  |
| Profanity    | OFF |
| Diarization  | OFF |

⚠️ Éviter `auto` pour la langue en prod tant que tout n’est pas stable.

## Côté code (déjà en place)

- **Stratégie 2** (chat/completions) : firewall text-only, whitelist tokens critiques, UNCLEAR → menu → transfert.
- `normalize_transcript`, `is_filler_only`, critical tokens ("oui", "non", "ok", 1/2/3).
- Override en START : "oui" / "ok" seul → toujours YES.

Aucun changement de code nécessaire pour passer à nova-3 + français.

## Vérification terrain (2 appels)

1. **Phrase normale** : *« Bonjour, je veux un rendez-vous »*  
   → transcript FR, TEXT, flow booking normal.

2. **Confirmation** : *« oui »*  
   → critical token → TEXT, confirmation OK.

Si ces deux tests passent → bon pour prod.
