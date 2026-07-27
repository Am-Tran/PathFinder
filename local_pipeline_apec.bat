@echo off
:: Passage de la console en UTF-8 pour bien lire les emojis de tes scripts
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo ===================================================
echo       LANCEMENT DU PIPELINE APEC (Parallele)
echo ===================================================
echo.

:: Se placer dans le bon dossier racine
cd /d D:\VSC\PathFinder

:: Activer l'environnement virtuel (.venv)
call .venv\Scripts\activate

:: Creation securisee du dossier de logs s'il n'existe pas
if not exist "logs\apec" mkdir "logs\apec"

:: Lancement avec decalage pour eviter la collision Chrome
echo Lancement du Scraper...
start "APEC_Scraper" cmd /c "python -u scrapers\apec\scraper_apec.py > logs\apec\log_scraper.txt 2>&1"

echo Decalage de 15 secondes pour securiser le moteur Chrome...
timeout /t 15 /nobreak > nul

echo Lancement de l'Updater...
start "APEC_Updater" cmd /c "python -u scrapers\apec\updater_apec.py > logs\apec\logs_updater.txt 2>&1"

echo.
echo Les deux robots ont ete lances !
echo Ils tournent en arriere-plan.
echo Tu peux suivre leur avancee en ouvrant les fichiers .txt dans logs\apec\
echo.
echo ===================================================
echo Termine ! Appuie sur une touche pour fermer CETTE fenetre.
pause > nul