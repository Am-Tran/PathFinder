import os
import sys
import pandas as pd
import time
import random
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from supabase import create_client

# --- CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, load_data

supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

table_choisie = "Data_Analyst_test"

if project_root not in sys.path:
    sys.path.append(project_root)
from utils import sauvegarde_securisee

INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_apec_url.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_apec_full.csv")

# --- FONCTION UTILITAIRE DE NETTOYAGE ---
def extraire_id(url_brute):
    """
    Transforme n'importe quelle URL Apec en son ID unique.

    """
    if not isinstance(url_brute, str):
        return ""
    
    # 1. On coupe tout ce qui dépasse après le ?
    base = url_brute.split('?')[0]
    
    # 2. On enlève le dernier slash s'il y en a un (ex: .../123W/)
    if base.endswith('/'):
        base = base[:-1]
        
    # 3. On prend le dernier morceau après le dernier slash
    id_offre = base.split('/')[-1]
    
    return id_offre.strip()

# --- CHARGEMENT DE L'HISTORIQUE ---
chemin_history = "data/enriched/offres_apec_full.csv"
ids_connus = set()

print("🔄 Chargement de l'historique...")
if os.path.exists(chemin_history):
    try:
        df_history = pd.read_csv(chemin_history)
        
        # Recherche de la colonne URL
        col_url = None
        if 'URL' in df_history.columns:
            col_url = 'URL'
        if col_url:    
            raw_urls = df_history[col_url].dropna().tolist()
            ids_connus = set([extraire_id(u) for u in raw_urls])
            print(f"🧠 Historique chargé et nettoyé : {len(ids_connus)} offres uniques en mémoire.")
        else:
            print("⚠️ Pas de colonne URL trouvée dans le fichier historique.")
            
    except Exception as e:
        print(f"❌ Erreur lecture historique : {e}")
else:
    print("✨ Aucun historique trouvé, on part de zéro.")

urls_trouvees_ce_jour = [] # On stockera ici les URLs propres trouvées aujourd'hui

# --- CONFIGURATION ---
URL_APEC = "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=Data%20analyst&tri=DatePublication_desc"
PAGES_A_SCRAPER = 38  # 5 pages = environ 100 offres (L'Apec met 20 offres par page)

# --- INITIALISATION DU ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
#options.add_argument("--headless") # Laisse commenté pour voir le robot travailler

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)
stop_scraping = False
try:
    driver.get(URL_APEC)
    
    # 1. GESTION DES COOKIES
    print("🍪 Tentative d'acceptation des cookies...")
    try:
        wait = WebDriverWait(driver, 10)
        # L'ID du bouton "Tout accepter" sur Apec
        selecteur_cookies = "#onetrust-accept-btn-handler, #didomi-notice-agree-button"
        btn_cookie = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selecteur_cookies)))
        btn_cookie.click()        
        print("✅ Cookies acceptés !")
        time.sleep(2)
    except:
        print("⚠️ Pas de bannière cookie ou clic impossible (on continue quand même).")    
    
    # --- BOUCLE DES PAGES ---
    for page in range(PAGES_A_SCRAPER):
        if stop_scraping:
            print("🛑 Arrêt demandé : historique rejoint (fin de la boucle des pages).")
            break
        print(f"\nAnalyse de la page {page + 1} / {PAGES_A_SCRAPER}...")
        
        # On scroll un peu pour être sûr que tout charge
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight -500);")
        time.sleep(random.uniform(2, 4)) # Pause humaine
        
        # Analyse du HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Sur Apec, les cartes sont souvent des <div>, mais les liens sont la clé
        # On cherche tous les liens qui contiennent "/emploi/detail-offre/"
        liens_offres = soup.find_all('a', href=True)        
        count_page = 0
        compteur_doublons = 0
        SEUIL_TOLERANCE = 10 # On s'arrête seulement si on voit 3 doublons d'affilée
        for lien in liens_offres:
            url_partielle = lien['href']
            
            if '/emploi/detail-offre/' in url_partielle:
                # Reconstruction de l'URL complète
                if url_partielle.startswith('http'):
                    full_url = url_partielle
                else:
                    full_url = "https://www.apec.fr" + url_partielle
                
                id_actuel = extraire_id(full_url)
                if (id_actuel not in ids_connus) and (full_url not in urls_trouvees_ce_jour):
                    urls_trouvees_ce_jour.append(full_url)
                    compteur_doublons = 0
                    count_page += 1          

                elif id_actuel in ids_connus:
                    compteur_doublons += 1
                    print(f"Doublon détecté ({compteur_doublons}/{SEUIL_TOLERANCE})")
                    
                    if compteur_doublons >= SEUIL_TOLERANCE:
                        print("🛑 Trop de doublons, on arrête tout.")   
                        stop_scraping = True                         
                        break
                else:
                    pass                
                                   
                                          
        print(f"✅ {count_page} offres trouvées sur cette page.")
        
        # Passage à la page suivante
        if not stop_scraping and page < PAGES_A_SCRAPER - 1:
            page_suivante_trouvee = False
            try:
                print("➡️ Recherche du bouton 'Suivant'...")
                # On cherche une balise 'a' ou 'li' qui contient le texte "Suivant" ou qui a une classe spécifique
                # Sur l'Apec, c'est souvent la classe "page-link" dans le dernier "page-item"
                boutons_pagination = driver.find_elements(By.CSS_SELECTOR, "ul.pagination li")
                
                if boutons_pagination:
                    # Le bouton "Suivant" est généralement le dernier de la liste
                    bouton_suivant = boutons_pagination[-1]
                    
                    # Vérification : est-il désactivé ? (Classe 'disabled')
                    classes = bouton_suivant.get_attribute("class")
                    if "disabled" in classes:
                        print("🛑 Le bouton Suivant est désactivé. Fin du site.")
                        break
                    
                    # On cherche le lien <a> à l'intérieur pour cliquer dessus
                    lien_a_cliquer = bouton_suivant.find_element(By.TAG_NAME, "a")

                    # On scroll jusqu'au bouton pour être sûr qu'il est visible
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lien_a_cliquer)
                    time.sleep(1)
                    
                    # On clique (via Javascript pour forcer le clic même si une pub gêne)
                    driver.execute_script("arguments[0].click();", lien_a_cliquer)
                    print("🖱️ Clic effectué ! Chargement...")
                    time.sleep(5) # On attend bien que la nouvelle page charge
                else:
                    print("🛑 Pas de pagination trouvée.")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception as e:
                print(f"❌ Erreur pagination : {e}")
                # Si ça plante, on tente une dernière méthode de secours : trouver la flèche par son icône
                try:
                    fleche = driver.find_element(By.CSS_SELECTOR, ".pagination-item-next")
                    driver.execute_script("arguments[0].click();", fleche)
                    time.sleep(5)
                except:
                    print("   -> Échec définitif du passage de page. Arrêt.")
                    break

except Exception as e:
    print(f"❌ Erreur générale : {e}")

finally:
    driver.quit()
    if urls_trouvees_ce_jour:
        print(f"\n📤 Envoi de {len(urls_trouvees_ce_jour)} nouvelles URLs vers Supabase...")
        # SAUVEGARDE FINALE
        date_jour = datetime.now().strftime("%Y-%m-%d")
        donnees_a_inserer = []
        for url in urls_trouvees_ce_jour:
            donnees_a_inserer.append({
                "URL": url,
                "Source": "APEC"
                
                #"Statut": "A_SCRAPER" # Un petit tag utile pour ton scraper
            })    
        try:
            for i in range(0, len(donnees_a_inserer), 1000):
                batch = donnees_a_inserer[i:i+1000]            
                supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
                
            print("✅ SUCCÈS : Base de données mise à jour avec les nouvelles URLs.")
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi à Supabase : {e}")
        # --- 2. SAUVEGARDE LOCALE (Pour le Scraper V1) ---
        try:
            os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
            df_urls = pd.DataFrame(urls_trouvees_ce_jour, columns=["URL"])
            # On recrée le fichier pour le scraper
            sauvegarde_securisee(df_urls, OUTPUT_CSV)
            print(f"✅ SUCCÈS LOCAL : 'offres_apec_url.csv' généré pour le scraper.")
        except Exception as e:
            print(f"❌ Erreur lors de la création du CSV : {e}")

    else:
        print("Ø Aucune nouvelle offre détectée par rapport à l'historique.")  