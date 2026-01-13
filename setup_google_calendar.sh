#!/bin/bash

# Script de setup Google Calendar
# Usage: ./setup_google_calendar.sh

set -e

echo "🚀 SETUP GOOGLE CALENDAR"
echo "========================"
echo ""

# 1. Installer dépendances
echo "📦 Installation des dépendances Google Calendar..."
pip install google-auth==2.27.0 \
            google-auth-oauthlib==1.2.0 \
            google-auth-httplib2==0.2.0 \
            google-api-python-client==2.110.0

echo "✅ Dépendances installées"
echo ""

# 2. Vérifier dossier credentials
if [ ! -d "credentials" ]; then
    echo "📁 Création du dossier credentials..."
    mkdir -p credentials
    echo "✅ Dossier créé"
else
    echo "✅ Dossier credentials existe déjà"
fi
echo ""

# 3. Vérifier fichier JSON
if [ -f "credentials/uwi-agent-service-account.json" ]; then
    echo "✅ Fichier credentials trouvé: credentials/uwi-agent-service-account.json"
else
    echo "⚠️  Fichier credentials manquant !"
    echo ""
    echo "📋 PROCHAINES ÉTAPES :"
    echo "1. Aller sur https://console.cloud.google.com"
    echo "2. Créer un projet 'UWI Agent IA'"
    echo "3. Activer Google Calendar API"
    echo "4. Créer un Service Account"
    echo "5. Télécharger le JSON et le placer dans:"
    echo "   credentials/uwi-agent-service-account.json"
    echo ""
fi

echo ""
echo "✅ Setup terminé !"
echo ""
echo "🧪 Pour tester :"
echo "   python backend/google_calendar.py"
echo ""
