import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import os
from datetime import datetime

# --- CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
CSV_PATH = os.path.join(project_root, "data", "enriched", "offres_wttj_full.csv")

# Ordre des colonnes
ordre_colonnes = ["Titre", "Entreprise", "Ville", "Experience_Salaire_Infos", "Description_Complete", "URL", "Date_Publication", "Date_Expiration"]

if not os.path.exists(CSV_PATH):
    print("❌ Pas de fichier historique trouvé.")
    exit()

print("🔄 Chargement de la base de données...")
# Moteur python pour tolérance aux erreurs
try:
    df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', dtype=str, engine='python')
except:
    df = pd.read_csv(CSV_PATH, encoding='utf-8', dtype=str, engine='python')

if 'Date_Expiration' not in df.columns:
    df['Date_Expiration'] = None

# --- FILTRAGE : On ne vérifie que ce qui est vivant ---
mask_a_verifier = df['Date_Expiration'].isna() | (df['Date_Expiration'] == "") | (df['Date_Expiration'].str.lower() == "nan") | (df['Date_Expiration'] == "Non spécifié")
indices_a_verifier = df[mask_a_verifier].index

print(f"📊 Total offres : {len(df)}")
print(f"🕵️  Offres actives à vérifier : {len(indices_a_verifier)}")

if len(indices_a_verifier) == 0:
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
modifications = False

try:
    for i, idx in enumerate(indices_a_verifier):
        url_cible = str(df.at[idx, 'URL'])
        titre = str(df.at[idx, 'Titre'])
        
        print(f"[{i+1}/{len(indices_a_verifier)}] {titre[:30]}...", end=" ")
        
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
                date_jour = datetime.now().strftime("%Y-%m-%d")
                df.at[idx, 'Date_Expiration'] = date_jour
                print(f"❌ EXPIRÉE ({raison})")
                compteur_morts += 1
                modifications = True
            else:
                print("✅ VIVANTE")
                compteur_vivants += 1

            # Sauvegarde intermédiaire
            if modifications and i > 0 and i % 10 == 0:
                df.reindex(columns=ordre_colonnes).to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
                modifications = False
                
        except Exception as e:
            print(f"⚠️ Bug : {e}")

except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel !")

finally:
    df = df.reindex(columns=ordre_colonnes)
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    driver.quit()
    print("\n🏁 Bilan :")
    print(f"   ⚰️  Expirées : {compteur_morts}")
    print(f"   ✅  Actives : {compteur_vivants}")
    print("Fin du updater_wttj ==> Lancer le clean_wttj")