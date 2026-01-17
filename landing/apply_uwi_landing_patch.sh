#!/bin/bash

# Script pour appliquer le patch uwi-landing
# Usage: ./apply_uwi_landing_patch.sh [chemin_vers_patch]

set -e

PATCH_FILE="${1:-uwi-landing.patch}"

echo "🚀 APPLICATION DU PATCH UWI-LANDING"
echo "===================================="
echo ""

# Vérifier si le fichier patch existe
if [ ! -f "$PATCH_FILE" ]; then
    echo "❌ Fichier patch non trouvé : $PATCH_FILE"
    echo ""
    echo "📋 OPTIONS :"
    echo "1. Télécharger depuis GitHub (si disponible)"
    echo "2. Spécifier le chemin complet du patch"
    echo ""
    echo "Exemple :"
    echo "  $0 /chemin/vers/uwi-landing.patch"
    echo "  $0 ~/Downloads/uwi-landing.patch"
    exit 1
fi

echo "📁 Fichier patch : $PATCH_FILE"
echo "📊 Taille : $(du -h "$PATCH_FILE" | cut -f1)"
echo ""

# Vérifier le statut Git
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Ce n'est pas un dépôt Git"
    exit 1
fi

# Vérifier s'il y a des modifications non commitées
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  ATTENTION : Modifications non commitées détectées"
    echo ""
    git status --short
    echo ""
    echo "Voulez-vous continuer ? (y/N)"
    read -r response
    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        echo "❌ Application annulée"
        exit 1
    fi
fi

# Vérifier le patch
echo "🔍 Vérification du patch..."
if git apply --check "$PATCH_FILE" 2>&1; then
    echo "✅ Patch valide"
else
    echo "⚠️  Le patch contient des erreurs ou des conflits potentiels"
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

# Essayer avec git am d'abord (préserve les métadonnées)
if git am "$PATCH_FILE" 2>&1; then
    echo ""
    echo "✅ Patch appliqué avec succès avec 'git am' !"
    echo ""
    echo "📊 Commits appliqués :"
    git log --oneline -3
    echo ""
    echo "📁 Statut Git :"
    git status --short
else
    echo ""
    echo "⚠️  'git am' a échoué, tentative avec 'git apply'..."
    
    # Fallback sur git apply
    if git apply "$PATCH_FILE" 2>&1; then
        echo ""
        echo "✅ Patch appliqué avec succès avec 'git apply' !"
        echo ""
        echo "📁 Statut Git :"
        git status --short
        echo ""
        echo "⚠️  Note : Les métadonnées de commit ne sont pas préservées"
        echo "   Vous devrez créer un commit manuellement si nécessaire"
    else
        echo ""
        echo "❌ Erreur lors de l'application du patch"
        echo ""
        echo "💡 Suggestions :"
        echo "1. Vérifier les conflits : git apply --check $PATCH_FILE"
        echo "2. Appliquer avec résolution automatique : git apply --3way $PATCH_FILE"
        echo "3. Voir les différences : git diff"
        exit 1
    fi
fi

echo ""
echo "✅ TERMINÉ !"
echo ""
echo "📋 PROCHAINES ÉTAPES :"
echo "1. Vérifier les modifications : git status"
echo "2. Tester l'application"
echo "3. Si tout est OK, commit et push :"
echo "   git add ."
echo "   git commit -m 'Apply uwi-landing patch'"
echo "   git push origin main"
