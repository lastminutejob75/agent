# Scénarios vocal — impact des changements

**Objectif :** Anticiper les régressions. Avant de modifier un prompt ou une branche engine, vérifier les scénarios et tests listés ci-dessous.

---

## 1. Parcours vocal complet (référence)

| Étape | État / action | Fichiers / symboles concernés | Règle UX |
|-------|----------------|------------------------------|----------|
| **Start** | User dit « rendez-vous » / « rdv » | `engine`: intent start → booking, `prompts`: VOCAL_NAME_ASK | 1 phrase utile, pas de « je n'ai pas compris » |
| **Nom** | 1re question agent | `prompts`: get_qualif_question("name") → VOCAL_NAME_ASK = "Parfait. À quel nom…" | 1 seul « Parfait » ici (début booking) |
| **Après nom** | 2e question (préférence) | `engine`: _next_qualif_step, `prompts`: get_qualif_question_with_name("pref") | **Pas** de 2e « Parfait » (pas d'ack, pas de wrap_with_signal) |
| **Préférence** | matin / après-midi | `prompts`: QUALIF_QUESTIONS_VOCAL["pref"], PREFERENCE_CONFIRM | Pas de sur-confirmation |
| **Créneaux** | proposition 1/2/3 | `prompts`: format_slot_proposal (vocal), VOCAL_CONFIRM_SLOTS | Un, deux, trois — pas « oui 1 » |
| **Choix créneau** | User dit « un » / « deux » / « trois » | `engine`: WAIT_CONFIRM, `prompts`: format_slot_early_confirm | Confirmation courte : « C'est noté. Le créneau… » (pas « Parfait » ici pour varier) |
| **Contact** | Demande numéro | `prompts`: VOCAL_PHONE_CONFIRM, VOCAL_CONTACT_CONFIRM | « Je confirme votre numéro : … Dites oui ou non. » |
| **Confirmation numéro** | User dit « oui » / « c'est bien ça » | `engine`: CONTACT_CONFIRM → YES implicite, puis booking | 1 filet max, pas de relecture après filet |
| **Message final** | RDV confirmé + rappel | `prompts`: format_booking_confirmed_vocal, VOCAL_BOOKING_CONFIRMED | TTS-friendly : **pas « SMS »** (→ « message de rappel »), virgule pour prosodie |

---

## 2. Avant de modifier… vérifier

### Modifier un prompt vocal (`backend/prompts.py`)

- **VOCAL_NAME_ASK, QUALIF_QUESTIONS_VOCAL, get_qualif_question_with_name**  
  → Scénario **Start + après nom** : pas deux « Parfait » sur deux tours consécutifs.  
  → Tests : `test_vocal_no_double_parfait_after_name`, `test_vocal_booking_confirmed_tts_friendly`.

- **format_booking_confirmed_vocal / VOCAL_BOOKING_CONFIRMED**  
  → Scénario **Message final** : pas d’emoji, pas d’abréviation « SMS » (TTS hachuré).  
  → Tests : `test_vocal_booking_confirmed_no_emoji`, `test_vocal_booking_confirmed_tts_friendly`.

- **MSG_SLOT_EARLY_CONFIRM_VOCAL, format_slot_early_confirm**  
  → Scénario **Confirmation créneau** : varier avec la fin (pas « Parfait » + « Parfait » au message final).  
  → Vérifier manuellement : créneau → contact → message final.

- **TransitionSignals, wrap_with_signal**  
  → Utilisé ailleurs qu’en _next_qualif_step (ex. processing). Ne pas réintroduire d’appel en _next_qualif_step (vocal) pour éviter 2e « Parfait » en start.

### Modifier l’engine (`backend/engine.py`)

- **_next_qualif_step**  
  → Ne pas réactiver `wrap_with_signal(question, "PROGRESSION")` en vocal (double Parfait après le nom).  
  → Scénario : start → nom → préférence (2e tour agent sans Parfait).

- **_start_booking_with_extraction**  
  → 1 acknowledgement max : pas d’ack si la question commence déjà par un ack (ex. VOCAL_NAME_ASK).

- **CONTACT_CONFIRM (oui / numéro)**  
  → YES implicite, filet « oui ou non », pas de relecture du numéro après filet.

---

## 3. Tests de non-régression (à lancer après tout changement vocal)

```bash
pytest tests/test_prompt_compliance.py -v -k "vocal"
pytest tests/test_vocal_confirmations.py -v
pytest tests/test_repeat_and_yesno_context.py -v
```

**Tests critiques ajoutés pour éviter les casses :**

- `test_vocal_booking_confirmed_tts_friendly` : message final contient « message » (pas « SMS »), pas d’emoji.
- `test_vocal_no_double_parfait_after_name` : get_qualif_question_with_name("pref") en vocal ne commence pas par « Parfait » / « Très bien » / « D'accord ».

---

## 4. Checklist avant merge / déploiement

- [ ] Aucun nouveau « Parfait » / « Très bien » sur deux tours consécutifs (start et fin).
- [ ] Message final confirmation : « message de rappel » (pas « SMS »), formulation courte.
- [ ] `make test` ou `pytest tests/` vert (dont tests vocaux ci-dessus).
- [ ] Si changement de prompt ou d’engine vocal : parcourir mentalement le tableau §1 (parcours complet).

---

*Référence : CHECKLIST_AUDIT_UX_VOCAL.md, PRD_UX_VOCAL_V2.md.*
