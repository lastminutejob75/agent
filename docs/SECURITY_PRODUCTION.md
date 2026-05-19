# Sécurité production — UWi (données médicales)

## Variables Railway obligatoires

| Variable | Rôle |
|----------|------|
| `JWT_SECRET` | Sessions client (32+ caractères aléatoires) |
| `ADMIN_SESSION_SECRET` | Sessions admin (**différent** de `JWT_SECRET`) |
| `ADMIN_PASSWORD_HASH` | Mot de passe admin (bcrypt), pas de `ADMIN_PASSWORD` en clair |
| `VAPI_WEBHOOK_SECRET` | Signature webhooks Vapi (`x-vapi-secret`) |
| `ALLOW_GOOGLE_SELF_SIGNUP` | `false` en prod |
| `REDIS_URL` | Rate limiting distribué (recommandé multi-réplicas) |

## Migration RLS PostgreSQL

```bash
python scripts/run_migration.py 034
```

Active l’isolation par `tenant_id` en base. L’application pose `SET LOCAL app.current_tenant_id` sur chaque connexion tenant.

**Important :** sur Railway, `DATABASE_URL` pointe souvent vers l’utilisateur **`postgres`** (superutilisateur). En PostgreSQL, un superuser **contourne toujours le RLS**, même avec la migration 034.

### Procédure Railway (PostgreSQL)

1. Appliquer le RLS :
   ```bash
   railway run python scripts/run_migration.py 034
   ```

2. Créer le rôle applicatif (une seule fois) :
   ```bash
   railway run python scripts/setup_uwi_app_role.py
   ```
   Le script affiche :
   - le nouveau `DATABASE_URL` avec `uwi_app`
   - le mot de passe généré (ou utilisez `UWI_APP_PASSWORD=...` avant la commande)

3. Dans le **service backend** Railway → Variables :
   - Renommer l’ancienne URL : `DATABASE_URL_MIGRATE` = URL `postgres` actuelle (migrations uniquement)
   - Remplacer `DATABASE_URL` (et `PG_TENANTS_URL` si présent) par l’URL `uwi_app` affichée

4. Redéployer le backend.

5. Migrations futures (toujours avec le superuser) :
   ```bash
   railway run python scripts/run_migration.py 036
   ```
   (Railway injecte `DATABASE_URL` ; utilisez `DATABASE_URL_MIGRATE` en local si besoin.)

Les routes admin authentifiées posent `SET LOCAL app.bypass_tenant_rls = 'on'` pour les listes cross-tenant (voir `backend/pg_tenant_context.py`).

## Rôles applicatifs (RBAC)

| Rôle | Droits |
|------|--------|
| `owner` | Tout, dont facturation Stripe, paramètres système, agenda Google |
| `member` | Lecture / exploitation courante (appels, patients, profil cabinet) — **pas** facturation ni `/params` |

## RGPD / hébergement santé

Checklist à valider côté organisation (hors code) :

- [ ] Registre des traitements (finalités, durées de conservation)
- [ ] DPA avec sous-traitants (Railway, Vapi, Stripe, Google, Postmark…)
- [ ] Durée de rétention des enregistrements vocaux et transcripts
- [ ] Procédure droits des personnes (accès, effacement)
- [ ] Analyse d’impact (AIPD) si traitement à risque
- [ ] Hébergement : clarifier si HDS requis selon votre activité (non substituable par ce document)

## Déploiement sécurité

1. `git pull` + redéploiement Railway (backend + front).
2. `python scripts/run_migration.py 034` sur la base prod.
3. Vérifier `VAPI_WEBHOOK_SECRET` aligné avec Vapi.
4. Tester login client, login admin, appel démo, wizard lead.
