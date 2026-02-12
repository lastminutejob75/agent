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

**Erreur 403 "Permission denied" ?** → Le token n'a pas accès à `uwi-landing`. Recrée-le avec les étapes ci-dessous.

### Classic (recommandé pour ce cas)

1. **https://github.com/settings/tokens**
2. **"Generate new token (classic)"**
3. **Note** : `UWI sync uwi-landing`
4. **Expiration** : 90 jours ou No expiration
5. **Scopes** : coche **`repo`** (accès complet)
6. Génère et copie le token (`ghp_...`)
7. Met à jour le secret : https://github.com/lastminutejob75/agent/settings/secrets/actions

### Fine-grained (alternative)

1. **https://github.com/settings/tokens?type=beta**
2. **"Generate new token (fine-grained)"**
3. **Repository access** : **Only select repositories** → ajoute **`uwi-landing`**
4. **Permissions** → **Repository permissions** → **Contents** : **Read and write**
5. Génère et copie le token (`github_pat_...`)
6. Met à jour le secret dans agent

## Dépannage

| Erreur | Cause | Solution |
|--------|-------|----------|
| **Bad credentials** | Token invalide, expiré ou mal collé | Recrée un token Classic (scope `repo`), copie-colle sans espace ni saut de ligne, met à jour le secret |
| **403 Permission denied** | Token sans accès à uwi-landing | Classic : scope `repo` obligatoire. Fine-grained : ajouter `uwi-landing` + Contents Read and write |

**Vérifier le secret** : Settings → Secrets → UWI_LANDING_PAT doit exister. Pour le modifier : "Update" et coller le nouveau token (sans espaces avant/après).

## Vérifier

Après configuration, le prochain push qui modifie `landing/**` déclenchera le workflow. Consulte **Actions** sur le dépôt pour voir le résultat.
