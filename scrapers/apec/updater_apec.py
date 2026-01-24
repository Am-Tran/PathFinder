import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import random
import os
from datetime import datetime

# --- CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
CSV_PATH = os.path.join(project_root, "data", "enriched", "offres_apec_full.csv")

# Ordre des colonnes pour la réécriture propre
ORDRE_COLONNES = ["Date", "Date_Expiration", "Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL"]

if not os.path.exists(CSV_PATH):
    print("❌ Pas de fichier historique trouvé. Lancez d'abord le scraper.")
    exit()

print("🔄 Chargement de la base de données...")
# On charge tout en string pour éviter les conflits de types (NaN vs texte)
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', dtype=str)

# --- FILTRAGE INTELLIGENT ---
# On ne vérifie QUE les lignes où Date_Expiration est vide (ou NaN)
# Critère : est vide (NaN) OU est une chaine vide "" OU est la string literal "nan"
mask_a_verifier = df['Date_Expiration'].isna() | (df['Date_Expiration'] == "") | (df['Date_Expiration'] == "nan")
indices_a_verifier = df[mask_a_verifier].index

print(f"📊 Total offres : {len(df)}")
print(f"🕵️  Offres actives à vérifier : {len(indices_a_verifier)}")

if len(indices_a_verifier) == 0:
    print("✅ Toutes vos offres sont déjà marquées expirées. Rien à faire.")
    exit()

# --- ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless") # Décommentez pour exécuter sans fenêtre (plus rapide)
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
modifications = False

try:
    for i, idx in enumerate(indices_a_verifier):
        url = df.at[idx, 'URL']
        titre = str(df.at[idx, 'Titre'])
        
        # Affichage progression
        print(f"[{i+1}/{len(indices_a_verifier)}] {titre[:30]}...", end=" ")
        
        try:
            driver.get(url)
            
            # Gestion cookies au tout début
            if i == 0: 
                tuer_cookies(driver)
                time.sleep(1)
            
            # Pause très courte (on veut juste voir si le texte charge)
            time.sleep(random.uniform(1.5, 2.5))
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            text_page = soup.get_text().lower()
            
            # --- DIAGNOSTIC VITAL ---
            est_morte = False
            
            # 1. Message explicite Apec
            if "cette offre n'est plus en ligne" in text_page:
                est_morte = True
            # 2. Redirection ou erreur générique
            elif "erreur inattendue" in text_page:
                est_morte = True
            
            if est_morte:
                date_jour = datetime.now().strftime("%d/%m/%Y")
                df.at[idx, 'Date_Expiration'] = date_jour
                
                # Optionnel : On peut marquer la description, mais attention à ne pas écraser l'info si vous voulez la garder pour l'analyse
                # df.at[idx, 'Description_Complete'] = "OFFRE_EXPIREE" 
                
                print(f"❌ EXPIRÉE (Notée au {date_jour})")
                compteur_morts += 1
                modifications = True
            else:
                print("✅ VIVANTE")
                compteur_vivants += 1
            
            # Sauvegarde intermédiaire tous les 20 items (sécurité)
            if modifications and i > 0 and i % 20 == 0:
                df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
                print("   💾 (Sauvegarde intermédiaire)")
                modifications = False

        except Exception as e:
            print(f"⚠️ Erreur tech : {e}")

except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel ! Sauvegarde de ce qui a été fait...")

finally:
    # SAUVEGARDE FINALE
    # On s'assure de garder l'ordre des colonnes propre
    df = df.reindex(columns=ORDRE_COLONNES)
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    
    driver.quit()
    print("\n🏁 Bilan Updater :")
    print(f"   ⚰️  Offres passées en 'Expirée' : {compteur_morts}")
    print(f"   ✅  Offres confirmées actives : {compteur_vivants}")
    print(f"   📂  Fichier mis à jour : {CSV_PATH}")