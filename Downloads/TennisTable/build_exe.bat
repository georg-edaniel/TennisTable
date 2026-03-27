@echo off
echo =====================================================
echo  TableTennis System v3.0 - Build
echo =====================================================

REM Vérifier que config.json existe
if not exist config.json (
    echo ERREUR: config.json introuvable dans le repertoire courant.
    echo Veuillez creer config.json avant de builder.
    exit /b 1
)

echo Installation des dependances...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR: Installation des dependances echouee.
    exit /b 1
)

echo Construction de l'executable avec TableTennisSystem.spec...
pyinstaller --clean TableTennisSystem.spec
if errorlevel 1 (
    echo ERREUR: Build PyInstaller echoue.
    exit /b 1
)

echo.
echo Copie de config.json dans dist\ pour les overrides operateur...
copy /Y config.json dist\config.json

echo.
echo =====================================================
echo  Build termine avec succes !
echo  Executable : dist\TableTennisSystem.exe
echo  Config     : dist\config.json  (editez ce fichier
echo               pour surcharger la config embarquee)
echo =====================================================
echo.
pause
