# Statut multi-tenant

## ✅ En place

| Composant | Statut | Détail |
|-----------|--------|--------|
| **Feature flags** | OK | `tenant_config`, `get_flags()`, cache TTL 60s, `session.flags_effective` |
| **DID routing** | OK | `tenant_routing`, `resolve_tenant_id_from_vocal_call()`, extraction Vapi |
| **Ordre d'exécution** | OK | `[TENANT_ROUTE]` loggé avant tout `_persist_ivr_event` |
| **Scope events** | OK | Vocal : `tenant_id` utilisé pour ivr_events (rapport quotidien) |
| **Logs** | OK | `[TENANT_ROUTE] to=... tenant_id=... source=route|default` |
| **Intégration** | OK | Webhook, tool, chat/completions |

## ⚠️ Multi-tenant partiel

### Calendrier (provider par tenant)

**État** : `CalendarAdapter` en place. Provider par tenant via `params_json`.

**Schéma `params_json`** :
```json
{
  "calendar_provider": "google",
  "calendar_id": "xxx@group.calendar.google.com"
}
```

| provider | Comportement |
|----------|--------------|
| `google` | Utilise `calendar_id` (params ou config global) |
| `none` | Pas de créneaux, pas de booking → collecte demande + transfert |
| (vide) | Fallback config global `GOOGLE_CALENDAR_ID` (migration sans downtime) |

**Migration** : tant que tenant n'a pas `calendar_provider` → comportement legacy (global).

---

## Garde-fou optionnel (numéro non routé)

**Variable** : `ENABLE_TENANT_ROUTE_MISS_GUARD` (env, default: false)

Si `true` et `source=default` sur vocal avec un numéro connu (to_number présent mais pas de route) :
- Log `[TENANT_ROUTE_MISS] to=... tenant_id=... numéro non onboardé`
- TODO : transfert immédiat possible (à brancher si besoin)
