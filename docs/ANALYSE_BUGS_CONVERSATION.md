# Analyse des bugs conversation après modifs TTS premium

Après les changements de wording (conseiller vs humain, nouvelles formulations), plusieurs incohérences ont été identifiées et corrigées.

---

## 1. MSG_WELCOME inexistant (critique)

**Problème** : `voice.py` et `bland.py` utilisaient `prompts.MSG_WELCOME` quand le premier message utilisateur est vide. Cette constante n’existe pas dans `prompts.py` → `AttributeError` au premier appel sans message.

**Correction** : Remplacer par `prompts.get_vocal_greeting(config.BUSINESS_NAME)` (salutation vocale avec nom du cabinet). Import de `config` ajouté dans `bland.py`.

**Fichiers** : `backend/routes/voice.py`, `backend/routes/bland.py`.

---

## 2. « Conseiller » non reconnu → transfert (CANCEL / MODIFY)

**Problème** : Les prompts disent maintenant « Dites : vérifier, ou : **conseiller** ». L’engine ne déclenchait le transfert que sur « humain », « quelqu’un », « opérateur », « transfert ». Si l’utilisateur disait « conseiller », il n’était pas transféré.

**Correction** : Ajout de `"conseiller"` dans les listes de détection de demande de transfert :
- `engine.py` : états `CANCEL_NO_RDV` et `MODIFY_NO_RDV` (deux endroits).
- `engine.py` : bloc INTENT_ROUTER (menu 1/2/3/4) pour cohérence.

**Fichier** : `backend/engine.py`.

---

## 3. Reconstruction de session vocale (voice.py)

**Problème** : Les patterns de reconstruction s’appuient sur le dernier message assistant pour retrouver l’état. Après changement des formulations, certains états n’étaient plus reconnus.

**Corrections** :
- **WAIT_CONFIRM** : le message de créneaux est passé à « Très bien. **Voici** trois créneaux » et « **Dites simplement** : un, deux, ou trois ». Ajout des patterns `"voici trois créneaux"` et `"dites simplement"`.
- **CONTACT_CONFIRM** : la confirmation téléphone est passée à « **Je confirme** : {phone_spaced}. C'est bien ça ? ». Ajout du pattern `"je confirme"`.

**Fichier** : `backend/routes/voice.py` (fonction `_reconstruct_session_from_history`).

---

## 4. Déjà cohérent (vérifié)

- **POST_FAQ** : le pattern `"souhaitez-vous autre chose"` était déjà présent → reconstruction OK après passage de « Puis-je vous aider pour autre chose ? » à « Souhaitez-vous autre chose ? ».
- **QUALIF_NAME** : « quel nom » reste dans les messages (« À quel nom, s'il vous plaît ? », « À quel nom est le rendez-vous ») → détection d’état OK.
- **INTENT_ROUTER** : le menu propose « dites quatre pour un conseiller » ; l’utilisateur dit en pratique « quatre ». Ajout de « conseiller » pour les cas où il répète le mot.

---

## 5. Autres points à surveiller (non modifiés)

- **VOCAL_EMAIL_CONFIRM** : absent de `prompts.py` ; l’engine utilise `getattr(prompts, "VOCAL_EMAIL_CONFIRM", None)` et un fallback → pas de crash.
- **MSG_CANCEL_NOT_FOUND_VERIFIER_HUMAN_WEB** / **MSG_MODIFY_NOT_FOUND_VERIFIER_HUMAN_WEB** : le texte web contient encore « vérifier ou humain ». Pour aligner avec le vocal (« conseiller »), il faudrait des constantes web dédiées si on veut le même vocabulaire partout.
- **Guards** : la liste de mots courts (ex. « humain ») dans `guards.py` peut rester pour éviter les transferts sur un seul mot ; « conseiller » est plus long et moins ambigu.

---

## Résumé des correctifs appliqués

| Fichier        | Correction |
|----------------|------------|
| voice.py       | Welcome → `get_vocal_greeting(config.BUSINESS_NAME)` ; patterns WAIT_CONFIRM + CONTACT_CONFIRM. |
| bland.py       | Welcome → `get_vocal_greeting(config.BUSINESS_NAME)` ; import `config`. |
| engine.py      | Ajout de `"conseiller"` pour transfert (CANCEL_NO_RDV, MODIFY_NO_RDV, INTENT_ROUTER). |

Tests recommandés après déploiement : premier message vide (welcome), annulation/modification avec « conseiller » pour transfert, reconstruction après redémarrage en WAIT_CONFIRM ou après confirmation téléphone.
