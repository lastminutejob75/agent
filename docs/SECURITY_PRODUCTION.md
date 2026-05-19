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

**Important :** le rôle `postgres` Railway **contourne** le RLS. Pour une isolation effective :

1. Créer un rôle `uwi_app` (LOGIN, non superuser).
2. `GRANT` SELECT/INSERT/UPDATE/DELETE sur les tables applicatives.
3. Pointer `DATABASE_URL` vers `uwi_app` (pas `postgres`).

Les routes admin authentifiées peuvent poser `SET LOCAL app.bypass_tenant_rls = 'on'` (voir `backend/pg_tenant_context.py`).

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
