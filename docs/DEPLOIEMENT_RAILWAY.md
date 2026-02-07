# Déployer sur Railway — version simple

Deux façons de déployer. Une seule suffit.

---

## Option 1 : Push Git (si ton repo est connecté à Railway)

1. **Vérifie que Railway utilise ce repo**
   - railway.app → ton projet → ton **service** (backend)
   - Onglet **Settings** : section **Source** ou **Repository**
   - Tu dois voir le repo GitHub (ex. `lastminutejob75/agent`) et une **branche** (souvent `main`)

2. **Déploie = push sur cette branche**
   - Dans ton terminal, à la racine du projet :
   ```bash
   git add -A
   git commit -m "deploy"
   git push origin main
   ```
   - Railway détecte le push et lance un nouveau déploiement tout seul.

3. **Voir le résultat**
   - railway.app → ton projet → **Deployments**
   - Le dernier déploiement doit passer en **Success** (vert). Si **Failed** (rouge), clique dessus et regarde les **logs** pour l’erreur.

---

## Option 2 : Railway CLI (`railway up`)

Tu as déjà fait `railway link` dans ce dossier.

1. À la racine du projet :
   ```bash
   cd /Users/actera/agent-accueil-pme
   npx railway up
   ```
2. Le CLI envoie le code à Railway et déclenche un déploiement.
3. Résultat dans **Deployments** sur le dashboard (comme en option 1).

---

## "J’arrive plus à déployer" — à vérifier

| Problème | À faire |
|----------|--------|
| **Rien ne se lance après un push** | Railway → Service → Settings : vérifier que la **source** est bien le bon repo + la bonne branche (`main` en général). |
| **Déploiement en Failed** | Cliquer sur le déploiement en erreur → **View Logs** : l’erreur (build ou démarrage) est en bas des logs. |
| **"No service" / "Not linked"** | Dans le dossier du projet : `npx railway link` et reselectionner le projet + le **service backend**. |
| **Build Docker qui échoue** | Souvent une dépendance ou un fichier manquant. Regarder la ligne indiquée dans les logs (ex. `COPY backend/` = le dossier `backend/` doit exister). |
| **L’app ne répond pas après déploiement** | Vérifier les variables d’env (ex. `PORT`), et que le **health check** répond : `https://ton-url/health`. |

---

## Récap en une ligne

- **Déploiement automatique (Git)** : `git push origin main` → Railway déploie si le repo est connecté.
- **Déploiement manuel (CLI)** : `npx railway up` dans le dossier du projet (après `railway link`).

Si tu me dis exactement ce que tu vois (message d’erreur ou écran Railway), je peux te dire quoi cliquer ou quoi taper.
