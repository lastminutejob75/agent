# Check-list de validation manuelle — 10 appels de test

Calibrée pour vérifier P0/P1 en conditions réelles (STT imparfait + interruptions).  
À utiliser lors des tests manuels voix (Vapi ou équivalent).

---

## Appel 1 — START : "oui" ambigu (P0.1)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| **User** | « oui » |
| **Attendu** | L’agent **ne part pas** en prise de RDV. |
| **Agent** | *« Pas de souci. C’est pour un rendez-vous, ou pour une question ? »* |

---

## Appel 2 — START : booking explicite

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| **User** | « je veux un rendez-vous » |
| **Attendu** | Bascule booking directe → demande du **nom** (ou préférence si extraction). |
| **Agent** | *« Pour le rendez-vous, à quel nom s’il vous plaît ? »* (ou équivalent) |

---

## Appel 3 — START : question FAQ

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| **User** | « c’est quoi vos horaires ? » |
| **Attendu** | Réponse FAQ + relance courte. |
| **Agent** | « (réponse horaires) … Souhaitez-vous autre chose ? » |

---

## Appel 4 — POST_FAQ : "oui" ambigu → disambiguation unifiée (P1.3)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| Contexte | Après une réponse FAQ (ex. horaires). |
| **User** | « oui » |
| **Attendu** | **Une seule** disambiguation naturelle, **pas** « Dites : … ». |
| **Agent** | *« Vous voulez prendre rendez-vous, ou poser une question ? »* |

---

## Appel 5 — INTENT_ROUTER : robustesse STT (P1.5)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| Contexte | Forcer le menu (2–3 incompréhensions), puis : |
| **User** | « cat » (erreur STT fréquente pour « quatre ») |
| **Attendu** | Option 4 → transfert conseiller. |
| **Agent** | *« Je vous passe un conseiller. Un instant. »* (ou équivalent transfert) |

---

## Appel 6 — Booking : slots séquentiels (P0.2)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| Contexte | Arriver au moment des créneaux (nom, motif, préférence, contact selon flow). |
| **Attendu** | L’agent **ne lit jamais** 3 créneaux d’un coup. |
| **Agent** | *« Le prochain créneau est {slot1}. Ça vous convient ? »* |
| **User** | « non » |
| **Agent** | *« Le prochain créneau est {slot2}. Ça vous convient ? »* |
| **User** | « oui » |
| **Attendu** | Booking continue (confirmation créneau puis contact si besoin). |

---

## Appel 7 — Booking : "répéter" au moment du créneau (P0.2)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| Contexte | Au moment « Ça vous convient ? » (créneau proposé). |
| **User** | « vous pouvez répéter ? » |
| **Attendu** | Relit **le créneau courant** (pas retour au menu 1/2/3/4). |
| **Agent** | *« Le prochain créneau est {slotX}. Ça vous convient ? »* |

---

## Appel 8 — Booking : sortie "piège" — strong intents (P1.6)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| Contexte | En plein booking (ex. après la question du nom). |
| **User** | « en fait je veux juste l’adresse » |
| **Attendu** | Bascule **FAQ (adresse)** sans boucle, sans perdre le fil. |
| **Agent** | Répond avec l’adresse + « autre chose ? » (ou relance équivalente). |
| Puis **User** | « rdv » (ou « rendez-vous ») |
| **Attendu** | Reprise du flow booking (ex. demande du nom). |

---

## Appel 9 — MODIFY : ordre sécurisé (P0.4)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| **User** | « je veux déplacer mon rendez-vous » |
| Donner un nom valide, arriver à la proposition de **nouveaux** slots. |
| **Attendu** | L’agent **ne supprime pas** l’ancien RDV tant que le **nouveau n’est pas confirmé**. |
| **Cas test** | Raccrocher **avant** confirmation du nouveau slot → **l’ancien RDV doit rester** (vérifier en base ou calendrier). |

---

## Appel 10 — Téléphone : ladder FAIL + fallback email (P1.8)

| Étape | Action / Réponse attendue |
|-------|----------------------------|
| Contexte | À « Quel numéro ? » (ou équivalent). |
| **User** | Répondre volontairement mal : « euh… zéro… six… euh… » (ou équivalent flou). |
| **Attendu** | |
| **FAIL_1** | *« Je n’ai pas bien compris le numéro. Pouvez-vous le répéter lentement ? »* |
| **FAIL_2** | *« Dites les chiffres deux par deux. Par exemple : zéro six, douze… »* |
| **FAIL_3** | Bascule email : *« Pas de souci. On peut aussi prendre votre email. Quelle est votre adresse email ? »* |

---

## Mini check "qualité audio / wording"

Pendant ces 10 appels, vérifier aussi :

- Pas de **« Qu’est-ce qui vous ferait plaisir ? »**
- Pas de **« Je vais simplifier »**
- Pas de **« Vérifier ou humain ? »**
- Pas de **« oui un / oui deux / oui trois »** (en vocal, slots séquentiels → « Ça vous convient ? »)
- Phrases courtes (≈ 12–14 mots max)
- Pas de double **« Parfait… Parfait… »**

---

## Indicateurs à noter (à la main)

Sur chaque appel, noter :

| Indicateur | Objectif / Note |
|------------|------------------|
| **Temps total** | Objectif booking happy path **< 75 s** |
| **Nb de repeats** | Objectif **≤ 1** par étape |
| **1ère incompréhension** | L’agent guide-t-il correctement ? (oui/non) |
| **Transfert** | Arrive-t-il « proprement » (pas après 3 minutes) ? (oui/non) |

---

## Référence code

- Comportements P0/P1 : `docs/voice_changes_2026-02.md`
- Messages : `backend/prompts.py`
- Logique : `backend/engine.py` (START, CLARIFY, WAIT_CONFIRM séquentiel, MODIFY, INTENT_ROUTER, strong intents, PHONE_FAIL).
