# Règles de l’agent — vue complète pour analyse

Document de référence : **toutes les règles** de l’agent (PRD, SYSTEM_PROMPT, audit vocal, STT, config).  
À utiliser pour reprendre / auditer / simplifier.

---

## 1. Principes généraux (PRD / SYSTEM_PROMPT)

| # | Règle | Source | Résumé |
|---|--------|--------|--------|
| 0 | **Modification = respect du PRD** | PRD §0 | Toute modification doit respecter strictement le PRD. Hors scope = refus ou version future. |
| F | **Fiabilité > intelligence** | PRD §1, SYSTEM | L’agent est **contraint, pas créatif**. Ne jamais inventer. Transférer dès que le cadre est dépassé. |
| UX | **Jamais de silence** | PRD §6, SYSTEM §3 | Si pas de certitude : soit la phrase exacte "Je ne suis pas certain… Puis-je vous mettre en relation avec [entreprise] ?", soit UNE question de qualification. Jamais rester silencieux. |

---

## 2. Règles absolues produit (PRD §5, SYSTEM §2)

| # | Règle | Détail |
|---|--------|--------|
| A1 | **FAQ < 80 % → ne pas répondre** | Match FAQ strict (rapidfuzz ≥ 80 %). Sinon appliquer la règle UX (transfert / question autorisée). |
| A2 | **Hésitation → transfert immédiat** | En cas de doute, transfert humain immédiat. |
| A3 | **Une seule question à la fois** | Pas deux questions dans le même message. |
| A4 | **Max 2 tours hors FAQ → transfert** | Après 2 tours sans match FAQ, transfert (ou INTENT_ROUTER selon spec V3). |
| A5 | **Réponses courtes et traçables** | Réponse courte (<150 car. en V1), factuelle, traçable (Source : FAQ_ID). |
| A6 | **Aucune action sans confirmation** | RDV / annulation / modification uniquement après confirmation explicite (ex. "oui 1/2/3"). |
| A7 | **Français uniquement** | Répondre uniquement en français. |
| A8 | **Pas de formulation hors liste** | N’inventer aucune formulation hors celles autorisées (prompts.py). |

---

## 3. Qualification (PRD §7, SYSTEM §5)

| # | Règle | Détail |
|---|--------|--------|
| Q1 | **Ordre fixe** | Nom → Motif → Créneau préféré (matin/après-midi + jour) → Contact (email ou téléphone). |
| Q2 | **Format motif** | 1 phrase max. Pas de justification / détails multiples. |
| Q3 | **Format créneau** | [Matin \| Après-midi] + jour de semaine. |
| Q4 | **Format contact** | Email valide OU numéro de téléphone valide. |
| Q5 | **Non-conformité** | Une clarification, puis transfert si toujours non conforme. |

---

## 4. Flow RDV (PRD, SYSTEM §6)

| # | Règle | Détail |
|---|--------|--------|
| R1 | **3 créneaux proposés** | Toujours proposer exactement 3 créneaux (config : MAX_SLOTS_PROPOSED = 3). |
| R2 | **Confirmation explicite** | "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer." |
| R3 | **Pas de créneaux inventés** | Slots issus de Google Calendar ou SQLite uniquement (RÈGLE 8 audit). |
| R4 | **Pas de slots → transfert** | Si aucun créneau dispo : message type "plus de créneaux" + transfert. |
| R5 | **1 redemande puis transfert** | Format invalide (ex. "je prends mercredi") : 1 redemande, puis transfert (CONFIRM_RETRY_MAX = 1). |

---

## 5. Cas limites & erreurs (PRD §11, SYSTEM §7–8)

| # | Cas | Comportement attendu |
|---|-----|----------------------|
| L1 | **Message vide** | "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?" (web) ; vocal : MSG_SILENCE_1 puis MSG_SILENCE_2 puis INTENT_ROUTER (RÈGLE 3). |
| L2 | **Message > 500 car.** | "Votre message est trop long. Pouvez-vous résumer ?" |
| L3 | **Insultes / spam** | Transfert humain **silencieux** immédiat (pas de message). |
| L4 | **Langue non française** | "Je ne parle actuellement que français." |
| L5 | **Session expirée (15 min)** | "Votre session a expiré. Puis-je vous aider ?" (SESSION_TTL_MINUTES = 15). |
| L6 | **Historique** | Max 10 derniers messages (MAX_MESSAGES_HISTORY = 10). |

---

## 6. Format réponse FAQ (PRD §12, SYSTEM §4)

| # | Règle | Détail |
|---|--------|--------|
| F1 | **Structure** | [Réponse factuelle] + ligne "Source : [FAQ_ID]". |
| F2 | **Pas de reformulation** | Réponse exacte FAQ, pas de paraphrase. |

---

## 7. Règles audit vocal (10 règles globales)

| # | Nom | Résumé | Config / code |
|---|-----|--------|----------------|
| **1** | **Intent override absolu** | CANCEL, MODIFY, TRANSFER, ABANDON, ORDONNANCE préemptent le flow. Détection avant guards. | `detect_strong_intent()`, `should_override_current_flow_v3()` |
| **2** | **Max recovery = 2** | Après N échecs sur un même champ (nom, slot_choice, phone, etc.) → INTENT_ROUTER (menu), pas transfert direct. | RECOVERY_LIMITS (name: 2, slot_choice: 3, phone: 2, silence: 3) |
| **3** | **Silence interdit** | Message vide : 1re fois MSG_SILENCE_1, 2e MSG_SILENCE_2, 3e → INTENT_ROUTER. + safe_reply() en filet. | empty_message_count, MSG_SILENCE_1/2, RECOVERY_LIMITS["silence"]=3 |
| **4** | **Anti-loop** | Max 25 tours (turn_count) → INTENT_ROUTER. Max 3 questions consécutives sans réponse concrète. | MAX_TURNS_ANTI_LOOP=25, MAX_CONSECUTIVE_QUESTIONS=3 |
| **5** | **Confirmer inférences** | Toute inférence (ex. préférence) → état de confirmation ("C'est bien ça ?") avant de l’utiliser. | PREFERENCE_CONFIRM, CONTACT_CONFIRM |
| **6** | **Répétition ≠ correction** | "Répétez" / "redites" → rejouer dernier message agent. "Attendez" / "erreur" / "trompé" → rejouer dernière question. | detect_user_intent_repeat(), last_agent_message, last_question_asked |
| **7** | **Contrainte horaire vs cabinet** | "Je finis à 17h" etc. : extraction heure ; si après CABINET_CLOSING_HOUR → message impossibilité + alternatives ou transfert. Filtrage créneaux si besoin. | extract_time_constraint(), CABINET_CLOSING_HOUR=19, TIME_CONSTRAINT_ENABLED |
| **8** | **No hallucination** | Aucun créneau hardcodé. Slots = get_slots_for_display() uniquement. Si 0 slot → transfert. | tools_booking, list_free_slots |
| **9** | **Une question à la fois** | Aucun message avec deux questions distinctes. Une étape qualif = une question. | Prompts / engine |
| **10** | **Caller ID respect** | Numéro Vapi : confirmation explicite ("Votre numéro est bien le … ?") avant utilisation. | CONTACT_CONFIRM, customer_phone |

---

## 8. Règle 11 — STT vocal (NOISE ≠ SILENCE)

| # | Règle | Détail |
|---|--------|--------|
| 11 | **NOISE vs SILENCE** | Transcript vide + **faible confidence** → NOISE (MSG_NOISE_1/2, puis INTENT_ROUTER). Transcript vide + pas de signal bruit → SILENCE (RÈGLE 3). Mots critiques (oui, non, ok, un, deux, trois) **jamais** classés NOISE. |
| 11b | **Partials ignorés** | transcriptType = "partial" → no-op (réponse `{"content": ""}`). Pas de réponse sur hypothèse STT. |
| 11c | **Fillers** | Normalisation début/fin uniquement. Ne pas supprimer : ok, oui, non. |
| 11d | **Reset noise** | noise_detected_count / last_noise_ts remis à 0 **uniquement** en état CONFIRMED ou TRANSFERRED. |
| 11e | **Seuils** | NOISE_CONFIDENCE_THRESHOLD=0.35, SHORT_TEXT_MIN_CONFIDENCE=0.50, MIN_TEXT_LENGTH=5, NOISE_COOLDOWN_SEC=2, MAX_NOISE_BEFORE_ESCALATE=3. |
| 11f | **Crosstalk (barge-in)** | Entrée UNCLEAR dans les CROSSTALK_WINDOW_SEC (5 s) après envoi de la dernière réponse agent, et longueur brute ≤ CROSSTALK_MAX_RAW_LEN (40) → réponse "Je vous écoute." sans incrémenter unclear_text_count ni transférer. Évite transfert quand le client parle pendant que le robot parle (TTS). |
| 11g | **Overlap (overlap ≠ unclear)** | UNCLEAR dans les OVERLAP_WINDOW_SEC (1,2 s) après envoi de la dernière réponse agent → réponse "Je vous ai entendu en même temps. Pouvez-vous répéter maintenant ?" sans incrémenter unclear_text_count. Timestamp : last_agent_reply_ts mis à jour à chaque réponse. |
| 11h | **Semi-sourd (speaking_until_ts)** | Pendant que l’agent « parle » (speaking_until_ts = now + estimate_tts_duration(reply)) : UNCLEAR/SILENCE → overlap_ignored ("Je vous écoute."), TEXT court (&lt;10 car) → "Pardon, pouvez-vous répéter ?". Mots critiques (oui, non, stop, humain, annuler, etc.) passent toujours (is_critical_overlap). |

---

## 9. Config & seuils (backend/config.py)

| Variable | Valeur | Rôle |
|----------|--------|------|
| FAQ_THRESHOLD | 0.80 | Match FAQ ≥ 80 % |
| SESSION_TTL_MINUTES | 15 | Timeout session |
| MAX_MESSAGES_HISTORY | 10 | Derniers messages conservés |
| MAX_MESSAGE_LENGTH | 500 | Refus au-delà |
| MAX_SLOTS_PROPOSED | 3 | Créneaux proposés |
| CONFIRM_RETRY_MAX | 1 | Redemande confirmation puis transfert |
| RECOVERY_LIMITS | name:2, slot_choice:3, phone:2, silence:3 | Échecs avant INTENT_ROUTER |
| CABINET_CLOSING_HOUR | 19 | RÈGLE 7 (contrainte horaire) |
| STT / NOISE_* | (voir §8) | Règle 11 |
| CROSSTALK_WINDOW_SEC | 5.0 | Fenêtre (s) après réponse agent : UNCLEAR court = crosstalk ignoré |
| CROSSTALK_MAX_RAW_LEN | 40 | Longueur max (car.) pour considérer entrée comme crosstalk |
| OVERLAP_WINDOW_SEC | 1.2 | Fenêtre (s) : UNCLEAR juste après réponse agent = overlap_guard (pas d’incrément) |

---

## 10. Critères de validation PRD (10 tests V1)

| # | Scénario | Résultat attendu |
|---|----------|------------------|
| V1 | FAQ "Quels sont vos horaires ?" | Réponse exacte + "Source : FAQ_HORAIRES" |
| V2 | Message vide | "Je n'ai pas reçu votre message…" |
| V3 | Message > 500 car. | "Votre message est trop long…" |
| V4 | "Hello" | "Je ne parle actuellement que français." |
| V5 | Booking complet | 3 slots → "oui 2" → confirmation |
| V6 | "je prends mercredi" | Redemande → puis transfert |
| V7 | Hors FAQ × 2 | Transfert (ou INTENT_ROUTER en V3) |
| V8 | Session 15 min | "Votre session a expiré…" |
| V9 | Insulte | Transfert silencieux |
| V10 | Temps première réponse | < 3 s (contrainte PRD, pas forcément appliquée dans le code) |

---

## 11. Sources des règles

| Document | Contenu |
|----------|--------|
| **PRD.md** | Scope V1, règles absolues §5, UX §6, qualification §7, cas limites §11, format FAQ §12, session §13, flows §15, critères de succès §16. |
| **SYSTEM_PROMPT.md** | Identité, règles absolues, jamais de silence, FAQ, qualification, flow RDV, transfert, cas limites, session, style. |
| **docs/RAPPORT_AUDIT_10_REGLES_VOCAL.md** | Règles 1–10 (intent override, recovery, silence, anti-loop, inférences, répétition/correction, contrainte horaire, no hallucination, une question, caller ID). |
| **docs/VAPI_STT_FIX.md** | Règle 11 (NOISE vs SILENCE, partials, fillers, seuils STT). |
| **backend/config.py** | Seuils (FAQ, session, message, slots, recovery, STT, cabinet). |
| **backend/prompts.py** | Tous les messages utilisateur (source unique de vérité). |

---

## 12. Synthèse pour analyse

- **Produit / comportement** : §1–6 (principes, absolues, qualification, RDV, cas limites, format FAQ).
- **Vocal / robustesse** : §7 (10 règles audit) + §8 (Règle 11 STT).
- **Chiffres** : §9 (config).
- **Validation** : §10 (10 critères PRD).

Tu peux couper par thème (ex. « tout ce qui touche au silence / vide / bruit » ou « tout ce qui touche à la confirmation ») et décider quoi garder, simplifier ou repousser en V2.
