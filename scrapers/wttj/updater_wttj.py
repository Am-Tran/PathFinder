import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import os
import sys
from datetime import datetime
import pytz
from supabase import create_client
from tqdm import tqdm

# --- CONFIGURATION ---

table_choisie = "Data_Analyst"
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

print("☁️ Récupération des offres actives depuis Supabase...")
filters_wttj_update= {
    "source": "Welcome to the Jungle",
    "statut": "Actif",
    "only_active": True
    }
df_base = load_data(supabase, table_name=table_choisie, limit=None, filters = filters_wttj_update)   

df_a_verifier = df_base[
    # (df_base['Source'] == 'Welcome to the Jungle') & 
    #(df_base['Date_Expiration'].isna()) &
    (df_base['Date_Publication'].dt.date != date_actuelle)
]

print(f"🕵️ {len(df_a_verifier)} offres à vérifier dans la base de données.")
if len(df_a_verifier) == 0:
    print(" ⚠️ Il n'y a aucune offre active de l'APEC.")
    exit()

print(f"🕵️  Offres actives à vérifier : {len(df_a_verifier)}")

if len(df_a_verifier) == 0:
    print("✅ Tout est à jour.")
    exit()

# --- ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--headless") 
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)

print("\n🚀 Démarrage de la mise à jour WTTJ...")

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
        url_cible = offre.get('URL')
        if not url_cible:
                print(f"⚠️  Ligne {i} : Pas d'URL trouvée.")
                continue    
        
        try:          
            driver.get(url_cible)      
            time.sleep(random.uniform(3, 5))
            
            url_actuelle = driver.current_url
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            # On récupère tout le texte visible en minuscules
            text_page = soup.get_text(" ", strip=True).lower()
            
            est_morte = False
            raison = ""

            # --- PREUVE 1 : LA REDIRECTION (Toujours le signe n°1) ---
            # Si on voulait voir un job et qu'on est sur la page vitrine de l'entreprise
            if len(url_actuelle) < len(url_cible) - 15 and "jobs" not in url_actuelle:
                est_morte = True
                raison = "Redirection auto"

            # --- PREUVE 2 : LE MESSAGE SPÉCIFIQUE (Votre découverte) ---
            # On cherche exactement le texte que vous avez trouvé dans le <span>
            # On gère les deux types d'apostrophes (courbe ’ et droite ')
            elif "cette offre n’est plus disponible" in text_page:
                est_morte = True
                raison = "Message 'Plus disponible'"
            elif "cette offre n'est plus disponible" in text_page:
                est_morte = True
                raison = "Message 'Plus disponible'"
                
            # --- PREUVE 3 : LES ARCHIVES ---
            elif "archivée" in text_page or "archived" in text_page:
                est_morte = True
                raison = "Archivée"
            elif "page introuvable" in text_page or "404" in driver.title:
                est_morte = True
                raison = "Erreur 404"

            # --- ACTION ---
            if est_morte:
                offres_a_mettre_a_jour.append({
                    "URL": url_cible,
                    "Date_Expiration": date_actuelle.strftime("%Y-%m-%d"),
                    "Statut": "Archivé"
                })
                print(f" ❌ EXPIRÉE ({raison})")
                compteur_morts += 1
                modifications = True             
                         
            else:
                print("✅ VIVANTE")
                compteur_vivants += 1

                
        except Exception as e:
            print(f"⚠️ Bug : {e}")

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