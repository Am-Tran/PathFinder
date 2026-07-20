import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
from bs4 import BeautifulSoup
import time
import random
import os
import sys
from datetime import datetime
from supabase import create_client
from tqdm import tqdm
import pytz
import undetected_chromedriver as uc


# --- CONFIGURATION ---

table_choisie = "Data_Analyst_test"
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, load_data, upsert_data, verifier_pause_manuelle, verifier_blocage_et_pause

supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

timezone_fr = pytz.timezone('Europe/Paris')
date_actuelle = datetime.now(timezone_fr).date()
date_du_jour = pd.to_datetime(date_actuelle)

# --- CHARGEMENT ---

print("☁️ Récupération des offres actives depuis Supabase...")
filters_apec_update= {
    "source": "APEC",
    "statut": "Actif"
    }
df_base = load_data(supabase, table_name=table_choisie, limit=100, filters = filters_apec_update)
if df_base.empty:
        print("✅ Aucun ancien stock à vérifier.")
        exit()

df_base['Date_Publication'] = pd.to_datetime(df_base['Date_Publication'], errors='coerce')
df_a_verifier = df_base[    
    (df_base['Date_Publication'].dt.date != date_actuelle)
]
df_a_verifier = df_a_verifier.sort_values(by="Date_Publication", ascending=True)

print(f"🕵️ {len(df_a_verifier)} offres à vérifier dans la base de données.")
if len(df_a_verifier) == 0:
    print(" ⚠️ Il n'y a aucune offre active de l'APEC.")
    exit()

# Ordre des colonnes pour la réécriture propre
ordre_colonnes = ["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL", "Date_Publication", "Date_Expiration", "Statut"]


# --- ROBOT ---

# options = webdriver.ChromeOptions()
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless") # Décommentez pour exécuter sans fenêtre (plus rapide)
# driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
options = uc.ChromeOptions()
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox") # Sécurité requise sur les serveurs Linux
options.add_argument("--disable-dev-shm-usage") # Évite les crashs de mémoire (RAM)

driver = uc.Chrome(options=options,version_main=150)
driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
    'source': '''
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        })
    '''
})

def tuer_cookies(driver):
    try:
        WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))).click()
    except:
        try: driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        except: pass

print("\n🚀 Démarrage de la mise à jour des statuts...")

heure_demarrage = time.time()
LIMITE_TEMPS = (5 * 3600) + (30 * 60)
compteur_morts = 0
compteur_vivants = 0
compteur_doutes = 0
modifications = False
offres_a_mettre_a_jour = []
liste_offres = df_a_verifier.to_dict(orient='records')
# for offre in liste_offres:
#     for cle, valeur in offre.items():
#         if pd.isna(valeur):
#             offre[cle] = None
#         elif isinstance(valeur, pd.Timestamp):
#             # On convertit le Timestamp en texte "AAAA-MM-JJ"
#             offre[cle] = valeur.strftime("%Y-%m-%d")

try:
    for i, offre in enumerate(tqdm(liste_offres, desc="Vérification du statut des offres")):
        if time.time() - heure_demarrage > LIMITE_TEMPS:
            print("\n⏳ Limite de 5h30 atteinte ! Arrêt d'urgence pour sauvegarder...")
            break
        url = offre.get('URL')
        if not url:
                print(f"⚠️  Ligne {i} : Pas d'URL trouvée.")
                continue    
        
        try:          
            driver.get(url)        
               
            # Gestion cookies au tout début
            if i == 0: 
                tuer_cookies(driver)
                time.sleep(1)
            
            # Pause très courte (on veut juste voir si le texte charge)
            time.sleep(random.uniform(2, 4))
            verifier_blocage_et_pause(driver)
            verifier_pause_manuelle()
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')           
            
            # --- LOGIQUE DE DIAGNOSTIC ---
            div_officielle = soup.select_one(".details-offer-content")
            texte_page = soup.get_text(separator=" ", strip=True).lower()
            balise_morte = soup.find('apec-offre-unpublished-archived')

            # --- DÉCISION ---
            if "n'est plus en ligne" in texte_page or "n'est plus disponible" in texte_page or balise_morte:
                offres_a_mettre_a_jour.append({
                    "URL": url, 
                    "Date_Expiration": datetime.now().strftime("%Y-%m-%d"),
                    "Statut": "Archivé"
                })
                
                tqdm.write(f" ❌ EXPIRÉE : {url}")
                compteur_morts += 1
                
            elif div_officielle:
                # L'offre est vivante, on ne spamme pas la console pour aller plus vite
                compteur_vivants += 1           
                
            else:
                # Si on n'a NI l'un NI l'autre, c'est qu'on a probablement mangé un Captcha !
                tqdm.write(f" ⚠️ DOUTE (Page non reconnue) : {url}")
                compteur_doutes += 1
                
                # On limite le nombre de photos à 10 pour ne pas saturer ton disque dur
                if compteur_doutes <= 10:
                    nom_photo = f"debug_apec_doute_{compteur_doutes}.png"
                    driver.save_screenshot(nom_photo)
            
        except Exception as e:
                    print(f"⚠️ Erreur tech : {e}")

# --- GESTION DE L'ARRÊT MANUEL (CTRL+C) ---
except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel ! Sauvegarde de ce qui a été fait...")

# --- FERMETURE PROPRE ---
finally:
    # SAUVEGARDE FINALE     
    if offres_a_mettre_a_jour:
        filtre_anti_doublons = {}
        for offre in offres_a_mettre_a_jour:
            url_de_loffre = offre['URL']
            filtre_anti_doublons[url_de_loffre] = offre
        offres_uniques = list(filtre_anti_doublons.values())  
        print(f"\n📤 Envoi de {len(offres_uniques)} mises à jour vers Supabase...")
        upsert_data(supabase, table_choisie, offres_uniques)        
    else:
        print("\n✅ Aucune offre à mettre à jour.")
    driver.quit()
    
    print("\n🏁 Bilan Updater :")
    print(f"   ⚰️  Offres passées en 'Expirée' : {compteur_morts}")
    print(f"   ✅  Offres confirmées actives : {compteur_vivants}")  