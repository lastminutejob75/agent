#!/bin/bash

# Script pour télécharger le patch depuis GitHub uwi-landing
# Usage: ./download_patch_from_github.sh

set -e

echo "🔍 Récupération du patch depuis GitHub..."
echo ""

# Vérifier si le remote landing existe
if ! git remote | grep -q "landing"; then
    echo "❌ Remote 'landing' non trouvé"
    echo "Ajout du remote..."
    git remote add landing https://github.com/lastminutejob75/uwi-landing.git
fi

# Fetch depuis landing
echo "📥 Récupération des données depuis GitHub..."
git fetch landing

# Vérifier si le patch existe dans le dépôt
if git ls-tree -r landing/main --name-only | grep -q "uwi-landing.patch"; then
    echo "✅ Patch trouvé dans le dépôt GitHub"
    echo "📥 Téléchargement..."
    git show landing/main:uwi-landing.patch > uwi-landing.patch
    echo "✅ Patch téléchargé : uwi-landing.patch"
    ls -lh uwi-landing.patch
else
    echo "❌ Patch non trouvé dans le dépôt GitHub"
    echo ""
    echo "📋 Fichiers disponibles dans uwi-landing :"
    git ls-tree -r landing/main --name-only
    echo ""
    echo "💡 Le patch doit être poussé vers GitHub d'abord"
fi
