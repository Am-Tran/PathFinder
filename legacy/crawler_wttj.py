from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import pandas as pd
import os
import sys
from datetime import datetime

# --- 1. CONFIGURATION DES CHEMINS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
CSV_PATH = os.path.join(project_root, "data", "raw", "offres_wttj_url.csv")

if project_root not in sys.path:
    sys.path.append(project_root)
from utils import sauvegarde_securisee

# --- 2. CHARGEMENT DE L'HISTORIQUE ---
urls_vues = set()
data_existante = []

if os.path.exists(CSV_PATH):
    print(f"📂 Chargement de l'historique : {CSV_PATH}")
    try:
        df_old = pd.read_csv(CSV_PATH, dtype=str)
        # On remplit la mémoire avec les URLs existantes
        urls_vues = set(df_old['URL'].tolist())
        data_existante = df_old.to_dict('records')
        print(f"🧠 Mémoire chargée : {len(urls_vues)} offres déjà connues.")
    except Exception as e:
        print(f"⚠️ Erreur lecture fichier : {e}. On repart de zéro.")
else:
    print("✨ Aucun historique trouvé. On commence à zéro.")

# --- CONFIGURATION ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
#options.add_argument("--headless")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)

# Variables globales
page_number = 1
nouvelles_offres = []
continuing = True

print("🐢 Mode 'Tortue' activé : On va prendre notre temps pour ne pas se faire repérer.")

# --- BOUCLE PRINCIPALE ---
while continuing:
    
    # 1. Construction de l'URL dynamique avec le numéro de page
    url = f"https://www.welcometothejungle.com/fr/jobs?query=data%20analyst&page={page_number}&refinementList%5Boffices.country_code%5D%5B%5D=FR"
    
    print(f"\n📄 Traitement de la page {page_number}...")
    driver.get(url)
    
    # 2. Pause aléatoire "Humaine" (Entre 5 et 10 secondes au début)
    temps_pause = random.uniform(5, 8)
    time.sleep(temps_pause)
    
    # 3. Scrolling progressif (Pour charger les images et le bas de liste)
    # On scrolle 4 fois avec des petites pauses
    for _ in range(4):
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(random.uniform(1.0, 2.0))
    
    # 4. Extraction
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    liens = soup.find_all('a')
    
    nb_offres_page = 0
    
    for lien in liens:
        href = lien.get('href')
        texte = lien.get_text()
        
        # Le filtre
        if href and '/companies/' in href and '/jobs/' in href and len(texte.strip()) > 0:
            full_url = "https://www.welcometothejungle.com" + href            
            
            if full_url not in urls_vues:
                titre = " ".join(texte.split())
                nouvelles_offres.append({
                    "Titre": titre,
                    "URL": full_url,
                    "Page": page_number,
                    "Date_Scrap": datetime.now().strftime("%Y-%m-%d"),
                    "Plateforme": "WTTJ"
                })
                urls_vues.add(full_url)
                nb_offres_page += 1
                # On print un petit point pour dire "je suis vivant" sans spammer
                print("+", end="", flush=True)
            else:
                print(".", end="", flush=True)

    print(f"\n✅ Page {page_number} terminée : {nb_offres_page} nouvelles offres récupérées.")
    
    # 5. Condition d'arrêt
    # Si on trouve 0 nouvelle offre sur une page, c'est qu'on est arrivé au bout
    if nb_offres_page == 0:
        print("🛑 Plus aucune offre trouvée. Fin du scraping.")
        continuing = False
    else:
        # On prépare la page suivante
        page_number += 1
        
        # 6. PAUSE ENTRE LES PAGES        
        wait_time = random.uniform(8, 15)
        print(f"☕ Pause café de {wait_time:.1f} secondes avant la suite...")
        time.sleep(wait_time)

# --- SAUVEGARDE FINALE ---
driver.quit()

print(f"\n Bilan Total : {len(nouvelles_offres)} offres récupérées sur {page_number} pages.")

if len(nouvelles_offres) > 0:
    df_new = pd.DataFrame(nouvelles_offres)    
    if data_existante:
                df_old = pd.DataFrame(data_existante)                
                df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new
        
    # Sauvegarde
    # On s'assure que le dossier existe
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    
    #df_final.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    sauvegarde_securisee(df_final, CSV_PATH)
    print(f"✅ Base mise à jour avec succès : {len(df_final)} offres au total.")
    print(f"📁 Fichier : {CSV_PATH}")
    print("Fin du crawler_wttj ==> Lancer le scraper_wttj")
            
else:
    print("🤷 Aucune nouvelle offre à sauvegarder.")