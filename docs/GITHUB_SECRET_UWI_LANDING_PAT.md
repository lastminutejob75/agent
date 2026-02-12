# Configurer UWI_LANDING_PAT (secret GitHub)

Le workflow `sync-landing` a besoin du secret `UWI_LANDING_PAT` pour pousser vers uwi-landing à chaque modification de `landing/`.

## Option 1 : Interface GitHub (le plus simple)

1. Va sur : **https://github.com/lastminutejob75/agent/settings/secrets/actions**
2. Clique **"New repository secret"**
3. **Name** : `UWI_LANDING_PAT`
4. **Value** : ton PAT (voir ci-dessous pour le créer)
5. Clique **"Add secret"**

## Option 2 : Ligne de commande (gh CLI)

```bash
# Installer gh si besoin (macOS)
brew install gh

# Se connecter
gh auth login

# Configurer le secret (demande la valeur)
gh secret set UWI_LANDING_PAT

# Ou via make
make gh-secret-sync
```

## Créer un PAT (Personal Access Token)

1. **https://github.com/settings/tokens**
2. **"Generate new token"** → **"Classic"** ou **"Fine-grained"**
3. **Classic** : coche `repo` (accès complet aux dépôts)
4. **Fine-grained** : dépôt `lastminutejob75/uwi-landing`, permission `Contents: Read and write`
5. Génère et copie le token (commence par `ghp_` ou `github_pat_`)

⚠️ Le token doit avoir accès en **écriture** au dépôt `uwi-landing`.

## Vérifier

Après configuration, le prochain push qui modifie `landing/**` déclenchera le workflow. Consulte **Actions** sur le dépôt pour voir le résultat.
