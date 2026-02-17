# Déploiement uwiapp.com sur Vercel

## Pourquoi le site affiche encore l’ancienne version ?

Le nouveau design UWi Medical est dans **ce repo (agent)** :
- `landing/src/components/UwiLanding.jsx` — design UWi Medical + liens Connexion `/login`, Démarrer `/onboarding`
- Commit : `feat(landing): UWi Medical design dans landing/ pour déploiement Vercel`

Si uwiapp.com pointe encore vers le **repo `uwi-landing`** (lastminutejob75/uwi-landing), Vercel ne voit jamais les commits du repo **agent**. Donc l’ancienne version reste en ligne.

## Solution : déployer depuis le repo agent

1. **Vercel** → Projet uwiapp.com → **Settings** → **General**.
2. **Repository** : passer à **lastminutejob75/agent** (et non uwi-landing).
3. **Root Directory** : `landing` (obligatoire).
   - Build sera exécuté dans `landing/` : `npm run build`, sortie `dist/`.
4. **Save** puis **Redeploy** (Deployments → … → Redeploy).

Vercel va alors builder le dossier `landing/` du repo agent ; la page d’accueil utilisera le nouveau design.

## Vérifier la config actuelle

- **Settings** → **General** :
  - **Root Directory** doit être `landing`.
  - **Framework Preset** : Vite (ou détecté).
- **Build & Development** :
  - **Build Command** : `npm run build` (défaut dans `landing/`).
  - **Output Directory** : `dist` (défaut dans `landing/vercel.json`).

## Si tu gardes temporairement le repo uwi-landing

Pour que uwiapp.com (toujours connecté à uwi-landing) affiche le nouveau design, il faut pousser le contenu de `landing/` vers le repo uwi-landing (sync manuel ou workflow GitHub Actions). Sinon, la solution recommandée est de faire pointer Vercel sur le repo **agent** avec Root Directory = **landing**.
