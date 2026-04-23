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

# --- CONFIGURATION ---

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, load_data

supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

timezone_fr = pytz.timezone('Europe/Paris')
date_actuelle = datetime.now(timezone_fr).date()
date_du_jour = pd.to_datetime(date_actuelle)

# --- CHARGEMENT ---

table_choisie = "Data_Analyst"
print("☁️ Récupération des offres actives depuis Supabase...")
df_base = load_data(supabase, table_name=table_choisie)

df_a_verifier = df_base[
    (df_base['Source'] == 'APEC') & 
    (df_base['Date_Expiration'].isna()) &
    (df_base['Date_Publication'] != date_du_jour)
]

print(f"🕵️ {len(df_a_verifier)} offres à vérifier dans la base de données.")
if len(df_a_verifier) == 0:
    print(" ⚠️ Il n'y a aucune offre active de l'APEC.")
    exit()

# Ordre des colonnes pour la réécriture propre
ordre_colonnes = ["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL", "Date", "Date_Expiration"]


# --- ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--headless") # Décommentez pour exécuter sans fenêtre (plus rapide)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def tuer_cookies(driver):
    try:
        WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))).click()
    except:
        try: driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        except: pass

print("\n🚀 Démarrage de la mise à jour des statuts...")

compteur_morts = 0
compteur_vivants = 0
compteur_doutes = 0
modifications = False
offres_a_mettre_a_jour = []
liste_offres = df_a_verifier.to_dict(orient='records')
for offre in liste_offres:
    for cle, valeur in offre.items():
        if pd.isna(valeur):
            offre[cle] = None
        elif isinstance(valeur, pd.Timestamp):
            # On convertit le Timestamp en texte "AAAA-MM-JJ"
            offre[cle] = valeur.strftime("%Y-%m-%d")

try:
    for i, offre in enumerate(tqdm(liste_offres, desc="Vérification du statut des offres")):
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
            time.sleep(random.uniform(3, 5))
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')           
            
            # --- LOGIQUE DE DIAGNOSTIC ---
            balise_morte = soup.find("apec-offre-unpublished-archived")            
            balise_vivante_class = soup.find(class_="card_offer__text")
            balise_vivante_tag = soup.find(["apec-detail-emploi", "apec-poste-information", "apec_offre_metadata"])

            # --- DÉCISION ---
            if balise_morte:
                date_jour = datetime.now().strftime("%Y-%m-%d") 
                offre['Date_Expiration'] = date_jour
                offres_a_mettre_a_jour.append(offre) 
                
                print(f" ❌ EXPIRÉE (Balise 'archived' détectée)")
                compteur_morts += 1
                
            elif balise_vivante_class or balise_vivante_tag:
                print(" ✅ VIVANTE (Structure d'offre détectée)")
                compteur_vivants += 1           
                
            else:
                # Si on n'a NI l'un NI l'autre, c'est qu'on a probablement mangé un Captcha !
                print(" ⚠️ DOUTE (Page non reconnue -> Captcha ou blocage ?)")
                compteur_doutes += 1
                nom_photo = f"debug_apec_{i}.png"
                driver.save_screenshot(nom_photo)
                print(f"   📸 Photo prise : {nom_photo}")
                time.sleep(5)
            
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
        
        # On envoie par paquets de 1000 (limite Supabase)
        for i in range(0, len(offres_uniques), 1000):
            batch = offres_uniques[i : i + 1000]
            supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
        print("✅ Base de données synchronisée !")
    else:
        print("\n✅ Aucune offre à mettre à jour.")
    driver.quit()
    
    print("\n🏁 Bilan Updater :")
    print(f"   ⚰️  Offres passées en 'Expirée' : {compteur_morts}")
    print(f"   ✅  Offres confirmées actives : {compteur_vivants}")  