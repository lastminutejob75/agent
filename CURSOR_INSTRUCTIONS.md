# POUR CURSOR - Informations complètes sur les commits à appliquer

## 📋 Instructions pour appliquer les commits

Ce fichier contient les instructions pour appliquer les modifications depuis le dépôt `uwi-landing` vers le dépôt actuel `agent-accueil-pme`.

---

## 🔗 Dépôts

- **Dépôt source (landing)** : `https://github.com/lastminutejob75/uwi-landing.git`
- **Dépôt actuel (origin)** : `https://github.com/lastminutejob75/uwiagent.git`

---

## 📍 Localisation du patch

**Chemin complet** : `/home/user/UWI/uwi-landing.patch`

⚠️ **Note** : Ce chemin est sur un système Linux. Sur macOS, le patch peut être :
- Téléchargé depuis GitHub (une fois poussé)
- Dans `~/Downloads/uwi-landing.patch`
- Dans un autre emplacement spécifique

---

## 📚 Fichiers disponibles

- **uwi-landing.patch** (305 KB) - Patch git complet avec tout le code
- **CURSOR_INSTRUCTIONS.md** (6 KB) - Instructions complètes et détaillées
- **PATCH_INSTRUCTIONS.md** (3.4 KB) - Instructions alternatives
- **uwi-landing/** (dossier complet) - 31 fichiers sources prêts à copier

---

## 📝 Commits à appliquer

### Liste des commits (3 au total)

1. **f2f9a45** - Instructions pour Cursor
2. **e3ce764** - Patch file et instructions
3. **3d4377b** - UWI Landing page complète (31 fichiers)

### Voir les commits

```bash
# Voir les commits dans uwi-landing
git log landing/main --oneline

# Voir les différences
git diff landing/main..HEAD
```

---

## 🚀 Méthode recommandée : Appliquer le patch

### Option la plus simple (recommandée)

```bash
# 1. Lire les instructions complètes (ce fichier)
cat CURSOR_INSTRUCTIONS.md

# 2. Appliquer le patch
# Si le patch est dans le workspace :
git am uwi-landing.patch

# Si le patch est ailleurs, spécifier le chemin :
git am /chemin/vers/uwi-landing.patch

# 3. Push vers GitHub
git push origin main
```

### Script automatique

```bash
# Utiliser le script helper créé
./apply_uwi_landing_patch.sh uwi-landing.patch
# ou
./apply_uwi_landing_patch.sh /chemin/vers/uwi-landing.patch
```

---

## 🔄 Autres méthodes d'application

### Option 2 : Cherry-pick des commits

```bash
# Lister les commits à appliquer
git log landing/main --oneline

# Appliquer les commits spécifiques
git cherry-pick f2f9a45
git cherry-pick e3ce764
git cherry-pick 3d4377b
```

### Option 3 : Merge

```bash
# Fusionner la branche landing/main dans la branche actuelle
git merge landing/main
```

### Option 4 : Appliquer avec git apply

```bash
# Vérifier le patch d'abord
git apply --check uwi-landing.patch

# Appliquer le patch
git apply uwi-landing.patch

# Créer un commit manuellement
git add .
git commit -m "Apply uwi-landing patch"
```

---

## 📦 Fichiers concernés

Le patch contient **31 fichiers sources** pour la landing page UWI.

Liste complète à vérifier après application :

```bash
# Voir les fichiers modifiés après application
git status
git diff --name-only
```

---

## ⚠️ Notes importantes

- ✅ Vérifier les conflits avant d'appliquer : `git apply --check uwi-landing.patch`
- ✅ Tester après application
- ✅ Créer une branche de test si nécessaire : `git checkout -b test-uwi-landing`
- ✅ Le patch fait 305 KB, vérifier l'espace disque disponible
- ✅ Sauvegarder l'état actuel avant application : `git stash` ou créer une branche de sauvegarde

---

## ✅ Checklist de vérification

- [x] Dépôt uwi-landing ajouté comme remote (`landing`)
- [ ] Patch téléchargé/récupéré (`uwi-landing.patch`)
- [ ] Patch vérifié : `git apply --check uwi-landing.patch`
- [ ] Patch appliqué : `git am uwi-landing.patch`
- [ ] Tests effectués
- [ ] Conflits résolus (si applicable)
- [ ] Commit créé (si utilisé `git apply` au lieu de `git am`)
- [ ] Push vers GitHub : `git push origin main`

---

## 🐛 Dépannage

### Erreur : "Patch does not apply"

```bash
# Essayer avec résolution automatique
git apply --3way uwi-landing.patch

# Résoudre les conflits manuellement
git status
# Éditer les fichiers en conflit
git add .
git am --continue
```

### Erreur : "Patch format error"

```bash
# Vérifier le format du patch
head -20 uwi-landing.patch

# Essayer avec git apply au lieu de git am
git apply uwi-landing.patch
```

### Conflits de merge

```bash
# Voir les fichiers en conflit
git status

# Résoudre les conflits
# Éditer les fichiers marqués comme "both modified"
# Puis :
git add .
git am --continue
```

---

## 📞 Support

Si vous rencontrez des problèmes :
1. Vérifier que le patch est complet (305 KB)
2. Vérifier que vous êtes sur la bonne branche
3. Vérifier les logs : `git log --oneline -10`
4. Consulter les instructions alternatives dans `PATCH_INSTRUCTIONS.md`