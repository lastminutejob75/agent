# Options et évolutions futures (multi-tenant)

Points optionnels listés dans l’audit, à traiter selon les besoins produit.

---

## #2 Calendar — credentials Google par tenant

**État actuel** : un seul `SERVICE_ACCOUNT_FILE` (ou base64) global ; par tenant seul le `calendar_id` (et `calendar_provider`) est dans `params_json`.

**Évolution possible** : pour une isolation forte par cabinet, prévoir des credentials Google par tenant (fichier ou JSON par tenant_id) ou une délégation de domaine (Domain-Wide Delegation), et charger le bon credential dans `calendar_adapter` / `GoogleCalendarService` selon `session.tenant_id`. Stockage : par ex. `tenant_config.params_json` avec une clé type `google_credentials_b64` ou table dédiée sécurisée.

---

## #9 Tracking — consommation par tenant

**État actuel** : aucun tracking de consommation (tokens LLM, minutes Vapi) par tenant dans le code.

**Évolution possible** :  
- Logger ou incrémenter des compteurs par `tenant_id` (table `tenant_usage` ou équivalent : date, tenant_id, tokens, minutes_vapi, etc.).  
- Intégrer les métriques Vapi (webhooks ou API) et les associer au tenant de l’appel.  
- Utilisation : facturation, quotas, alertes.

---

Voir aussi : `docs/AUDIT_MULTI_TENANT_READINESS.md` (plan #8 RLS, #5 doc ivr_events).
