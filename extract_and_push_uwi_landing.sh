#!/bin/bash

# Script pour extraire l'archive uwi-landing-source.tar.gz et pousser vers GitHub
# Usage: ./extract_and_push_uwi_landing.sh [chemin_vers_archive]

set -e

ARCHIVE_FILE="${1:-uwi-landing-source.tar.gz}"
REPO_DIR="uwi-landing"
REPO_URL="https://github.com/lastminutejob75/uwi-landing.git"

echo "🚀 EXTRACTION ET PUSH UWI-LANDING"
echo "=================================="
echo ""

# Vérifier si l'archive existe
if [ ! -f "$ARCHIVE_FILE" ]; then
    echo "❌ Archive non trouvée : $ARCHIVE_FILE"
    echo ""
    echo "📋 EMPLACEMENTS POSSIBLES :"
    echo "1. ~/Downloads/uwi-landing-source.tar.gz"
    echo "2. /tmp/uwi-landing-source.tar.gz"
    echo "3. Chemin personnalisé (passer en argument)"
    echo ""
    echo "💡 Si l'archive est sur le système Linux :"
    echo "   scp /home/user/UWI/uwi-landing-source.tar.gz ~/Downloads/"
    echo ""
    echo "Usage :"
    echo "  $0 ~/Downloads/uwi-landing-source.tar.gz"
    echo "  $0 /chemin/vers/uwi-landing-source.tar.gz"
    exit 1
fi

echo "📁 Archive : $ARCHIVE_FILE"
echo "📊 Taille : $(du -h "$ARCHIVE_FILE" | cut -f1)"
echo ""

# Vérifier/cloner le dépôt uwi-landing
if [ -d "$REPO_DIR" ]; then
    echo "📂 Dépôt $REPO_DIR existe déjà"
    cd "$REPO_DIR"
    
    # Vérifier si c'est un dépôt Git valide
    if [ ! -d ".git" ]; then
        echo "⚠️  Le dossier existe mais n'est pas un dépôt Git"
        echo "Initialisation..."
        git init
        git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
    else
        echo "🔄 Mise à jour depuis GitHub..."
        git fetch origin || true
        git pull origin main || true
    fi
else
    echo "📥 Clonage du dépôt uwi-landing..."
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

echo ""
echo "📦 Extraction de l'archive..."
ARCHIVE_PATH="$(cd "$(dirname "$ARCHIVE_FILE")" && pwd)/$(basename "$ARCHIVE_FILE")"
tar -xzf "$ARCHIVE_PATH"

echo ""
echo "📋 Contenu extrait :"
ls -la | head -20

echo ""
echo "📦 Installation des dépendances npm..."
if [ -f "package.json" ]; then
    npm install
    echo "✅ Dépendances installées"
else
    echo "⚠️  package.json non trouvé, passage de l'installation npm"
fi

echo ""
echo "📊 Statut Git avant commit :"
git status --short

echo ""
echo "📝 Ajout des fichiers..."
git add .

echo ""
echo "💾 Création du commit..."
git commit -m "feat: Add UWI Landing page" || {
    echo "⚠️  Aucune modification à commiter (peut-être déjà commitée)"
}

echo ""
echo "🚀 Push vers GitHub..."
git push origin main || {
    echo "⚠️  Erreur lors du push"
    echo "💡 Vérifiez vos permissions GitHub et votre authentification"
    echo ""
    echo "Pour pousser manuellement :"
    echo "  cd $REPO_DIR"
    echo "  git push origin main"
    exit 1
}

echo ""
echo "✅ TERMINÉ !"
echo ""
echo "📋 RÉSUMÉ :"
echo "- Archive extraite : $ARCHIVE_FILE"
echo "- Dépôt : $REPO_DIR"
echo "- Commit : feat: Add UWI Landing page"
echo "- Push : origin main"
echo ""
echo "🔗 Dépôt GitHub : $REPO_URL"
