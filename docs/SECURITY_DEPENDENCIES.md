# Audit des dépendances (CVE)

Ce document explique comment fonctionne l'audit automatique des dépendances Python et Node, comment l'exécuter localement, et comment réagir lorsqu'une CVE est signalée.

## Vue d'ensemble

Deux jobs dédiés tournent dans la CI (`.github/workflows/backend-tests.yml`) :

| Job | Outil | Cible | Niveau |
|-----|-------|-------|--------|
| `audit-deps-python` | `pip-audit` | `requirements.txt` | toutes les CVE |
| `audit-deps-node` | `npm audit` | `landing/package-lock.json` (prod uniquement) | high+ |

Les deux jobs sont configurés en `continue-on-error: true` pour le moment, donc une CVE upstream **n'arrête pas** la CI. Ils servent de signal : on lit le rapport, on évalue l'exposition, on fixe quand un upgrade est disponible.

> Objectif à terme : retirer le `continue-on-error` une fois la baseline propre.

## Lancer en local

### Python

```bash
pip install pip-audit
pip-audit -r requirements.txt --desc
```

Options utiles :
- `--ignore-vuln GHSA-xxxx` : ignorer une CVE spécifique (à documenter ci-dessous).
- `--fix` : applique les upgrades suggérés (à valider à la main avant commit).
- `--strict` : exit 1 si une vulnérabilité est trouvée (utile pour CI bloquante).

### Node

```bash
cd landing
npm audit --audit-level=high --omit=dev
```

Pour appliquer automatiquement les fixes "safes" :

```bash
npm audit fix
```

`npm audit fix --force` peut casser des choses (changement de major). À éviter sauf si on contrôle la suite avec un build + tests.

## Procédure quand une CVE est signalée

1. Lire le rapport (titre, package, version installée vs version corrigée, sévérité).
2. Vérifier l'exposition réelle :
   - Le package est-il utilisé en prod (vs dev/test) ?
   - Le code chemin vulnérable est-il atteint dans notre app ?
   - Les inputs proviennent-ils d'un attaquant (réseau, user) ?
3. Décider :
   - **Fix immédiat** si CVE critique + exposition réelle → upgrade de la dep.
   - **Fix planifié** si CVE moyenne → ajouter une ligne dans `Suivi des CVE actives` ci-dessous.
   - **Ignorer** si non exposé (ex: CVE dans le parser TOML d'un outil dev) → documenter ici.

## Suivi des CVE actives (à mettre à jour)

| Date | Package | CVE | Sévérité | Statut | Décision |
|------|---------|-----|----------|--------|----------|
| _baseline_ | _vide pour le moment_ | _-_ | _-_ | _-_ | _Premier passage prévu lors du premier run CI_ |

## Pourquoi `--omit=dev` côté Node ?

Les dépendances de dev (ex: `vite`, `eslint`, plugins) génèrent énormément de bruit dans `npm audit`, rarement avec un impact réel en prod. On les ignore pour rester focalisé. À réévaluer si on déploie un environnement de dev publiquement (ce n'est pas le cas ici).

## Pourquoi pas Dependabot / Renovate ?

Pour le moment on reste sur un audit "passif" en CI. Quand le projet sera plus mature, on pourra :
- activer Dependabot pour des PR automatiques d'upgrade.
- ajouter un workflow scheduled `cron` pour re-run les audits chaque semaine.

Voir aussi : `docs/AUDIT_SECURITE_2026-05.md` (audit produit complet).
