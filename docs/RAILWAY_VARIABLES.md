# Variables d'environnement sur Railway

Guide minimal pour que tes variables soient bien prises en compte.

---

## Option A : Dashboard (interface web)

1. Va sur **https://railway.app** → connecte-toi.
2. Clique sur **ton projet** (pas "New Project").
3. Clique sur **le service** (la carte qui représente ton app backend, pas la base de données).
4. En haut tu as des onglets : **Deployments**, **Settings**, **Variables**, etc.
   - Clique sur **Variables**.
5. Tu vois une liste de variables (peut être vide).
   - Clique sur **"+ New Variable"** ou **"Add variable"** ou **"Raw Editor"**.
   - **Raw Editor** : tu peux coller plusieurs lignes d’un coup, une par variable :
     ```
     LLM_ASSIST_ENABLED=true
     ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxx
     ```
   - Ou ajoute une par une : **Name** = `LLM_ASSIST_ENABLED`, **Value** = `true`, puis une autre **Name** = `ANTHROPIC_API_KEY`, **Value** = ta clé.
6. Sauvegarde. Railway redéploie en général tout seul. Sinon : onglet **Deployments** → **Redeploy** sur le dernier déploiement.

**Important :** les variables se définissent **par service**. Si tu as plusieurs services (backend + DB), ajoute les variables sur le **service backend** (celui qui exécute le Dockerfile / Python).

---

## Option B : Railway CLI (souvent plus fiable)

Si le dashboard te semble confus, utilise le CLI.

1. Installe Railway CLI : **https://docs.railway.app/develop/cli**
   - Mac : `brew install railway`
2. Dans un terminal, à la racine de ton projet :
   ```bash
   cd /chemin/vers/agent-accueil-pme
   railway login
   railway link   # choisis ton projet + le service backend
   railway variables set LLM_ASSIST_ENABLED=true
   railway variables set ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxx
   ```
3. Redéploie si besoin : `railway up` ou déclenche un déploiement depuis le dashboard.

Les variables définies avec `railway variables set` sont bien injectées au prochain déploiement.

---

## Vérifier que ça marche

Après déploiement :

1. **Logs Railway**  
   Dans le dashboard : ton service → **Deployments** → clique sur le dernier déploiement → **View Logs**. Au démarrage tu dois voir par exemple :
   - `LLM_ASSIST_ENABLED: true`
   - `ANTHROPIC_API_KEY present: True`

2. **Endpoint debug**  
   Ouvre dans le navigateur (remplace par l’URL réelle de ton app Railway) :
   - `https://ton-app.railway.app/debug/env-vars`
   Tu dois voir `"llm_ready": true` si tout est bon.

Si `llm_ready` est `false`, vérifie que les variables sont bien sur le **bon service** (backend) et que tu as bien redéployé après les avoir ajoutées.
