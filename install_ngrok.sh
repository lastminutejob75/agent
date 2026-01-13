#!/bin/bash
# Script d'installation de ngrok (méthode manuelle)

echo "📥 Installation de ngrok"
echo "======================="
echo ""

# Vérifier si le fichier ngrok existe dans Downloads
if [ -f ~/Downloads/ngrok ]; then
    echo "✅ Fichier ngrok trouvé dans ~/Downloads"
    echo ""
    echo "Installation en cours..."
    sudo mv ~/Downloads/ngrok /usr/local/bin/
    sudo chmod +x /usr/local/bin/ngrok
    
    echo ""
    echo "✅ Installation terminée !"
    echo ""
    echo "Vérification :"
    ngrok version
    
    echo ""
    echo "🔐 Prochaine étape : Configurer votre token"
    echo "   1. Aller sur : https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   2. Copier votre token"
    echo "   3. Exécuter : ngrok config add-authtoken VOTRE_TOKEN"
    
elif [ -f ~/Downloads/ngrok.zip ]; then
    echo "📦 Fichier ngrok.zip trouvé dans ~/Downloads"
    echo ""
    echo "Extraction en cours..."
    cd ~/Downloads
    unzip -o ngrok.zip
    
    if [ -f ~/Downloads/ngrok ]; then
        echo "Installation en cours..."
        sudo mv ~/Downloads/ngrok /usr/local/bin/
        sudo chmod +x /usr/local/bin/ngrok
        
        echo ""
        echo "✅ Installation terminée !"
        echo ""
        echo "Vérification :"
        ngrok version
        
        echo ""
        echo "🔐 Prochaine étape : Configurer votre token"
        echo "   1. Aller sur : https://dashboard.ngrok.com/get-started/your-authtoken"
        echo "   2. Copier votre token"
        echo "   3. Exécuter : ngrok config add-authtoken VOTRE_TOKEN"
    else
        echo "❌ Erreur : ngrok n'a pas été extrait correctement"
        exit 1
    fi
else
    echo "❌ Fichier ngrok ou ngrok.zip non trouvé dans ~/Downloads"
    echo ""
    echo "📥 Pour installer ngrok :"
    echo "   1. Aller sur : https://ngrok.com/download"
    echo "   2. Télécharger 'Download for macOS'"
    echo "   3. Relancer ce script : ./install_ngrok.sh"
    exit 1
fi

