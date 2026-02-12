# Agent vocal : calendrier et confirmation

## 1. Problème : « oui je confirme » ne fonctionne pas

**Correction** : la phrase « oui je confirme » (réponse à « Vous confirmez ? ») est maintenant reconnue et acceptée comme confirmation du créneau.

Autres formules acceptées : « je confirme », « oui », « c'est bien ça », « parfait », etc.

---

## 2. Problème : agent non connecté à l’agenda

### Causes possibles

| Cause | Vérification |
|-------|--------------|
| **Variables Railway absentes** | `GOOGLE_SERVICE_ACCOUNT_BASE64` et `GOOGLE_CALENDAR_ID` définis ? |
| **Tenant avec provider=none** | `tenant_config.params_json` contient `"calendar_provider": "none"` ? |
| **Credentials invalides** | Tester via `GET /debug/force-load-credentials` |

### Diagnostic

1. **Backend** : `GET https://ton-backend.railway.app/debug/config`
   - `google_calendar_enabled: true` → credentials OK
   - `google_calendar_enabled: false` → vérifier `reason`

2. **Force load** : `GET /debug/force-load-credentials`
   - Affiche les erreurs éventuelles de chargement

3. **Tenant** : si multi-tenant, vérifier `params_json` :
   - `"calendar_provider": "google"` (ou absent pour legacy)
   - `"calendar_id": "xxx@group.calendar.google.com"`
   - Si `"calendar_provider": "none"` → SQLite fallback (pas de créneaux Google)

### Variables Railway nécessaires

| Variable | Description |
|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_BASE64` | JSON du Service Account encodé en base64 |
| `GOOGLE_CALENDAR_ID` | ID du calendrier cible (ex. `xxx@group.calendar.google.com`) |

### Encoder les credentials

```bash
base64 -i credentials/service-account.json | tr -d '\n' | pbcopy
# Coller dans GOOGLE_SERVICE_ACCOUNT_BASE64 sur Railway
```

Le calendrier doit être partagé avec l’email du Service Account (en lecture/écriture).
