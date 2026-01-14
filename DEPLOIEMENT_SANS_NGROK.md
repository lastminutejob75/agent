# 🚀 Déploiement sans ngrok - Alternatives

## ✅ Pourquoi se passer de ngrok ?

- ✅ **Gratuit en production** (vs ngrok payant pour domaines persistants)
- ✅ **URL stable** (pas de changement à chaque redémarrage)
- ✅ **HTTPS automatique** (certificats gérés)
- ✅ **Disponible 24/7** (pas besoin de laisser votre Mac allumé)
- ✅ **Meilleure performance** (pas de tunnel intermédiaire)

---

## 🎯 Option 1 : Railway (Recommandé - Le plus simple)

### Avantages
- ✅ Gratuit jusqu'à 500h/mois
- ✅ Déploiement en 2 minutes
- ✅ Support Docker natif
- ✅ URL HTTPS automatique
- ✅ Variables d'environnement faciles

### Déploiement

1. **Créer un compte** : https://railway.app
2. **Installer Railway CLI** :
   ```bash
   npm i -g @railway/cli
   railway login
   ```

3. **Déployer** :
   ```bash
   cd /Users/actera/agent-accueil-pme
   railway init
   railway up
   ```

4. **Récupérer l'URL** :
   ```bash
   railway domain
   ```
   Vous obtiendrez : `https://votre-projet.railway.app`

5. **Configurer dans Vapi** :
   - Server URL : `https://votre-projet.railway.app/api/vapi/webhook`

### Coût
- **Gratuit** : 500h/mois, $5 de crédit gratuit
- **Payant** : $5/mois pour plus de ressources

---

## 🎯 Option 2 : Render (Gratuit)

### Avantages
- ✅ Plan gratuit disponible
- ✅ Support Docker
- ✅ HTTPS automatique
- ✅ Déploiement depuis GitHub

### Déploiement

1. **Créer un compte** : https://render.com
2. **Connecter GitHub** (ou push le code)
3. **Créer un nouveau Web Service**
4. **Configuration** :
   - **Build Command** : `docker build -t agent-accueil .`
   - **Start Command** : `docker run -p 8000:8000 agent-accueil`
   - **Ou directement** : `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

5. **Récupérer l'URL** :
   - Render vous donne : `https://votre-projet.onrender.com`

### Coût
- **Gratuit** : Service peut s'endormir après 15 min d'inactivité
- **Starter** : $7/mois pour service toujours actif

---

## 🎯 Option 3 : Fly.io (Gratuit)

### Avantages
- ✅ Gratuit généreux
- ✅ Support Docker
- ✅ Global edge network
- ✅ CLI simple

### Déploiement

1. **Installer Fly CLI** :
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login** :
   ```bash
   fly auth login
   ```

3. **Créer l'app** :
   ```bash
   cd /Users/actera/agent-accueil-pme
   fly launch
   ```

4. **Déployer** :
   ```bash
   fly deploy
   ```

5. **Récupérer l'URL** :
   ```bash
   fly info
   ```
   Vous obtiendrez : `https://votre-projet.fly.dev`

### Coût
- **Gratuit** : 3 VMs partagées, 160GB sortie/mois
- **Payant** : À partir de $1.94/mois

---

## 🎯 Option 4 : Cloudflare Tunnel (Alternative locale)

Si vous voulez rester en local mais avec une URL stable :

### Installation

```bash
# macOS
brew install cloudflare/cloudflare/cloudflared

# Ou télécharger depuis
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
```

### Utilisation

```bash
# Créer un tunnel (une seule fois)
cloudflared tunnel create agent-accueil

# Exposer le port 8000
cloudflared tunnel route dns agent-accueil votre-domaine.com
cloudflared tunnel run agent-accueil --url http://localhost:8000
```

### Avantages
- ✅ Gratuit
- ✅ URL personnalisée possible
- ✅ HTTPS automatique
- ✅ Pas de limite de temps

---

## 🎯 Option 5 : localtunnel (Alternative npm)

Alternative simple à ngrok :

```bash
# Installer
npm install -g localtunnel

# Utiliser
lt --port 8000
```

Vous obtiendrez : `https://xxx.loca.lt`

### Avantages
- ✅ Gratuit
- ✅ Simple
- ⚠️ URL change à chaque fois (comme ngrok gratuit)

---

## 📊 Comparaison rapide

| Solution | Gratuit | URL Stable | Setup | Recommandé |
|----------|---------|------------|-------|------------|
| **Railway** | ✅ (500h/mois) | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Render** | ✅ (avec sleep) | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Fly.io** | ✅ | ✅ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Cloudflare Tunnel** | ✅ | ✅ | ⭐⭐ | ⭐⭐⭐ |
| **localtunnel** | ✅ | ❌ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

---

## 🚀 Recommandation : Railway

**Pourquoi Railway ?**
1. ✅ Le plus simple à déployer
2. ✅ Gratuit généreux (500h/mois)
3. ✅ URL stable immédiatement
4. ✅ Support Docker natif
5. ✅ Variables d'environnement faciles
6. ✅ Logs en temps réel

**Commandes rapides Railway :**
```bash
# Installer
npm i -g @railway/cli

# Login
railway login

# Dans le projet
cd /Users/actera/agent-accueil-pme
railway init
railway up

# Récupérer l'URL
railway domain

# Voir les logs
railway logs
```

---

## 🔧 Configuration Vapi après déploiement

Une fois déployé, dans Vapi :

1. **Server URL** : `https://votre-url.railway.app/api/vapi/webhook`
2. **Méthode** : `POST`
3. **Headers** : (optionnel) `Content-Type: application/json`

---

## 📝 Notes importantes

### Variables d'environnement
Si vous avez des secrets (Google Calendar, etc.), configurez-les dans :
- Railway : Dashboard → Variables
- Render : Dashboard → Environment
- Fly.io : `fly secrets set KEY=value`

### Base de données
SQLite fonctionne en local, mais pour la production, considérez :
- **Railway** : PostgreSQL addon (gratuit 1GB)
- **Render** : PostgreSQL (gratuit 90 jours)
- **Fly.io** : Volume persistant

---

## ✅ Checklist de déploiement

- [ ] Choisir une plateforme (Railway recommandé)
- [ ] Créer un compte
- [ ] Déployer le backend
- [ ] Récupérer l'URL HTTPS
- [ ] Tester le webhook : `curl https://votre-url/api/vapi/health`
- [ ] Configurer l'URL dans Vapi
- [ ] Tester un appel réel
- [ ] Configurer les variables d'environnement si nécessaire

---

**Recommandation finale : Railway pour la simplicité et la stabilité ! 🚂**
