@echo off
:: Passage de la console en UTF-8 pour bien lire les emojis de tes scripts
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo ===================================================
echo       LANCEMENT DU PIPELINE APEC (Séquentiel)
echo ===================================================
echo.

:: Se placer dans le bon dossier racine
cd /d D:\VSC\PathFinder

:: Activer l'environnement virtuel (.venv)
call .venv\Scripts\activate

:: Création sécurisée du dossier de logs s'il n'existe pas
if not exist "logs\apec" mkdir "logs\apec"

:: Lancer le Scraper
echo [ETAPE 1/2] Demarrage du Scraper...
:: Le symbole > ecrase le fichier. Le 2>&1 capture les erreurs et tqdm.
python -u scrapers\apec\scraper_apec.py > logs\apec\log_scraper.txt 2>&1
echo.

:: Lancer l'Updater
echo [ETAPE 2/2] Demarrage de l'Updater...
python -u scrapers\apec\updater_apec.py > logs\apec\logs_updater.txt 2>&1
echo.

:: Fermeture propre
deactivate
echo ===================================================
echo               PIPELINE TERMINE
echo ===================================================
pause