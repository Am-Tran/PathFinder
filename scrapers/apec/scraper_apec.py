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
import sys
from datetime import datetime
from tqdm import tqdm
from supabase import create_client

# --- 0. CONFIGURATION ---
table_choisie = "Data_Analyst"

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, upsert_data

INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_apec_url.csv")

ordre_colonnes = ["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL", "Date", "Date_Expiration", "Source", "Statut"]

if not os.path.exists(INPUT_CSV):
    print(f"❌ ERREUR : {INPUT_CSV} introuvable.")
    exit()

df_source = pd.read_csv(INPUT_CSV, encoding='utf-8', header=None, names=['URL'], nrows=1000)
print(f"✅ Chargement de {len(df_source)} offres APEC.")

supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Reprise automatique


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
            date_brute = raw_date.replace("Publiée le", "").replace("Actualisée le", "").strip()
            date_clean = datetime.strptime(date_brute, "%d/%m/%Y").strftime("%Y-%m-%d")
        else:
            date_clean = datetime.now().strftime("%Y-%m-%d")
    except:
        date_clean = time.strftime("%Y-%m-%d") # Fallback : Date d'aujourd'hui
    return date_clean

# --- 2. LA BOUCLE ---
try:
    offres_en_memoire = []
    deja_faites = []

    for index, row in tqdm(df_source.iterrows(), desc="Scraping APEC"):
        url = row['URL']
        titre_csv = 'Inconnu'
        
        if url in deja_faites:
            continue
        
        print(f"\n🔎 ({index + 1}/{len(df_source)}) {titre_csv}")
        # Init variables pour cette offre
        date_expiration = "" # Vide par défaut
        date_clean = datetime.now().strftime("%Y-%m-%d")
        titre_reel = "Inconnu"
        description = ""
        try:
            # On s'assure que c'est bien du texte et que ça commence par http
            if not isinstance(url, str) or not url.startswith("http"):
                print(f"⚠️ URL ignorée car invalide : {url}")
                continue
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
            salaire_brut = None
            ville = None
            
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
            description_totale = f"TAGS APEC : {details_concat}\n\nDESCRIPTION :\n{description}"
            deja_faites.append(url)

            # --- SAUVEGARDE ---      
            nouvelle_ligne = {
                "Titre": titre_reel,
                "Entreprise": None,
                "Ville": ville,
                "Salaire_Annuel": salaire_brut,                
                "Description": description_totale,
                "Source" : "APEC",
                "URL": url,
                "Date_Publication" : date_clean,
                "Date_Expiration" : None,
                "Statut" : "Collecte"

            }
                        
            offres_en_memoire.append(nouvelle_ligne)     

        except Exception as e:
            print(f"❌ Erreur : {e}")
except KeyboardInterrupt:
    print("\n🛑 INTERRUPTED ! Sauvegarde d'urgence...")
    upsert_data(supabase, table_choisie, offres_en_memoire)
    driver.quit()
    exit(0)
except Exception as e:
    print(f"❌ Erreur : {e}")
    upsert_data(supabase, table_choisie, offres_en_memoire)
    driver.quit()
    exit(1)

upsert_data(supabase, table_choisie, offres_en_memoire)
driver.quit()
print("Fin de scraper_apec ==> Lancer clean_apec")
