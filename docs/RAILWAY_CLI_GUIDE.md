# Utiliser Railway CLI

## 1. Installer le CLI

Ouvre un terminal et choisis **une** des méthodes :

**A) Avec npm (si tu as Node.js) :**
```bash
npm install -g @railway/cli
```

**B) Avec le script d’installation (Mac/Linux) :**
```bash
bash <(curl -fsSL https://railway.app/install.sh)
```

**C) Avec Homebrew (Mac) :**
```bash
brew install railway
```

Vérifie l’installation :
```bash
railway --version
```

---

## 2. Se connecter

Dans le dossier de ton projet (ou n’importe où) :
```bash
railway login
```
Une page web s’ouvre pour te connecter à ton compte Railway. Une fois connecté, reviens au terminal.

---

## 3. Lier le projet au service Railway

Va dans le dossier de ton repo :
```bash
cd /Users/actera/agent-accueil-pme
railway link
```

Le CLI te demande :
- **Select a project** → choisis ton projet (flèches + Entrée).
- **Select an environment** → souvent "production" ou le seul proposé.
- **Select a service** → choisis le **service backend** (celui qui déploie ton app Python/FastAPI), pas la base de données.

Une fois lié, les commandes suivantes s’appliquent à ce service.

---

## 4. Définir les variables

Toujours dans le même dossier :

```bash
railway variables set LLM_ASSIST_ENABLED=true
railway variables set ANTHROPIC_API_KEY=sk-ant-api03-TA_CLE_ICI
```

Remplace `sk-ant-api03-TA_CLE_ICI` par ta vraie clé Anthropic.

Pour vérifier que c’est enregistré (sans afficher les valeurs) :
```bash
railway variables
```

---

## 5. Redéployer

Les variables sont prises en compte au **prochain déploiement**. Tu peux :

- Déclencher un déploiement depuis le dashboard Railway (Deployments → Redeploy), ou
- Si tu déploies via Git : faire un petit commit vide et push, ou
- Avec le CLI : `railway up` (envoie le code actuel et redéploie).

---

## Vérifier toutes les variables

```bash
npx railway variables
```
Affiche toutes les variables du service lié (nom + valeur). **Ne pas partager la sortie** : elle contient des secrets (clés API, SMTP, etc.).

---

## Récap des commandes

```bash
npm install -g @railway/cli   # ou une autre méthode ci-dessus
railway login
cd /Users/actera/agent-accueil-pme
railway link                  # projet + service backend (ou railway service si déjà projet lié)
railway variables set LLM_ASSIST_ENABLED=true
railway variables set ANTHROPIC_API_KEY=ta_cle_anthropic
npx railway variables         # vérifier toutes les variables
```

Ensuite : redéploie, puis ouvre `https://ton-app.railway.app/debug/env-vars` pour voir `llm_ready: true`.
