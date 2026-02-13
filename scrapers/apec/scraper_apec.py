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

# --- 0. CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_apec_url.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_apec_full.csv")

ordre_colonnes = ["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL", "Date", "Date_Expiration"]

if not os.path.exists(INPUT_CSV):
    print(f"❌ ERREUR : {INPUT_CSV} introuvable.")
    exit()

df_source = pd.read_csv(INPUT_CSV, encoding='utf-8', header=None, names=['URL'])
print(f"✅ Chargement de {len(df_source)} offres APEC.")

# Reprise automatique
deja_faites = []
if os.path.exists(OUTPUT_CSV):
    try:
        df_exist = pd.read_csv(OUTPUT_CSV, encoding='utf-8-sig')
        if "Date_Expiration" not in df_exist.columns:
            print("⚠️ Mise à jour du fichier historique : Ajout de la colonne 'Date_Expiration'...")
            df_exist["Date_Expiration"] = "" 
            df_exist = df_exist.reindex(columns=ordre_colonnes)
            df_exist.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        if "URL" in df_exist.columns:
            deja_faites = df_exist["URL"].tolist()
            print(f"🔄 Reprise : {len(deja_faites)} offres déjà faites.")
    except:
        print("⚠️ Fichier de sortie existant mais illisible ou vide.")
        pass
else:
    # Création du fichier vide    
    pd.DataFrame(columns=ordre_colonnes).to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

# --- 1. LE ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--start-maximized")
options.add_argument("--headless")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("🚀 Démarrage du Robot APEC (Mode Tueur de Cookies)...")

# --- FONCTIONS ---

def tuer_les_cookies(driver):
    """Cherche le bouton 'Tout refuser' ou 'Refuser' et clique dessus."""
    try:
        # On attend max 3 secondes que le bouton apparaisse
        bouton = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Tout refuser') or contains(text(), 'Refuser tous') or contains(text(), 'Continuer sans accepter')]"))
        )
        bouton.click()
        time.sleep(2) # On laisse le temps à la bannière de disparaître
        return True
    except:
        # Si pas de bannière ou bouton pas trouvé, c'est pas grave, on continue
        return False

def extraire_description(soup):
    """Extrait la description maintenant que la voie est libre"""
    
    # 1. La classe standard APEC
    div_officielle = soup.select_one(".details-offer-content")
    if div_officielle:
        return div_officielle.get_text(separator="\n", strip=True)

    # 2. Plan B : Le texte le plus long (mais sans le risque cookie cette fois)
    candidats = soup.find_all(['div', 'section'])
    meilleur_texte = "Description introuvable"
    max_len = 0
    
    for c in candidats:
        texte = c.get_text(separator="\n", strip=True)
        # On évite le footer et le header
        if len(texte) > max_len and len(texte) < 15000:
            # Si le texte contient "Mentions légales" ou "Plan du site", on zappe
            if "vie privée" not in texte.lower() and "cookies" not in texte.lower():
                max_len = len(texte)
                meilleur_texte = texte
                
    return meilleur_texte

def extraire_date(soup):
    try:
    # Souvent dans une balise <span> ou <div> avec une classe "date"
    # (Inspectez la page pour trouver la bonne classe, ex: 'date-publication')
        date_element = soup.find('span', class_='date-offre')     
        if date_element:
            raw_date = date_element.get_text().strip()
            # Nettoyage : Transforme "Publiée le 23/01/2026" en "23/01/2026"
            date_clean = raw_date.replace("Publiée le", "").replace("Actualisée le", "").strip()
        else:
            date_clean = datetime.now().strftime("%d/%m/%Y")
    except:
        date_clean = time.strftime("%d/%m/%Y") # Fallback : Date d'aujourd'hui
    return date_clean

# --- 2. LA BOUCLE ---
try:
    for index, row in df_source.iterrows():
        url = row['URL']
        titre_csv = 'Inconnu'
        
        if url in deja_faites:
            continue
        
        print(f"\n🔎 ({index + 1}/{len(df_source)}) {titre_csv}")
        # Init variables pour cette offre
        date_expiration = "" # Vide par défaut
        date_clean = datetime.now().strftime("%d/%m/%Y")
        titre_reel = "Inconnu"
        description = ""
        try:
            driver.get(url)
            
            # 🔨 ACTION : On tue les cookies dès l'arrivée (sur la 1ère page surtout)
            if index == 0 or index % 10 == 0: # On insiste au début et de temps en temps
                tuer_les_cookies(driver)        
            
            time.sleep(random.uniform(4, 8))
            tuer_les_cookies(driver)
            
            # Petit scroll pour charger le contenu (Lazy loading)
            driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # --- A. VERIFICATION EXPIRATION ---
            # On extrait la description pour vérifier si l'offre est morte
            description = extraire_description(soup)
            
            # [MODIFICATION ICI] Si l'offre est morte, on l'abandonne totalement
            if "offre n'est plus en ligne" in description.lower() or "erreur inattendue" in description.lower():
                print("🗑️  Offre expirée entre-temps. Ignorée (pas de sauvegarde).")
                # On l'ajoute à la liste locale pour ne pas la retenter si la boucle continue
                deja_faites.append(url)
                continue
            
            # --- A. DONNÉES ---
            h1 = soup.find('h1')
            titre_reel = h1.get_text(strip=True) if h1 else titre_csv
            
            description = extraire_description(soup)
            date_clean = extraire_date(soup)       
            
            # --- B. TAGS (Salaire / Ville) ---
            tags = []
            salaire_brut = "Non spécifié"
            ville = "Non spécifié"
            entreprise = "Confidentiel"
            
            lis = soup.find_all('li')
            for li in lis:
                txt = li.get_text(strip=True)
                if not txt: continue            
                txt_low = txt.lower()
                # Salaire
                if ("€" in txt or "k€" in txt) and ("an" in txt_low or "brut" in txt_low):
                    if "sport" not in txt_low: # Évite les avantages CE
                        salaire_brut = txt
                # Ville
                elif any(v in txt_low for v in ["paris", "lyon", "marseille", "lille", "bordeaux", "nantes", "toulouse", "cedex"]):
                    if len(txt) < 50:
                        ville = txt
                
                tags.append(txt)
                
            details_concat = " | ".join(tags)

            # --- SAUVEGARDE ---      
            nouvelle_ligne = {
                "Titre": titre_reel,
                "Entreprise": "Apec",
                "Ville": ville,
                "Salaire_Brut": salaire_brut,
                "Details_Tags": details_concat,
                "Description_Complete": description,
                "URL": url,
                "Date" : date_clean,
                "Date_Expiration" : "Offre active"
            }
            
            df_new = pd.DataFrame([nouvelle_ligne], columns=ordre_colonnes)
            df_new.to_csv(OUTPUT_CSV, mode='a', header=False, index=False, encoding='utf-8-sig')
            
            status_msg = "✅ Sauvegardé (Active)" if not date_expiration else "Sauvegardé (Expirée)"
            print(f"{status_msg}")

        except Exception as e:
            print(f"❌ Erreur : {e}")
except KeyboardInterrupt:
    print("\n🛑 INTERRUPTED ! Sauvegarde d'urgence...")
    # Déjà sauvé ligne par ligne (mode='a')
    driver.quit()
    print("💾 Les offres déjà traitées sont en sécurité dans le CSV.")
    exit(0)
except Exception as e:
    print(f"❌ Erreur : {e}")
    # On peut aussi sauver ici si on veut
    driver.quit()

driver.quit()
print("\n🏁 Terminé ! Vérifiez data/enriched/offres_apec_full.csv")
print("Fin de scraper_apec ==> Lancer updater_apec")