#!/usr/bin/env bash
# TableTennis System v3.1 - Build (Linux / macOS)
set -euo pipefail

echo "====================================================="
echo " TableTennis System v3.1 - Build (Linux / macOS)"
echo "====================================================="

# Vérifier que config.json existe
if [ ! -f config.json ]; then
    echo "ERREUR: config.json introuvable dans le répertoire courant."
    echo "Veuillez créer config.json avant de builder."
    exit 1
fi

echo "Installation des dépendances..."
pip install -r requirements.txt

echo "Construction de l'exécutable avec TableTennisSystem.spec..."
pyinstaller --clean TableTennisSystem.spec

echo ""
echo "Copie de config.json dans dist/ pour les overrides opérateur..."
cp config.json dist/config.json

# Sur macOS : s'assurer que l'exe est exécutable
chmod +x dist/TableTennisSystem 2>/dev/null || true

echo ""
echo "====================================================="
echo " Build terminé !"
echo " Exécutable : dist/TableTennisSystem"
echo " Config     : dist/config.json  (éditez ce fichier"
echo "              pour surcharger la config embarquée)"
echo "====================================================="
