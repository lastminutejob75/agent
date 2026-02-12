# Checklist migration monorepo (Vercel + Railway)

Validation avant et après bascule sur le repo unique `agent`.

---

## Avant migration

- [ ] Backup du repo `uwi-landing` (au cas où)
- [ ] Vérifier que `agent/landing/` build correctement : `cd landing && npm run build`
- [ ] Noter l’URL Railway du backend (pour `VITE_UWI_API_BASE_URL`)

---

## Vercel (uwiapp.com)

1. **Settings → Git**
   - [ ] Déconnecter `uwi-landing`
   - [ ] Connecter `lastminutejob75/agent`

2. **Settings → General**
   - [ ] Root Directory : `landing`
   - [ ] Framework Preset : Vite (ou détecté)
   - [ ] Build Command : `npm run build`
   - [ ] Output Directory : `dist`

3. **Settings → Environment Variables**
   - [ ] `VITE_UWI_API_BASE_URL` = URL Railway (ex. `https://xxx.railway.app`)

4. **Deploy**
   - [ ] Déclencher un redeploy
   - [ ] Tester uwiapp.com (landing, onboarding, admin)

---

## Railway (backend)

1. **Build**
   - [ ] Le service utilise déjà le repo `agent`
   - [ ] `railway.toml` avec `watchPatterns` est en place
   - [ ] `.dockerignore` exclut `landing/`

2. **Vérifier**
   - [ ] Un push modifiant uniquement `landing/` ne déclenche pas de rebuild Railway
   - [ ] Un push modifiant `backend/` déclenche bien un rebuild

---

## uwi-landing (archivage)

1. **Avant d’archiver**
   - [ ] Mettre un README : `DEPRECATED: moved to lastminutejob75/agent/landing`
   - [ ] Attendre quelques jours en read-only
   - [ ] Vérifier qu’aucun lien ou script ne pointe encore vers uwi-landing

2. **Archiver**
   - [ ] Settings → Danger Zone → Archive repository

---

## Après migration

- [ ] Plus de script `sync_landing_to_uwiapp.sh`
- [ ] Push sur `agent/main` → Vercel déploie uwiapp.com, Railway déploie le backend (si watch paths match)
- [ ] Un seul repo à maintenir
