# Désactiver la Vercel Toolbar (instrumentation)

La Vercel Toolbar est injectée par défaut sur les **preview deployments**. Elle charge un script (`vercel.live` / `instrument.*`) qui peut générer des warnings dans la console (ex. `[DEPRECATED] Default export is deprecated... zustand`). Ce script n’est pas dans notre codebase.

## Désactivation

### 1. Via le dashboard Vercel (recommandé)

1. **Vercel** → Projet landing → **Settings** → **General**
2. Section **Vercel Toolbar**
3. Pour **Preview** : choisir **Off**

### 2. Via variable d’environnement

Dans **Vercel** → Projet → **Settings** → **Environment Variables** :

| Variable | Valeur | Environnement |
|----------|--------|---------------|
| `VERCEL_PREVIEW_FEEDBACK_ENABLED` | `0` | Preview |

### 3. Pour la session en cours

Cliquer sur la toolbar → Menu → **Disable for Session**.

---

## Référence

- [Managing the Vercel Toolbar](https://vercel.com/docs/vercel-toolbar/managing-toolbar)
- [Vercel Toolbar](https://vercel.com/docs/workflow-collaboration)
