from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import pandas as pd

# --- CONFIGURATION ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)

# Variables globales
page_number = 1
data_global = []
urls_vues = set()
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
            titre = " ".join(texte.split())
            
            if full_url not in urls_vues:
                data_global.append({
                    "Titre": titre,
                    "URL": full_url,
                    "Page": page_number,
                    "Plateforme": "WTTJ"
                })
                urls_vues.add(full_url)
                nb_offres_page += 1
                # On print un petit point pour dire "je suis vivant" sans spammer
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
        
        # 6. GRANDE PAUSE ENTRE LES PAGES
        # C'est ici qu'on est "généreux". On attend entre 8 et 15 secondes avant de changer de page.
        # Ça laisse le temps au serveur d'oublier notre précédente requête.
        wait_time = random.uniform(8, 15)
        print(f"☕ Pause café de {wait_time:.1f} secondes avant la suite...")
        time.sleep(wait_time)

# --- SAUVEGARDE FINALE ---
driver.quit()

print(f"\n Bilan Total : {len(data_global)} offres récupérées sur {page_number} pages.")

if len(data_global) > 0:
    df = pd.DataFrame(data_global)
    nom_fichier = "offres_wttj_complet.csv"
    df.to_csv(nom_fichier, index=False, encoding='utf-8')
    print(f" Sauvegardé dans {nom_fichier}")
else:
    print("❌ Rien trouvé.")