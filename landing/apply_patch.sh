#!/bin/bash

# Script pour appliquer un patch Git
# Usage: ./apply_patch.sh /chemin/vers/patch.patch

set -e

PATCH_FILE="${1:-}"

if [ -z "$PATCH_FILE" ]; then
    echo "❌ Usage: $0 /chemin/vers/patch.patch"
    echo ""
    echo "Exemples :"
    echo "  $0 ~/Downloads/uwi-landing.patch"
    echo "  $0 /Users/actera/Documents/uwi-landing.patch"
    exit 1
fi

if [ ! -f "$PATCH_FILE" ]; then
    echo "❌ Fichier patch non trouvé : $PATCH_FILE"
    exit 1
fi

echo "📋 Application du patch : $PATCH_FILE"
echo ""

# Vérifier le patch d'abord
echo "🔍 Vérification du patch..."
if git apply --check "$PATCH_FILE" 2>&1; then
    echo "✅ Patch valide"
else
    echo "❌ Le patch contient des erreurs ou des conflits"
    echo ""
    echo "Voulez-vous quand même essayer de l'appliquer ? (y/N)"
    read -r response
    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        echo "❌ Application annulée"
        exit 1
    fi
fi

echo ""
echo "🚀 Application du patch..."

# Appliquer le patch
if git apply "$PATCH_FILE"; then
    echo ""
    echo "✅ Patch appliqué avec succès !"
    echo ""
    echo "📊 Statut Git :"
    git status --short
else
    echo ""
    echo "❌ Erreur lors de l'application du patch"
    echo ""
    echo "💡 Astuce : Utilisez 'git apply --3way' pour résoudre les conflits automatiquement"
    exit 1
fi
