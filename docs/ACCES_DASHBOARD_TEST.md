# Accéder au tableau de bord (test)

Pour voir le dashboard connecté avec ton numéro/tenant de test.

---

## 1. Ajouter ton email au tenant

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

## 4. Connexion

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
