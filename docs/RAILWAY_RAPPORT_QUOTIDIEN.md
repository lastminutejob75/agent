# Trouver l’URL du rapport quotidien sur Railway

## Ce qui se passe

- **Ton URL backend** : `https://ton-app.railway.app` → c’est bien le bon service (FastAPI) : `/health` répond 200.
- **Problème** : `/api/reports/daily` renvoie 404 car la **version déployée** sur Railway ne contient pas encore la route (ancien déploiement avant le push du rapport quotidien).

## À faire : forcer un redéploiement

1. Ouvre **Railway** : [railway.app](https://railway.app) → ton projet.
2. Clique sur le **service** qui correspond à cette app (celui qui a le domaine `ton-app.railway.app`).
3. Onglet **Deployments** (ou **Historique des déploiements**).
4. Vérifie que le **dernier déploiement** part bien du commit qu’on a poussé (message du type « Rapport IVR quotidien: endpoint /api/reports/daily... »).
   - Si le dernier déploiement est plus ancien : clique sur **Deploy** / **Redeploy** pour lancer un nouveau build à partir de `main`.
5. Attends la fin du **build** puis du **deploy** (statut vert / Running).

## Tester après le redéploiement

Dans un terminal :

```bash
curl -X POST "https://ton-app.railway.app/api/reports/daily" \
  -H "X-Report-Secret: MonRapportSecret2025"
```

- **200** + JSON avec `sent`, `errors`, etc. → OK, le rapport a été généré et envoyé (ou tenté).
- **403** → secret incorrect : vérifier que la variable d’environnement `REPORT_SECRET` sur Railway est bien `MonRapportSecret2025`.
- **503** → `REPORT_SECRET` non configuré sur Railway.
- **404** → la nouvelle version n’est pas encore déployée ; refaire un redeploy et réessayer.

## Résumé

| Étape | Action |
|--------|--------|
| 1 | Railway → ton projet → service avec `ton-app.railway.app` |
| 2 | Vérifier / lancer un **Redeploy** depuis `main` |
| 3 | Attendre la fin du déploiement |
| 4 | Lancer le `curl` ci‑dessus |

L’URL du rapport quotidien est donc la même que celle du backend : **`https://ton-app.railway.app`** (pas une autre URL).
