# Questionnaire (7 étapes) pas à jour sur uwiapp.com

Vercel est bien connecté au repo **agent**. Si le nouveau questionnaire n’apparaît pas en prod, c’est en général l’un des points suivants.

---

## 1. Root Directory ≠ `landing`

Si **Root Directory** dans Vercel est vide (ou autre que `landing`), le build part de la **racine** du repo. Le site déployé n’utilise alors pas le code dans `landing/` (où se trouve `CreerAssistante.jsx`).

**À faire :**

1. Vercel → projet uwiapp.com → **Settings** → **General**
2. **Root Directory** : mettre **`landing`** (et enregistrer)
3. **Redeploy** (Deployments → … → Redeploy)

Après ça, le build tourne dans `landing/` (`npm run build`, sortie `dist/`) et le questionnaire à jour est servi.

---

## 2. Build en échec

Si le dernier déploiement est en erreur, le site affiche l’avant-dernier build (ancien).

**À faire :** Vercel → **Deployments** → ouvrir le dernier déploiement → regarder les **Build Logs**. Corriger l’erreur (dépendances, env, etc.) puis **Redeploy**.

---

## 3. Cache / ancienne version

Navigateur ou CDN peut servir une vieille version.

**À faire :** test en navigation privée, ou avec un autre navigateur. Si besoin, sur Vercel : **Redeploy** avec “Clear cache and redeploy”.

---

## Récap

| Réglage Vercel | Valeur à avoir |
|----------------|----------------|
| Repository | `lastminutejob75/agent` |
| Root Directory | **`landing`** |
| Build Command | `npm run build` |
| Output Directory | `dist` |

Le questionnaire est dans **`landing/src/pages/CreerAssistante.jsx`**, route **`/creer-assistante`**. Dès que le build part bien de `landing/`, les changements sont en ligne sur **uwiapp.com/creer-assistante**.
