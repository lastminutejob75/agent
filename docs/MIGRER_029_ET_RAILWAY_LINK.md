# Migration 029 + Railway link — Guide rapide

## Problèmes courants

### 1. `failed to resolve host 'host'`
Tu as utilisé un placeholder. Il faut la **vraie** URL Postgres de Railway, pas `postgresql://user:pass@host:port/railway`.

### 2. `npx railway link # si pas encore fait` → erreur `#`
En zsh, ne mets **pas** le `#` sur la même ligne. Lance les commandes séparément :

```bash
npx railway link
```

Puis dans le menu : choisis le **projet** puis le **service backend** (celui qui a DATABASE_URL).

### 3. `No service linked`
Il faut d’abord lancer `npx railway link` et sélectionner le service. Une fois lié, les commandes `railway run` fonctionneront.

---

## Option A : Migration 029 via Railway CLI (recommandé)

```bash
# 1. Lier le projet (une seule fois)
npx railway link

# 2. Lancer la migration (DATABASE_URL injectée automatiquement)
npx railway run make migrate-029
```

---

## Option B : Migration 029 avec URL manuelle

1. Va sur **https://railway.app** → ton projet
2. Clique sur le service **PostgreSQL** (ou celui qui expose la base)
3. Onglet **Connect** ou **Variables** → copie **Postgres Connection URL**
   - Format : `postgresql://postgres:XXXXX@containers-us-west-XXX.railway.app:5432/railway`
4. Lance :

```bash
DATABASE_URL='postgresql://postgres:xxx@containers-xxx.railway.app:5432/railway' make migrate-029
```

(Colle l’URL réelle, sans espaces, entre les guillemets.)

---

## Option C : Déploiement (migration au démarrage)

La migration 029 est exécutée **automatiquement au démarrage** du conteneur (voir `backend/railway_run.py`). Un simple push déclenche un redéploiement :

```bash
git commit --allow-empty -m "chore: trigger deploy"
git push
```

Après le déploiement, la migration 029 s’exécutera au démarrage.

---

## Reset mot de passe admin

```bash
# 1. Lier Railway (si pas fait)
npx railway link

# 2. Réinitialiser le mot de passe
./scripts/admin_reset_password.sh UwiAdmin#2026
```

Puis sur Railway → Variables : vérifier que **ADMIN_EMAIL** = `henigoutal@gmail.com`.

---

## Requête SQL (tenants)

Pour exécuter du SQL, utilise `psql` ou un client DB :

```bash
# Avec l’URL Postgres
psql 'postgresql://postgres:xxx@host:port/railway' -c "SELECT id FROM tenants LIMIT 5;"
```

Ou via Railway :

```bash
npx railway run psql \$DATABASE_URL -c "SELECT id FROM tenants LIMIT 5;"
```
