import os
import sys
import subprocess
import pandas as pd
from supabase import create_client
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime
from tqdm import tqdm
import pytz
from datetime import datetime
import undetected_chromedriver as uc


# --- 0. CONFIGURATION ---
table_choisie = "Data_Analyst"

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, upsert_data, load_data, verifier_pause_manuelle, verifier_blocage_et_pause


supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
if not supabase_url or not supabase_key:
        print("❌ ERREUR : Clés Supabase introuvables.")
        sys.exit(1)
supabase = create_client(supabase_url, supabase_key)   
print("📥 Récupération du stock actuel pour éviter les doublons...")
filters_apec_scraper= {
"source": "APEC",
"statut": "Cible",
"column": "URL, Ville, Salaire_Annuel, Type_Contrat, Date_Publication"
}
df_source = load_data(supabase, table_name=table_choisie, limit=None, filters = filters_apec_scraper)

timezone_fr = pytz.timezone('Europe/Paris')
date_actuelle = datetime.now(timezone_fr).date()

if df_source.empty:
    print("✨ Aucune nouvelle offre 'Cible' à scraper. Arrêt du script.")
    sys.exit(0)

ids_connus = set(df_source['URL'].dropna())
print(f"🛡️ {len(ids_connus)} offres APEC à scraper.")
print("🚀 Lancement du scraper APEC...")

# --- FONCTIONS ---

def tuer_les_cookies(driver):
    """Cherche le bouton 'Tout refuser' ou 'Refuser' et clique dessus."""
    try:
        # On attend max 3 secondes que le bouton apparaisse
        bouton = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'refuser') or contains(., 'Refuser') or contains(., 'Continuer sans accepter')]"))
        )
        time.sleep(1)
        bouton.click()
        time.sleep(2) # On laisse le temps à la bannière de disparaître
        return True
    except:
        # Si pas de bannière ou bouton pas trouvé, c'est pas grave, on continue
        return False

def extraire_description(soup):
    """Extrait la description"""    
    # 1. La classe standard APEC
    div_officielle = soup.select_one(".details-offer-content")
    if div_officielle:
        return div_officielle.get_text(separator="\n", strip=True)

    # 2. Plan B : Le texte le plus long (mais sans le risque cookie cette fois)
    candidats = soup.find_all(['div', 'section'])
    meilleur_texte = None
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

def clean_contrat(texte):
    """Regex de secours pour le contrat."""
    if not texte: return None
    txt = str(texte).upper()
    if "CDD" in txt: return "CDD"
    if "INTERIM" in txt or "INTÉRIM" in txt: return "Intérim"
    if "FREELANCE" in txt or "INDÉPENDANT" in txt: return "Freelance"
    if "STAGE" in txt: return "Stage"
    if "ALTERNANCE" in txt or "PROFESSIONNALISATION" in txt: return "Alternance"
    if "CDI" in txt: return "CDI"
    return None

def nettoyer_salaire(texte):
    if not texte:
        return None
    txt = str(texte).lower().strip()
    if txt in ["none", "nan", "autre", "inconnu"] or "négocier" in txt or "negocier" in txt:
        return None
    
    match_range = re.search(r'(\d{2,3})\s*[-à]\s*(\d{2,3})', txt)
    if match_range:
        salaire_min = int(match_range.group(1))
        salaire_max = int(match_range.group(2))        
        salaire_moyen = (salaire_min + salaire_max) / 2
        if salaire_moyen < 200:
            salaire_moyen = salaire_moyen * 1000            
        return int(salaire_moyen)
    
    match_simple = re.search(r'(\d{2,3})', txt)
    if match_simple:
        salaire_unique = int(match_simple.group(1))        
        if salaire_unique < 200:
            salaire_unique = salaire_unique * 1000            
        return int(salaire_unique)
    
    return None
    

# --- LE ROBOT ---
dossier_profil_bot = os.path.join(project_root, "logs", "profil_chrome_scraper")
os.makedirs(dossier_profil_bot, exist_ok=True)

lock_path = os.path.join(dossier_profil_bot, "SingletonLock")
if os.path.exists(lock_path):
    try:
        os.remove(lock_path)
    except:
        pass


options = uc.ChromeOptions()
# options = webdriver.ChromeOptions()
#options.add_argument("--start-maximized")
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_experimental_option("excludeSwitches", ["enable-automation"])
# options.add_experimental_option('useAutomationExtension', False)
#options.add_argument("--headless") # Laisse commenté pour voir le robot travailler
# options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox") # Sécurité requise sur les serveurs Linux
options.add_argument("--disable-dev-shm-usage") # Évite les crashs de mémoire (RAM)

options.add_argument(f"--user-data-dir={dossier_profil_bot}")

driver = uc.Chrome(options=options, version_main=152)
#driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
    'source': '''
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        })
    '''
})

print("🚀 Démarrage du Robot APEC (Mode Tueur de Cookies)...")

# --- LA BOUCLE ---
offres_en_memoire = []
deja_faites = []
heure_demarrage = time.time()
LIMITE_TEMPS = (5 * 3600) + (30 * 60)
try:    
    lignes = df_source.to_dict('records')
    
    for index, row in enumerate(tqdm(lignes, desc="Scraping & Cleaning APEC")):
        if time.time() - heure_demarrage > LIMITE_TEMPS:
            print("\n⏳ Limite de 5h30 atteinte ! Arrêt d'urgence pour sauvegarder...")
            break
            
        url = row.get('URL')
        
        # On récupère les données "en or" déjà fournies par le Crawler API        
        ville = row.get('Ville')
        salaire_existant = row.get('Salaire_Annuel')
        contrat_existant = row.get('Type_Contrat')        
        date_publi = row.get('Date_Publication')
        try:
            # On s'assure que c'est bien du texte et que ça commence par http
            if not isinstance(url, str) or not url.startswith("http"):
                print(f"⚠️ URL ignorée car invalide : {url}")
                continue
            driver.get(url)           
                                    
            # 🔨 ACTION : On tue les cookies dès l'arrivée (sur la 1ère page surtout)
            if index == 0 or index % 10 == 0: # On insiste au début et de temps en temps
                tuer_les_cookies(driver)        
            
            time.sleep(random.uniform(3, 5))
            tuer_les_cookies(driver)
            verifier_blocage_et_pause(driver)
            verifier_pause_manuelle()
            
            # Petit scroll pour charger le contenu (Lazy loading)
            driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)
            # if index == 0 or index == 1:
            #     driver.save_screenshot(f"debug_scraper_{index}.png")
            #     print(f"📸 Photo {index} sauvegardée. Regarde le fichier pour vérifier l'affichage.")
            source_brute = driver.page_source.lower()
            if "data-dd" in source_brute or "captcha" in source_brute:
                print("\n🚨 Rattrapage : Blocage DataDome apparu tardivement !")
                verifier_blocage_et_pause(driver)
                source_brute = driver.page_source.lower()

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # --- A. VERIFICATION EXPIRATION ---
            # On extrait la description pour vérifier si l'offre est morte
            description = extraire_description(soup)    
            
            # --- A. DONNÉES ---
                  
            
            # --- B. TAGS (Salaire / Ville) ---
            tags = []
            contrat_final = contrat_existant

            if pd.isna(date_publi) or str(date_publi).lower() in ["none", "nan", "autre", "inconnu"]:
                date_publi = date_actuelle.strftime("%Y-%m-%d")
            
            if pd.notna(ville) and " - " in str(ville):
                ville_finale = re.sub(r"\s*(?:\d{2})?\s*-\s*\d{2,3}$", "", str(ville)).strip()
            else:
                ville_finale = ville
            
            if salaire_existant:
                salaire_clean = nettoyer_salaire(salaire_existant)
            else:
                salaire_clean = None
            
            if pd.isna(contrat_final) or str(contrat_final).lower() in ["none", "nan", "autre", "inconnu"]:
                contrat_final = clean_contrat(description)

            # Si l'offre est morte, on la marque comme archivée
            if not description:
                description = "None"            
            balise_morte = soup.find('apec-offre-unpublished-archived')
            
            if ("n'est plus en ligne" in description.lower() or balise_morte) and "data-dd" not in source_brute:
                print("🗑️  Offre expirée entre-temps. Mise à jour en 'Archivé'.")
                statut = "Archivé"
                date_expi = datetime.now().strftime("%Y-%m-%d")
                description_totale = "Offre expirée/retirée du site."
            else:
                date_expi = None
                statut = "Prep"           
                     
                lis = soup.find_all('li')
                for li in lis:
                    txt = li.get_text(strip=True)
                    if not txt:
                        continue            
                    txt_low = txt.lower()               
                    tags.append(txt)
                
                    # Fallback Salaire
                    if salaire_clean is None:
                        if ("€" in txt or "k€" in txt) and ("an" in txt_low or "brut" in txt_low):
                            if "sport" not in txt_low:
                                # On nettoie la trouvaille immédiatement avec ta fonction !
                                salaire_clean = nettoyer_salaire(txt) 
                                
                    # Fallback Ville
                    if pd.isna(ville) or str(ville).lower() in ["none", "nan"]:
                        if len(txt) < 50 and any(v in txt_low for v in ["paris", "lyon", "marseille", "lille", "bordeaux", "nantes", "toulouse", "cedex"]):
                            ville_finale = re.sub(r"\s*(?:\d{2})?\s*-\s*\d{2,3}$", "", txt).strip()
                    
                details_concat = " | ".join(tags)
                description_texte = description if description else "Description introuvable."
                description_totale = f"TAGS APEC : {details_concat}\n\nDESCRIPTION :\n{description_texte}"

            

            deja_faites.append(url)

            # --- SAUVEGARDE DYNAMIQUE (PARTIAL UPSERT) ---       
            if statut == "Archivé":                
                nouvelle_ligne = {
                    "URL": url,
                    "Statut": "Archivé",
                    "Date_Expiration": date_expi,
                    "Description": description_totale
                }
            else:                
                nouvelle_ligne = {
                    "URL": url,
                    "Ville": ville_finale,
                    "Type_Contrat": contrat_final,
                    "Salaire_Annuel": salaire_clean,                
                    "Description": description_totale,
                    "Date_Publication": date_publi,
                    "Date_Expiration": None,
                    "Statut": "Prep"
                }

            # 🧹 NETTOYAGE ANTI-CRASH JSON POUR SUPABASE
            for cle, valeur in nouvelle_ligne.items():
                if pd.isna(valeur): # Transforme les NaN/NaT de Pandas en "Null" pour Supabase
                    nouvelle_ligne[cle] = None
                elif isinstance(valeur, pd.Timestamp): # Transforme les dates Pandas en texte simple
                    nouvelle_ligne[cle] = valeur.strftime("%Y-%m-%d")
                        
            offres_en_memoire.append(nouvelle_ligne)     

        except Exception as e:
            print(f"❌ Erreur : {e}")
            continue
except KeyboardInterrupt:
    print("\n🛑 INTERRUPTED ! Sauvegarde d'urgence...")    
    exit(0)
except Exception as e:
    print(f"❌ Erreur : {e}")    
    exit(1)

finally:
    print("\n💾 Sauvegarde avant fermeture...")
    nb_archives = sum(1 for offre in offres_en_memoire if offre.get('Statut') == 'Archivé')
    nb_collecte = len(offres_en_memoire) - nb_archives

    print(f"📊 Bilan avant envoi : {nb_collecte} actives, {nb_archives} archivées.")
    if offres_en_memoire:
        upsert_data(supabase, table_choisie, offres_en_memoire)
    pid = None
    try:
        pid = driver.browser_pid
    except:
        print("Pas de PID")
        pass
    try:
        driver.quit()
    except:
        print("Echec de driver.quit()")
        pass
    if pid:
        try:       
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid), "/T"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            print(f"🔫 Processus fantôme Chrome (PID {pid}) éliminé avec succès.")
        except Exception as e:
            print(f"⚠️ Erreur lors du kill du processus : {e}")
        pass
    print("Fin de scraper_apec")
