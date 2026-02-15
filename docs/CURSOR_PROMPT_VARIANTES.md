# Variantes de prompt Cursor (UWI)

En plus de la règle globale `.cursor/rules/production-critical.mdc` et du prompt complet `CURSOR_PROMPT_PRODUCTION_SAFE.md`, tu peux coller l’une de ces variantes selon le besoin.

---

## Mode debug

Coller en début de session quand tu veux investiguer sans toucher au comportement.

```
Tu es en mode DEBUG sur le backend UWI.
Objectif : comprendre / tracer / logger, pas modifier le comportement.

- Tu peux proposer des logs additionnels (sans supprimer les existants).
- Tu peux proposer des variables d’environnement de debug (ex. VAPI_DEBUG_*).
- Tu ne modifies pas la logique de booking, SSE, rapports, ni les textes prompts.py.
- Toute modification de code doit être désactivable (flag, env) ou clairement temporaire.
```

---

## Mode performance

Coller quand tu veux optimiser sans casser la prod.

```
Tu es en mode PERFORMANCE sur le backend UWI.
Objectif : réduire latence ou charge sans changer le comportement observable.

- Tu ne modifies pas : format SSE, premier chunk immédiat, raison 403/409/technical, textes, routes publiques.
- Tu peux : cache, lazy load, réduction d’appels redondants, logs conditionnels.
- Toute optimisation doit être mesurable (garder LATENCY_* / métriques existantes).
- Proposer un diff minimal et un moyen de rollback (feature flag ou config).
```

---

## Mode booking uniquement

Coller quand tu travailles uniquement sur le flux de prise de rendez-vous.

```
Tu travailles UNIQUEMENT sur le flux booking (qualif → slots → confirmation) du backend UWI.

- Ne pas toucher : rapport quotidien, email, webhooks Vapi, logs DECISION_TRACE / LATENCY_*.
- Ne pas modifier : get_free_slots / book_appointment (signatures, distinction 403/409/technical).
- Ne pas modifier les textes dans prompts.py.
- Tu peux modifier : engine (états booking), tools_booking (hors signatures critiques), validation_config (états booking).
- Toute modification doit rester déterministe et testable (tests existants verts).
```

---

Pour chaque session, garder en tête : **stabilité > élégance**, **déterminisme > intelligence**.
