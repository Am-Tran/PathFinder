import pandas as pd
import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
URL_APEC = "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=Data%20analyst"
PAGES_A_SCRAPER = 35  # 5 pages = environ 100 offres (L'Apec met 20 offres par page)

# --- INITIALISATION DU ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless") # Laisse commenté pour voir le robot travailler

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)

try:
    driver.get(URL_APEC)
    
    # 1. GESTION DES COOKIES
    print("🍪 Tentative d'acceptation des cookies...")
    try:
        wait = WebDriverWait(driver, 10)
        # L'ID du bouton "Tout accepter" sur Apec (souvent OneTrust)
        btn_cookie = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        btn_cookie.click()
        print("✅ Cookies acceptés !")
        time.sleep(2)
    except:
        print("⚠️ Pas de bannière cookie ou clic impossible (on continue quand même).")

    all_offres = []
    
    # --- BOUCLE DES PAGES ---
    for page in range(PAGES_A_SCRAPER):
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
        for lien in liens_offres:
            url_partielle = lien['href']
            
            if '/emploi/detail-offre/' in url_partielle:
                # Reconstruction de l'URL complète
                if url_partielle.startswith('http'):
                    full_url = url_partielle
                else:
                    full_url = "https://www.apec.fr" + url_partielle
                
                # Extraction du Titre (souvent dans un h3 ou h4 dans le lien)
                titre_tag = lien.find(['h3', 'h4'])
                if titre_tag:
                    titre = titre_tag.get_text(strip=True)
                else:
                    # Si pas de balise titre, on prend le texte du lien
                    titre = lien.get_text(strip=True)
                
                # Extraction Entreprise (Souvent dans une div "frère" ou parent, plus dur à choper génériquement)
                # Pour l'instant on se concentre sur Titre + URL pour aller chercher les détails plus tard si besoin
                
                # Petit nettoyage du titre si c'est vide
                if titre and len(titre) > 3:
                    # On évite les doublons dans la liste actuelle
                    if not any(d['URL'] == full_url for d in all_offres):
                        all_offres.append({
                            "Titre": titre,
                            "URL": full_url,
                            "Source": "Apec",
                            "Date_Scraping": time.strftime("%Y-%m-%d")
                        })
                        count_page += 1
        
        print(f"   ✅ {count_page} offres trouvées sur cette page.")
        
        # Passage à la page suivante
        if page < PAGES_A_SCRAPER - 1:
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
                    print("   🖱️ Clic effectué ! Chargement...")
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
    print("\n🤖 Robot rentré à la base.")

# --- SAUVEGARDE ---
print(f"📊 Bilan Apec : {len(all_offres)} offres récupérées.")
if all_offres:
    df = pd.DataFrame(all_offres)
    df.to_csv("offres_apec.csv", index=False, encoding='utf-8')
    print("💾 Sauvegardé dans 'offres_apec.csv'")