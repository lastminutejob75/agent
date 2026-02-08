# Batterie de tests STT "worst-case" — Agent vocal UWI

Phrases volontairement tordues ou mal reconnues pour vérifier que **l’agent se rattrape proprement** (clarification, exemple, fallback, transfert propre).  
Le but n’est pas que tout passe parfaitement, mais que le comportement soit cohérent et guidant.

---

## Règle d’or

> Si une phrase est mal comprise mais l’intention serait évidente pour un humain → **l’agent doit clarifier, pas punir.**

---

## 1️⃣ START — Ambiguïtés naturelles

| Test | User | Attendu | Réplique agent type |
|------|------|--------|----------------------|
| **1.1** | « oui… » | Clarification (PAS booking) | *« Pas de souci. C’est pour un rendez-vous, ou pour une question ? »* |
| **1.2** | « ben… je sais pas » | Guidage progressif (pas menu direct) | *« Je peux vous aider pour un rendez-vous, ou pour une question. Qu’est-ce que je peux faire pour vous ? »* |
| **1.3** | « euh… » | 1re fois → reformulation douce ; 2e → guidage clair ; 3e → INTENT_ROUTER | VOCAL_START_CLARIFY_1 → VOCAL_START_GUIDANCE → menu 1/2/3/4 |

---

## 2️⃣ INTENT_ROUTER — Chiffres mal reconnus

| Test | User | Attendu | Réplique agent type |
|------|------|--------|----------------------|
| **2.1** | « cat » (Deepgram pour quatre) | Option 4 = transfert | *« Je vous passe un conseiller. Un instant. »* |
| **2.2** | « hein » | Clarification ou demander de répéter ; ❌ ne pas interpréter comme « un » | MSG_INTENT_ROUTER_RETRY |
| **2.3** | « le premier » | Option 1 = rendez-vous | Demande du nom (QUALIF_NAME) |
| **2.4** | « annuler » | Option 2 (même sans « deux ») | Démarrage flow CANCEL_NAME |

---

## 3️⃣ QUALIF_NAME — Noms propres mal transcrits

| Test | User / STT | Attendu | Réplique agent type |
|------|------------|--------|----------------------|
| **3.1** | « Dupont » → STT « du pont » / « deux ponts » | FAIL_1 → redemande polie ; FAIL_2 → exemple « Martin Dupont » | VOCAL_NAME_FAIL_1 → VOCAL_NAME_FAIL_2 |
| **3.2** | « nom merci » (non merci mal reconnu) | Détecter NO / ABANDON ; ❌ ne pas prendre « merci » comme nom | Pas de stockage nom ; handle_no_contextual ou abandon |
| **3.3** | « c’est pour mon fils » | Clarification : à quel nom ? | Rejet nom invalide + redemande (À quel nom est le rendez-vous ?) |

---

## 4️⃣ QUALIF_PREF — Préférences floues

| Test | User | Attendu | Réplique agent type |
|------|------|--------|----------------------|
| **4.1** | « le plus tôt possible » | Idéal : interpréter comme prochain créneau OU proposer sans redemander matin/après-midi | Inférence préférence ou proposition directe |
| **4.2** | « vendredi » | Si possible extraire le jour ; sinon clarification simple (pas FAIL brutal) | Clarification ou passage aux slots |

---

## 5️⃣ WAIT_CONFIRM — Créneaux (zone sensible)

| Test | Contexte | User | Attendu | Réplique agent type |
|------|----------|------|--------|----------------------|
| **5.1** | Agent : « Le prochain créneau est mardi à 9h30. Ça vous convient ? » | « euh… » | Répéter le créneau courant ; ❌ pas menu ; ❌ pas retour au début | *« Le prochain créneau est mardi à 9h30. Ça vous convient ? »* |
| **5.2** | — | « le deuxième » | Reconnu même sans « deux » | Si slot 1 proposé → proposer slot 2 ; si slot 2 proposé → confirmer slot 2 |
| **5.3** | — | « oui de… » | Clarification ou reformulation « le premier ou le second ? » ; ❌ ne pas planter le parsing | VOCAL_SLOT_SEQUENTIAL_NEED_YES_NO |

---

## 6️⃣ CONTACT — Téléphone (enfer STT)

| Test | User | Attendu |
|------|------|--------|
| **6.1** | « zéro six douze trente-quatre cinquante-six soixante-dix-huit » | Normalisation OK → confirmation |
| **6.2** | « 06 douze 34 56 78 » | Normalisation OK (format mixte) |
| **6.3** | « six douze trente-quatre… » (sans zéro) | Tentative → FAIL_1 / FAIL_2 → FAIL_3 propose email |
| **6.4** | « plus trente-trois six douze… » | Normalisation +33 → 06… |

---

## 7️⃣ CANCEL / MODIFY — Intentions fortes en plein flux

| Test | Contexte | User | Attendu |
|------|----------|------|--------|
| **7.1** | En plein booking | « en fait je veux annuler » | CANCEL override immédiat ; pas « terminer le booking d’abord » |
| **7.2** | En WAIT_CONFIRM | « je préfère parler à quelqu’un » | TRANSFER immédiat |

---

## 8️⃣ FAQ en plein booking

| Test | Contexte | User | Attendu |
|------|----------|------|--------|
| **8.1** | En QUALIF_PREF | « c’est où votre cabinet déjà ? » | FAQ adresse → relance « autre chose ? » → si « rdv » → reprise booking sans perte |

---

## 9️⃣ Abandon naturel

| Test | User | Attendu |
|------|------|--------|
| **9.1** | « bon… laisse tomber » | ABANDON ; message propre ; fin sans menu |
| **9.2** | « au revoir » | CONFIRMED ; pas de rattrapage lourd |

---

## 10️⃣ Stress / agacement léger

| Test | User | Attendu |
|------|------|--------|
| **10.1** | « putain ça marche pas » | VOCAL_INSULT_RESPONSE (calme) ; recentrer ; pas transfert silencieux |

---

## Implémentation (référence code)

| Catégorie | Fichiers / éléments |
|-----------|----------------------|
| START 1.2 / 1.3 | `VOCAL_START_CLARIFY_1`, `VOCAL_START_GUIDANCE` ; `start_unclear_count` dans `_handle_faq` |
| INTENT_ROUTER 2.x | `ROUTER_AMBIGUOUS_STT` (hein, de), `ROUTER_*_PATTERNS`, `ROUTER_4_STT_TOLERANCE` ; `_handle_intent_router` |
| QUALIF_NAME 3.x | `is_valid_name_input` (rejet « c’est pour mon fils », « nom merci » via NO) ; `VOCAL_NAME_FAIL_1/2` |
| WAIT_CONFIRM 5.x | Séquentiel vocal : filler/euh → relire créneau ; « le deuxième » selon `slot_offer_index` ; « oui de » → clarification |
| CONTACT 6.x | `parse_vocal_phone`, `normalize_phone_fr` (9 chiffres 6/7 → 0, +33) ; ladder FAIL_1/2/3 |
| CANCEL/MODIFY 7.x | `detect_strong_intent` (CANCEL, TRANSFER) en plein booking |
| FAQ 8.x | `FAQ_STRONG_PATTERNS` + strong intent FAQ → `_handle_faq` |
| Abandon 9.x | `ABANDON_PATTERNS` (laisse tomber, au revoir) |
| Stress 10.x | `is_light_frustration` → `VOCAL_INSULT_RESPONSE` (sans transfert) |

---

*Document à utiliser en complément de la check-list 10 appels (`CHECKLIST_VALIDATION_10_APPELS.md`) pour les tests manuels voix.*
