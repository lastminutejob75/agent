# 📅 Guide d'intégration Google Calendar

## 🎯 JOUR 1 : SETUP GOOGLE CALENDAR API (4H)

### Étape 1 : Créer projet Google Cloud (15 min)

1. Aller sur : https://console.cloud.google.com
2. Créer nouveau projet
   - Nom : **"UWI Agent IA"**
3. Activer Google Calendar API
   - → **API & Services** → **Library**
   - → Chercher **"Google Calendar API"**
   - → **Enable**

---

### Étape 2 : Créer Service Account (15 min)

1. **API & Services** → **Credentials**
2. **Create Credentials** → **Service Account**
3. Nom : **"uwi-calendar-service"**
4. Role : **Editor**
5. **Done**

6. Cliquer sur le service account créé
7. **Keys** → **Add Key** → **Create New Key**
8. Type : **JSON**
9. **Download**

📁 Tu obtiens un fichier : `uwi-agent-xxxx.json`

⚠️ **Garde ce fichier précieusement !** C'est les credentials.

---

### Étape 3 : Partager Calendar de test (5 min)

1. Ouvre **Google Calendar** (ton compte perso)
2. Créer un nouveau calendrier **"Test UWI"**
3. **Settings** → **Partager avec des personnes**
4. Ajouter email du service account :
   ```
   uwi-calendar-service@uwi-agent-xxxx.iam.gserviceaccount.com
   ```
5. Permissions : **"Apporter des modifications aux événements"**
6. **Save**

7. Copie l'ID du calendar :
   - **Settings** → **"Test UWI"** → **Integrate Calendar**
   - **Calendar ID** : `test-uwi-xxx@group.calendar.google.com`

8. Mettre à jour `backend/config.py` :
   ```python
   GOOGLE_CALENDAR_ID = "test-uwi-xxx@group.calendar.google.com"
   ```

---

### Étape 4 : Installer dépendances Python (2 min)

```bash
# Option 1 : Script automatique
./setup_google_calendar.sh

# Option 2 : Manuel
pip install google-auth==2.27.0 \
            google-auth-oauthlib==1.2.0 \
            google-auth-httplib2==0.2.0 \
            google-api-python-client==2.110.0
```

---

### Étape 5 : Préparer les credentials

```bash
# 1. Créer dossier credentials (déjà fait)
mkdir -p credentials

# 2. Mettre le fichier JSON téléchargé dedans
mv ~/Downloads/uwi-agent-xxxx.json credentials/uwi-agent-service-account.json

# 3. Vérifier que .gitignore contient credentials/
cat .gitignore | grep credentials
```

---

### Étape 6 : Tester l'intégration (30 min)

1. **Mettre à jour le Calendar ID dans le test** :
   ```python
   # backend/google_calendar.py
   CALENDAR_ID = "test-uwi-xxx@group.calendar.google.com"  # ← Ton ID
   ```

2. **Lancer le test** :
   ```bash
   python backend/google_calendar.py
   ```

**Résultat attendu :**
```
📅 Créneaux disponibles demain:
1. Mercredi 15 janvier à 09h00
2. Mercredi 15 janvier à 09h15
3. Mercredi 15 janvier à 09h30
4. Mercredi 15 janvier à 09h45
5. Mercredi 15 janvier à 10h00

✅ RDV créé: abc123xyz
   Mercredi 15 janvier à 09h00

✅ RDV annulé
```

✅ **Si ça marche → Jour 1 terminé !**

---

## 📊 RÉCAPITULATIF JOUR 1

- [ ] Projet Google Cloud créé
- [ ] Google Calendar API activée
- [ ] Service Account créé
- [ ] Credentials téléchargés
- [ ] Calendar de test partagé
- [ ] Calendar ID copié et configuré dans `backend/config.py`
- [ ] Dépendances installées
- [ ] Code intégration écrit
- [ ] Tests passent

---

## 🔧 FICHIERS CRÉÉS

- ✅ `backend/google_calendar.py` - Service Google Calendar
- ✅ `credentials/` - Dossier pour les credentials (dans .gitignore)
- ✅ `setup_google_calendar.sh` - Script d'installation
- ✅ `GOOGLE_CALENDAR_SETUP.md` - Ce guide

---

## ⚠️ IMPORTANT

1. **Ne jamais commiter les credentials** : Le dossier `credentials/` est dans `.gitignore`
2. **Calendar ID** : À mettre à jour dans `backend/config.py` après création
3. **Service Account Email** : À partager avec le calendar avec permissions "Editor"

---

## 🐛 DÉPANNAGE

### Erreur : "FileNotFoundError: credentials/uwi-agent-service-account.json"
→ Vérifier que le fichier JSON est bien dans `credentials/` avec le bon nom

### Erreur : "403 Forbidden" ou "Calendar not found"
→ Vérifier que le Service Account a bien accès au calendar (partage)

### Erreur : "Invalid credentials"
→ Vérifier que le fichier JSON est valide et non corrompu

---

## 📚 RESSOURCES

- [Google Calendar API Documentation](https://developers.google.com/calendar/api/v3/reference)
- [Service Account Setup](https://cloud.google.com/iam/docs/service-accounts)
- [Python Client Library](https://github.com/googleapis/google-api-python-client)
