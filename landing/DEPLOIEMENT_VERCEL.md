# 🚀 Déploiement Backend sur Vercel

## ✅ Avantages

- ✅ **Même plateforme que la landing page** (tout au même endroit)
- ✅ **Déploiement automatique** depuis GitHub
- ✅ **HTTPS automatique** (certificats gérés)
- ✅ **Gratuit** pour commencer (100GB bandwidth/mois)
- ✅ **URL stable** : `https://votre-projet.vercel.app`
- ✅ **Pas besoin de ngrok** ou autre tunnel

---

## 📁 Structure créée

```
agent-accueil-pme/
├── api/
│   └── index.py          # Point d'entrée Vercel (serverless)
├── vercel.json           # Configuration Vercel
├── requirements.txt      # (mangum ajouté)
└── backend/              # Code existant (inchangé)
```

---

## 🔧 Configuration

### 1. Fichier `vercel.json` (créé)

Configure les routes :
- `/api/*` → Backend FastAPI
- `/health`, `/chat`, `/stream/*` → Backend
- `/*` → Landing page (dans `/landing`)

### 2. Fichier `api/index.py` (créé)

Adapte FastAPI pour Vercel avec Mangum (ASGI → Lambda).

### 3. Dépendance `mangum` (ajoutée)

Adapter ASGI pour Vercel serverless functions.

---

## 🚀 Déploiement

### Option 1 : Via GitHub (Recommandé)

1. **Push le code sur GitHub** (si pas déjà fait)
   ```bash
   git add .
   git commit -m "feat: Add Vercel deployment config"
   git push origin main
   ```

2. **Dans Vercel Dashboard** :
   - Allez sur https://vercel.com
   - Importez le projet (ou reconnectez-le)
   - Vercel détectera automatiquement `vercel.json`
   - Déploiement automatique !

3. **Récupérer l'URL** :
   - Dans Vercel Dashboard → Settings → Domains
   - Ou dans l'onglet "Deployments"
   - URL : `https://votre-projet.vercel.app`

### Option 2 : Via Vercel CLI

```bash
# Installer Vercel CLI
npm i -g vercel

# Login
vercel login

# Déployer
cd /Users/actera/agent-accueil-pme
vercel

# Production
vercel --prod
```

---

## 🔗 Configuration Vapi

Une fois déployé sur Vercel, configurez dans Vapi :

**Server URL :**
```
https://votre-projet.vercel.app/api/vapi/webhook
```

**Méthode :** `POST`

**Headers :** (optionnel)
```
Content-Type: application/json
```

---

## 🧪 Tests

### 1. Health Check
```bash
curl https://votre-projet.vercel.app/health
```

### 2. Vapi Health
```bash
curl https://votre-projet.vercel.app/api/vapi/health
```

### 3. Vapi Test
```bash
curl https://votre-projet.vercel.app/api/vapi/test
```

### 4. Webhook Vapi
```bash
curl -X POST https://votre-projet.vercel.app/api/vapi/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "type": "user-message",
      "content": "bonjour"
    },
    "call": {
      "id": "test_001"
    }
  }'
```

---

## ⚠️ Limitations Vercel Serverless

### 1. SSE (Server-Sent Events)

**Problème :** Vercel serverless functions ont un timeout (10s sur gratuit, 60s sur Pro).

**Solution :** 
- Pour le webhook Vapi, ça fonctionne (pas de SSE)
- Pour le frontend web avec SSE, il faudra peut-être adapter ou utiliser WebSockets

**Pour Vapi :** ✅ Pas de problème, le webhook est synchrone.

### 2. SQLite en lecture seule

**Problème :** Vercel serverless functions sont stateless, SQLite écrit sur `/tmp` qui peut être effacé.

**Solutions :**
- **Option A :** Utiliser une DB externe (PostgreSQL, Supabase, etc.)
- **Option B :** Utiliser Vercel KV (Redis) pour les sessions
- **Option C :** Pour V1, SQLite en lecture seule fonctionne (FAQ, slots)

**Pour Vapi :** Les sessions sont en mémoire, donc ça fonctionne pour les appels vocaux.

### 3. Sessions en mémoire

**Problème :** Les sessions sont stockées en mémoire (`STREAMS`, `SessionStore`).

**Impact :** 
- ✅ Fonctionne pour Vapi (chaque appel = nouvelle session)
- ⚠️ Pour le web, les sessions peuvent être perdues entre les invocations

**Solution V1 :** Acceptable pour MVP, améliorer en V2 avec Redis/KV.

---

## 🔧 Variables d'environnement

Si vous avez des secrets (Google Calendar, etc.) :

1. **Dans Vercel Dashboard** :
   - Settings → Environment Variables
   - Ajouter vos variables

2. **Ou via CLI** :
   ```bash
   vercel env add GOOGLE_CALENDAR_ID
   vercel env add GOOGLE_SERVICE_ACCOUNT_FILE
   ```

---

## 📊 Structure des URLs

Après déploiement :

```
https://votre-projet.vercel.app/
├── /                    → Landing page (depuis /landing)
├── /health              → Backend health check
├── /api/vapi/webhook    → Webhook Vapi ✅
├── /api/vapi/health     → Vapi health check
├── /api/vapi/test       → Vapi test endpoint
├── /chat                → Backend chat (web)
└── /stream/{id}         → Backend SSE (web)
```

---

## 🐛 Debugging

### Voir les logs

```bash
# Via CLI
vercel logs

# Ou dans le Dashboard
# Vercel → Deployments → [Dernier déploiement] → Functions → Logs
```

### Erreurs communes

1. **"Module not found"**
   - Vérifier que `requirements.txt` contient toutes les dépendances
   - Vérifier que `mangum` est installé

2. **"Timeout"**
   - Vérifier que les fonctions répondent en < 10s (gratuit)
   - Optimiser le code si nécessaire

3. **"Database locked"**
   - SQLite peut avoir des problèmes en écriture simultanée
   - Pour Vapi (webhook synchrone), ça devrait fonctionner

---

## ✅ Checklist de déploiement

- [ ] `vercel.json` créé
- [ ] `api/index.py` créé
- [ ] `mangum` ajouté à `requirements.txt`
- [ ] Code pushé sur GitHub
- [ ] Projet connecté dans Vercel
- [ ] Déploiement réussi
- [ ] URL récupérée
- [ ] Tests health check OK
- [ ] Tests webhook Vapi OK
- [ ] Configuration dans Vapi mise à jour
- [ ] Test appel réel effectué

---

## 🎯 Résumé

**Avant (avec ngrok) :**
- ❌ URL change à chaque redémarrage
- ❌ Besoin de laisser le Mac allumé
- ❌ Tunnel intermédiaire (latence)

**Après (avec Vercel) :**
- ✅ URL stable : `https://votre-projet.vercel.app`
- ✅ Disponible 24/7
- ✅ HTTPS automatique
- ✅ Déploiement automatique
- ✅ Même plateforme que la landing page
- ✅ Gratuit pour commencer

---

**Prêt à déployer ! 🚀**
