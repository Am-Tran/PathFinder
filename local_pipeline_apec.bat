@echo off
:: Passage de la console en UTF-8 pour bien lire les emojis de tes scripts
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo ===================================================
echo       LANCEMENT DU PIPELINE APEC (Séquentiel)
echo ===================================================
echo.

:: 1. Se placer dans le bon dossier racine
cd /d D:\VSC\PathFinder

:: 2. Activer l'environnement virtuel (.venv)
call .venv\Scripts\activate

:: 3. Lancer le Scraper
echo [ETAPE 1/2] Demarrage du Scraper...
:: Le symbole > ecrase le fichier. Le 2>&1 capture les erreurs et tqdm.
python scrapers\apec\scraper_apec.py > scrapers\apec\log_scraper.txt 2>&1
echo.

:: 4. Lancer l'Updater
echo [ETAPE 2/2] Demarrage de l'Updater...
python scrapers\apec\updater_apec.py > scrapers\apec\log_updater.txt 2>&1
echo.

:: 5. Fermeture propre
deactivate
echo ===================================================
echo               PIPELINE TERMINE
echo ===================================================
exit /b 0