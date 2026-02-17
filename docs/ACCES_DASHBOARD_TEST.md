# Accéder au tableau de bord (test)

Pour accéder au dashboard. Le numéro de démo 09 39 24 05 75 est partagé (routé vers le tenant TEST interne). **Aucun lien entre onboarding et numéro démo** — voir [ARCHITECTURE_VOCAL_TENANTS.md](./ARCHITECTURE_VOCAL_TENANTS.md).

---

## Option A : Créer un compte

1. Aller sur **uwiapp.com/onboarding** (ou cliquer « Démarrer » sur la landing).
2. Remplir le formulaire : nom entreprise, **email** (celui que tu utiliseras pour te connecter), agenda.
3. Cliquer **Créer**. Le backend crée un tenant. Le **numéro de démo 09 39 24 05 75** reste une démo partagée (routé vers un tenant DEMO fixe, pas réassigné à chaque onboarding).
4. Cliquer **Se connecter au dashboard** (ou aller sur **/login**).
5. Saisir le même email → envoyer le lien → cliquer le Magic Link (ou en mode debug le lien s’affiche).
6. Tu arrives sur **/app** (dashboard de ton tenant). Pour tester la voix : appelez le 09 39 24 05 75 (démo partagée).

---

## Option B : Ajouter ton email à un tenant existant

Ton email doit être dans `tenant_users` pour pouvoir te connecter.

**En local** (si tu as DATABASE_URL dans .env) :
```bash
make add-tenant-user EMAIL=ton-email@exemple.com
```

**Via Railway** (depuis le dashboard, copie DATABASE_URL) :
```bash
DATABASE_URL="postgresql://..." python3 scripts/add_tenant_user.py ton-email@exemple.com
```

---

## 2. Variables Railway (service agent)

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Secret pour signer les JWT (ex: `openssl rand -hex 32`) |
| `APP_BASE_URL` | URL de la landing (ex: `https://uwiapp.com` ou `http://localhost:5173` en dev) |
| `ENABLE_MAGICLINK_DEBUG` | `true` → affiche le lien direct sans envoyer l’email (pour tester) |

---

## 3. Landing : pointer vers le backend

Dans `.env` de la landing (ou variables Vercel) :
```
VITE_UWI_API_BASE_URL=https://agent-production-xxx.up.railway.app
```

Remplace par l’URL réelle de ton backend Railway.

---

## 4. Connexion (Magic Link)

1. Va sur `/login` (landing)
2. Entre ton email (celui ajouté en étape 1)
3. Clique sur « Envoyer le lien »

**Si `ENABLE_MAGICLINK_DEBUG=true`** : le lien s’affiche directement sur la page. Clique dessus pour te connecter.

**Sans debug** : tu reçois un email (Postmark/SMTP configuré). Clique sur le lien dans l’email.

4. Tu es redirigé vers `/app` → dashboard avec KPIs 7j, graphique, etc.

---

## 5. CORS

Si erreur « CORS blocked » : ajoute l’origine de ta landing dans `CORS_ORIGINS` sur Railway, ex :
```
CORS_ORIGINS=https://uwiapp.com,https://www.uwiapp.com,http://localhost:5173
```
