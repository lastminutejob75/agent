# Hooks pre-commit

Ce projet utilise [`pre-commit`](https://pre-commit.com/) pour exécuter automatiquement quelques vérifications légères avant chaque commit. Cela évite de pousser un commit "bête" qui casse la CI (lint, fichier trop gros, secret par accident, etc.).

## Configuration

Tout est dans `.pre-commit-config.yaml` à la racine. Hooks actifs :

| Hook | But |
|------|-----|
| `trailing-whitespace` | Supprime les espaces en fin de ligne |
| `end-of-file-fixer` | Ajoute `\n` final si manquant |
| `check-yaml` / `check-json` | Vérifie la syntaxe |
| `check-added-large-files` | Refuse > 500 KB (évite gros assets non compressés dans git) |
| `check-merge-conflict` | Refuse les markers `<<<<<<<` |
| `detect-private-key` | Détecte une clé privée (RSA, SSH...) accidentellement committée |
| `ruff` | Lint Python (mêmes règles que la CI, cf. `pyproject.toml`) |
| `gitleaks` | Scan diff pour secrets (tokens, API keys) |

## Installation (une seule fois par dev)

```bash
pip install pre-commit
pre-commit install
```

`pre-commit install` installe le hook dans `.git/hooks/pre-commit`. À partir de là, chaque `git commit` lance les hooks **uniquement sur les fichiers modifiés**.

## Usage quotidien

Rien de spécial. Au moment du `git commit`, le hook s'exécute :

```bash
git add .
git commit -m "feat: ..."
# pre-commit s'exécute automatiquement
```

Si un hook modifie un fichier (ex: ruff fix), le commit est interrompu. Il suffit de re-stager + re-commit :

```bash
git add .
git commit -m "feat: ..."
```

## Lancer manuellement

Pour vérifier tout le repo (utile avant un gros PR) :

```bash
pre-commit run --all-files
```

Pour un seul hook :

```bash
pre-commit run ruff --all-files
```

## Bypass (urgence uniquement)

En cas d'absolue nécessité (push de hotfix critique, hook qui flake) :

```bash
git commit --no-verify -m "hotfix: ..."
```

À utiliser avec parcimonie. La CI relancera de toute façon ruff et le build.

## Mise à jour des versions des hooks

```bash
pre-commit autoupdate
```

Puis commit le `.pre-commit-config.yaml` mis à jour.

## En cas de problème

- Hook trop lent ? Vérifier qu'il ne s'exécute pas sur tout le repo (option `files:` dans la config).
- Faux positifs sur gitleaks ? Ajouter `.gitleaksignore` ou utiliser `--no-verify` pour ce commit, puis ouvrir une issue.
- Erreur d'install ? Vérifier `python --version` (>= 3.9) et que `pre-commit` est dans le PATH.

## Liens

- Doc officielle : <https://pre-commit.com/>
- Lint Python (ruff) : <https://docs.astral.sh/ruff/>
- Détection de secrets (gitleaks) : <https://github.com/gitleaks/gitleaks>
