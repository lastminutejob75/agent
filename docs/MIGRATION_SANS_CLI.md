# Migrations sans Railway CLI (bypass terminal)

Le CLI Railway peut avoir des soucis avec les menus interactifs (zsh, etc.). **Pas besoin** : les migrations s'exécutent **automatiquement au démarrage** du conteneur sur Railway.

## Ce qu'il faut faire

### 1. Ajouter Postgres sur Railway (dashboard)

1. Va sur **https://railway.app** → projet **cooperative-insight**
2. **+ New** → **Database** → **PostgreSQL**
3. Railway crée le service et injecte `DATABASE_URL` dans le service **agent**
4. Si besoin : service **agent** → **Variables** → **Add variable** → **Reference** → `DATABASE_URL` (depuis le service Postgres)

### 2. Déclencher un déploiement

```bash
git commit --allow-empty -m "chore: trigger deploy (migrations au startup)"
git push origin main
```

Ou modifie un fichier et push. Railway déploiera, et au démarrage du conteneur :

- `python scripts/run_migration.py 007` (si DATABASE_URL présent)
- `python scripts/run_migration.py 008`
- puis `uvicorn ...`

### 3. Vérifier

Une fois le déploiement terminé, les tables `tenant_users`, `magic_links`, `auth_events` existent.

## Pas besoin de

- `railway link`
- `make migrate-railway`
- Aucune commande Railway CLI

Tout se fait via le **dashboard** + **push**.
