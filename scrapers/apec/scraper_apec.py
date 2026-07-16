import pandas as pd
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
from utils import fetch_key, upsert_data, load_data

# INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_apec_url.csv")

# ordre_colonnes = ["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL", "Date", "Date_Expiration", "Source", "Statut"]

# if not os.path.exists(INPUT_CSV):
#     print(f"❌ ERREUR : {INPUT_CSV} introuvable.")
#     exit()

# df_source = pd.read_csv(INPUT_CSV, encoding='utf-8', header=None, names=['URL'], nrows=100)
# print(f"✅ Chargement de {len(df_source)} offres APEC.")

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
"column": "URL"
}
df_source = load_data(supabase, table_name=table_choisie, limit=None, filters = filters_apec_scraper)

if df_source.empty:
    print("✨ Aucune nouvelle offre 'Cible' à scraper. Arrêt du script.")
    sys.exit(0)

ids_connus = set(df_source['URL'].dropna())
print(f"🛡️ {len(ids_connus)} offres APEC déjà en base. Elles seront ignorées.")
print("🚀 Lancement du crawler APEC...")

# Reprise automatique


# --- 1. LE ROBOT ---
options = webdriver.ChromeOptions()
#options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--headless") # Laisse commenté pour voir le robot travailler
options.add_argument("--no-sandbox") # Sécurité requise sur les serveurs Linux
options.add_argument("--disable-dev-shm-usage") # Évite les crashs de mémoire (RAM)

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

def extraire_bandeau(soup) -> tuple[str | None, str | None, str | None]:
    """
    Extrait et nettoie la ville depuis la dernière puce du bandeau de l'offre APEC.
    
    """
    entreprise = None
    ville = None
    contrat = None
    try:
        # Recherche du bandeau de détails
        bandeau_details = soup.find(lambda tag: tag.has_attr('class') and 
                    any('details' in c for c in tag['class']) and 
                    any('offer' in c for c in tag['class']))
        if not bandeau_details:
            return entreprise, ville, contrat
            
        # Récupération des puces du bandeau
        lis_bandeau = bandeau_details.find_all('li')
        if not lis_bandeau:
            return entreprise, ville, contrat
        
        mots_bannis = ["linkedin", "twitter", "facebook", "imprimer"]
        puces_propres = []
        for li in lis_bandeau:
            texte = li.get_text(strip=True)
            if texte and not any(mot in texte.lower() for mot in mots_bannis):
                puces_propres.append(texte)
        
        if not puces_propres:
            return entreprise, ville, contrat
        
        premiere_puce = puces_propres[0]
        mots_contrats = ["cdi", "cdd", "stage", "alternance", "indépendant", "intérim", "freelance", "apprentissage"]

        for mot in mots_contrats:
            if mot in premiere_puce.lower():
                contrat = mot                
                break
        else:
            entreprise = premiere_puce
            for puce in puces_propres[1:]:
                for mot in mots_contrats:
                    if mot in puce.lower():
                        contrat = mot
                        break
                if contrat:
                    break

        ville_brute = puces_propres[-1]           
        ville_clean = re.sub(r'\s*\d{2}.*', '', ville_brute).strip()
        if len(ville_clean) > 0 and ville_clean != contrat:
            ville = ville_clean

    except Exception as e:
        print(f"⚠️ Erreur lors de l'extraction du bandeau : {e}")
    return entreprise, ville, contrat


# --- 2. LA BOUCLE ---
try:
    offres_en_memoire = []
    deja_faites = []
    heure_demarrage = time.time()
    LIMITE_TEMPS = (5 * 3600) + (30 * 60)

    for index, row in tqdm(df_source.iterrows(), desc="Scraping APEC"):
        if time.time() - heure_demarrage > LIMITE_TEMPS:
            print("\n⏳ Limite de 5h30 atteinte ! Arrêt d'urgence pour sauvegarder...")
            break
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
                print("🗑️  Offre expirée entre-temps. Mise à jour en 'Archivé'.")
                # On l'ajoute à la liste locale pour ne pas la retenter si la boucle continue
                deja_faites.append(url)
                offres_en_memoire.append({
                    "URL": url,
                    "Source": "APEC",
                    "Statut": "Archivé",
                    "Date_Expiration": datetime.now().strftime("%Y-%m-%d")
                })
                continue
            
            # --- A. DONNÉES ---
            h1 = soup.find('h1')
            titre_reel = h1.get_text(strip=True) if h1 else titre_csv
            
            description = extraire_description(soup)
            date_clean = extraire_date(soup)       
            
            # --- B. TAGS (Salaire / Ville) ---
            tags = []
            salaire_brut = None
            entreprise, ville, contrat = extraire_bandeau(soup)
            
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
                if( ville is None) and (len(txt) < 50) and any(v in txt_low for v in ["paris", "lyon", "marseille", "lille", "bordeaux", "nantes", "toulouse", "cedex"]):
                        ville = txt
                
                tags.append(txt)
                
            details_concat = " | ".join(tags)
            description_totale = f"TAGS APEC : {details_concat}\n\nDESCRIPTION :\n{description}"
            deja_faites.append(url)

            # --- SAUVEGARDE ---      
            nouvelle_ligne = {
                "Titre": titre_reel,
                "Entreprise": entreprise,
                "Ville": ville,
                "Type_Contrat": contrat,
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
    # upsert_data(supabase, table_choisie, offres_en_memoire)
    # driver.quit()
    exit(0)
except Exception as e:
    print(f"❌ Erreur : {e}")
    # upsert_data(supabase, table_choisie, offres_en_memoire)
    # driver.quit()
    exit(1)

finally:
    print("\n💾 Sauvegarde finale avant fermeture...")
    if offres_en_memoire:
        upsert_data(supabase, table_choisie, offres_en_memoire)
    try:
        driver.quit()
    except:
        pass
    print("Fin de scraper_apec ==> Lancer clean_apec")
