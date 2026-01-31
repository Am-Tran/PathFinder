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
ordre_colonnes = ["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL", "Date", "Date_Expiration"]

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
    print("✅ Toutes vos offres expirées sont déjà marquées . Rien à faire.")
    exit()

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
            time.sleep(random.uniform(3, 5))
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            text_page = soup.get_text().lower()
            
            # --- LOGIQUE DE DIAGNOSTIC ---
            # 1. Signes positifs
            signes_vie = ["postuler", "candidater", "sauvegarder cette offre"]
            est_vivante = any(s in text_page for s in signes_vie)

            # 2. Signes négatifs
            signes_mort = [
                "n'est plus en ligne",
                "n'est plus disponible",
                "n'existe plus"                
            ]
            est_morte_certaine = any(s in text_page for s in signes_mort)

            # --- DÉCISION ---
            if est_vivante:
                print("✅ VIVANTE (Confirmée)")
                compteur_vivants += 1

            elif est_morte_certaine:
                date_jour = datetime.now().strftime("%d/%m/%Y")
                df.at[idx, 'Date_Expiration'] = date_jour
                print(f"❌ EXPIRÉE (Preuve trouvée)")
                compteur_morts += 1
                modifications = True

            else:
                # ZONE GRISE : Ni vivante, ni morte explicite -> C'est louche (Bot detection ?)
                # On ne touche pas à la date, on garde l'offre, mais on regarde pourquoi
                print("⚠️ DOUTE (Ni bouton, ni message d'erreur -> On garde)")
                
                # Photo pour debug
                nom_photo = f"debug_apec_{i}.png"
                driver.save_screenshot(nom_photo)
                print(f"   📸 Photo prise : {nom_photo}")

            # Sauvegarde intermédiaire
            if modifications and i > 0 and i % 10 == 0:
                df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
                modifications = False
        except Exception as e:
                    print(f"⚠️ Erreur tech : {e}")

# --- GESTION DE L'ARRÊT MANUEL (CTRL+C) ---
except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel ! Sauvegarde de ce qui a été fait...")

# --- FERMETURE PROPRE ---
finally:
    # SAUVEGARDE FINALE
    # On s'assure de garder l'ordre des colonnes propre
    df = df.reindex(columns=ordre_colonnes)
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    
    driver.quit()
    print("\n🏁 Bilan Updater :")
    print(f"   ⚰️  Offres passées en 'Expirée' : {compteur_morts}")
    print(f"   ✅  Offres confirmées actives : {compteur_vivants}")
    print(f"   📂  Fichier mis à jour : {CSV_PATH}")
    print("Fin de updater_apec ==> Lancer clean_apec")