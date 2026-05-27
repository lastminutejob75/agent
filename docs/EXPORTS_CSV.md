# Export CSV (appels & RDV)

Exports des journaux d'appels et de RDV au format CSV (compatible Excel FR par défaut).

## Vue d'ensemble

| Composant | Fichier |
|-----------|---------|
| Module exports | `backend/exports.py` (helpers + streaming) |
| Endpoints admin | `backend/routes/admin.py` (`/api/admin/exports/calls.csv` + `/bookings.csv`) |
| Endpoints tenant | `backend/routes/tenant.py` (`/api/tenant/exports/calls.csv` + `/bookings.csv`) |
| Composant UI admin | `landing/src/admin/components/ui/ExportCsvButton.jsx` |
| Helper UI client | `downloadCsvExport()` dans `landing/src/pages/AppCalls.jsx` |
| Tests | `tests/test_exports.py` (20 tests) |

## Format

- **Encodage** : UTF-8 avec BOM (`\ufeff`) en tête → Excel reconnaît automatiquement.
- **Délimiteur** : `;` par défaut (Excel FR ouvre direct sans wizard d'import). Configurable via le query param `delimiter=,` pour les outils US.
- **Fin de ligne** : `\r\n` (Windows-friendly).
- **Quoting** : minimal (`"..."` uniquement si la valeur contient un `;`, un `"`, ou un saut de ligne).
- **Streaming** : la réponse est servie par chunks de ~50 lignes via `StreamingResponse` (RAM constante même sur 20k lignes).

## Endpoints

### Calls

```
GET /api/admin/exports/calls.csv?days=30&tenant_id=42&result=rdv&limit=5000
GET /api/tenant/exports/calls.csv?days=30&result=rdv
```

Query params communs :

| Param | Type | Défaut | Description |
|-------|------|--------|-------------|
| `days` | int 1-365 | 30 | Fenêtre temporelle |
| `limit` | int 1-20000 | 5000 | Plafond hard |
| `result` | string | (vide) | `rdv` / `transfer` / `abandoned` / `error` |
| `delimiter` | string | `;` | `;` ou `,` |
| `tenant_id` | int | (admin uniquement) | Filtrer par tenant. Côté tenant : auto-détecté via cookie. |

Colonnes :

```
Date ; Heure ; Tenant ; Tenant ID ; Numero appelant ;
Resultat ; Duree ; Duree (s) ; Last event ; Call ID
```

Exemple de ligne (delimiter `;`) :

```
2026-05-09;08:30:00;Cabinet Dupont;42;+33612345678;RDV pris;1m 05s;65;booking_confirmed;abc-123
```

### Bookings (RDV pris)

```
GET /api/admin/exports/bookings.csv?days=30&tenant_id=42
GET /api/tenant/exports/bookings.csv?days=30
```

Colonnes :

```
Date prise ; Heure prise ; Tenant ; Tenant ID ; Patient ; Telephone ;
Date RDV ; Heure RDV ; Motif ; Statut ; Source ; Call ID
```

Source : événements `booking_confirmed` dans `ivr_events` + jointure `call_sessions` pour le numéro patient. Les champs `patient_name`, `rdv_at`, `motif` sont extraits du `meta_json` de l'événement (best-effort, certaines colonnes peuvent être vides selon la qualité des metadata).

## Authentification

- **Admin** : cookie session `uwi_admin_session` ou `Authorization: Bearer <ADMIN_API_TOKEN>`.
- **Tenant** : cookie session `uwi_session` (issu de `/api/tenant/auth/login`).
- 401 si pas authentifié, 404 si `tenant_id` admin inconnu.

Toutes les requêtes d'export passent par le **middleware audit-log** (cf. `docs/AUDIT_LOG_ADMIN.md`) côté admin, mais **pas pour les exports** (méthode GET → non audité par défaut, on ne trace que les writes).

## UI

### Côté admin (`/admin/calls` ou `/admin/calls?tenant_id=42`)

Composant `<ExportCsvButton />` dans le header. Hérite des filtres actifs (days, tenant_id, result).

```jsx
<ExportCsvButton
  url={`/api/admin/exports/calls.csv?days=${days}${tenantId ? `&tenant_id=${tenantId}` : ""}${resultFilter ? `&result=${resultFilter}` : ""}`}
  filename={`appels_${days}j.csv`}
  label="Exporter CSV"
/>
```

Le composant fait `fetch + Blob + <a download>` (pas de redirection, supporte les cookies HttpOnly et l'auth Bearer).

### Côté client (`/app/calls`)

Bouton inline avec helper `downloadCsvExport()`. Même mécanique :

```jsx
<button
  onClick={() => downloadCsvExport(`/api/tenant/exports/calls.csv?days=${days}`, `appels_${days}j.csv`)}
>
  Exporter CSV
</button>
```

## Performance

- **Volume max** : `limit=20000` (hard cap). Pour ~5000 lignes, < 200 ms côté serveur.
- **Mémoire** : streaming par chunks → RAM constante.
- **Timeout** : pas de timeout explicite côté serveur. La fenêtre `days` est limitée à 365 pour éviter les abus.

## Évolutions possibles

- Ajouter un format XLSX (vraies cellules typées date/durée) via `openpyxl`. Pour l'instant : CSV avec strings formatées.
- Pré-générer un export en background + envoyer un email avec un lien S3 quand on dépasse 50k lignes.
- Filtrer par patient/appelant côté serveur (actuellement pas supporté).
- Export "Activité" (combinaison calls + handoffs + bookings) sur une période donnée.

## Lien avec les autres systèmes

- Les filtres (days, tenant_id, result) sont les **mêmes** que `GET /api/admin/calls` → l'export est cohérent avec ce qui est affiché dans le tableau.
- Les metadata sont sanitisées au format affichable (durée `1m 05s`, résultat `RDV pris` au lieu de `rdv`) → directement lisible par l'utilisateur final.
