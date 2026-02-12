# Checklist : mise en place des features en production

Code présent dans le repo ≠ feature en prod. Ce document liste ce qu'il faut faire pour chaque feature.

---

## 1. Multi-tenant

**Code** : `tenant_routing`, `resolve_tenant_id_from_vocal_call`, DID → tenant

**À faire** :
- [ ] Créer les tenants dans la DB (Railway ou SQLite)
- [ ] Configurer le routing DID → tenant (numéros Twilio/Vapi par client)
- [ ] Tester : appeler le numéro A → tenant 1, numéro B → tenant 2

**Variables** : `USE_PG_TENANTS`, tables `tenants`, `tenant_config`, `tenant_routing`

---

## 2. Auth Magic Link

**Code** : `POST /api/auth/request-link`, `GET /api/auth/verify`, `auth_pg.py`, `send_magic_link_email`

**À faire** :
- [ ] Migrations 007 + 008 exécutées sur Railway : `make migrate-railway`
- [ ] Backfill `tenant_users` : `make backfill-tenant-users`
- [ ] Configurer Postmark : `POSTMARK_SERVER_TOKEN`, `POSTMARK_FROM_EMAIL` (ou SMTP)
- [ ] Tester : entrer un email sur /login → recevoir le lien → cliquer → accès au dashboard

**Variables** : `POSTMARK_SERVER_TOKEN`, `POSTMARK_FROM_EMAIL`, `JWT_SECRET` (ou équivalent)

---

## 3. RGPD versionné

**Code** : `consent_obtained`, `consent_version`, `GET /api/tenant/rgpd`

**À faire** :
- [ ] Migrations OK
- [ ] `CONSENT_VERSION` défini dans `config.py`
- [ ] Tester : page /app/rgpd affiche les données consent_obtained

---

## 4. Consentement paramétrable (implicit/explicit)

**Code** : `consent_mode` dans params, `get_consent_mode()`, hook dans engine

**À faire** :
- [ ] `consent_mode` dans la whitelist des params (admin)
- [ ] Configurer par tenant : `{"consent_mode": "explicit"}` ou `"implicit"`
- [ ] Tester : appeler en mode explicit → prompt consentement avant traitement

---

## 5. Sync landing → uwi-landing

**Code** : workflow `.github/workflows/sync-landing.yml`, script `sync-landing-to-uwi-landing.sh`

**À faire** :
- [x] Secret `UWI_LANDING_PAT` configuré (token Classic scope `repo`)
- [ ] Vérifier : push sur landing/ → workflow s'exécute → uwi-landing mis à jour

---

## 6. Dashboard client (KPIs 7j)

**Code** : `GET /api/tenant/dashboard`, `GET /api/tenant/kpis`, `AppDashboard.jsx`

**À faire** :
- [ ] Migrations OK
- [ ] Auth Magic Link fonctionnel (pour accéder au dashboard)
- [ ] CORS configuré : `CORS_ORIGINS` inclut `https://uwiapp.com`
- [ ] Landing déployée sur uwiapp.com avec `VITE_UWI_API_BASE_URL` pointant vers le backend Railway
- [ ] Tester : login → /app → dashboard avec KPIs et graphique

---

## 7. Variables Railway gérées

**Code** : `scripts/railway-fix-variables.sh`, `make railway-fix-vars`

**À faire** :
- [ ] `railway link` : lier le projet au service backend
- [ ] `.env` avec les variables (TWILIO_*, SMTP_*) en local
- [ ] `make railway-fix-vars` après chaque push si variables "inactive"

---

## Prérequis : Postgres sur Railway

**DATABASE_URL absent ?** Le projet doit avoir une base Postgres.

1. Railway → projet **cooperative-insight** → **+ New** → **Database** → **PostgreSQL**
2. Une fois créé, Railway injecte `DATABASE_URL` dans les services liés
3. Vérifier : **agent** → **Variables** → `DATABASE_URL` doit exister
4. Si le Postgres est dans un autre service : **Variables** → **Add variable** → **Reference** → sélectionner `DATABASE_URL` du service Postgres

Puis : `make migrate-railway`

---

## Migrations sans Railway CLI

**Si `railway link` affiche des options bizarres** (zsh, menu confus) :

Les migrations 007+008 s'exécutent **automatiquement au démarrage** du backend (Dockerfile). Dès que `DATABASE_URL` est configuré sur Railway et que tu redéploies, les tables sont créées.

Pas besoin de `make migrate-railway` en local.

---

## Ordre recommandé

1. **Postgres** : créer la DB sur Railway si absente
2. **Redéployer** : les migrations s'exécutent au startup
3. **Backfill tenant_users** : `make backfill-tenant-users` (nécessite railway link ou DATABASE_URL en local)
4. **Email (Postmark/SMTP)** : pour envoyer les magic links
5. **CORS + VITE_UWI_API_BASE_URL** : pour que uwiapp.com appelle le backend
6. **Tester le flux complet** : login → dashboard → KPIs
