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

# --- 0. CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_apec_url.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_apec_full.csv")

if not os.path.exists(INPUT_CSV):
    print(f"❌ ERREUR : {INPUT_CSV} introuvable.")
    exit()

df_source = pd.read_csv(INPUT_CSV)
print(f"✅ Chargement de {len(df_source)} offres APEC.")

# Reprise automatique
deja_faites = []
if os.path.exists(OUTPUT_CSV):
    try:
        df_exist = pd.read_csv(OUTPUT_CSV)
        if "URL" in df_exist.columns:
            deja_faites = df_exist["URL"].tolist()
            print(f"🔄 Reprise : {len(deja_faites)} offres déjà faites.")
    except:
        pass
else:
    # Création du fichier vide
    pd.DataFrame(columns=["Titre", "Entreprise", "Ville", "Salaire_Brut", "Details_Tags", "Description_Complete", "URL"]).to_csv(OUTPUT_CSV, index=False)

# --- 1. LE ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--start-maximized")
# options.add_argument("--headless") # Garde ça commenté pour voir le clic se faire !

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

# --- 2. LA BOUCLE ---
for index, row in df_source.iterrows():
    url = row['URL']
    titre_csv = row['Titre']
    
    if url in deja_faites:
        continue
    
    print(f"\n🔎 ({index + 1}/{len(df_source)}) {titre_csv}")
    
    try:
        driver.get(url)
        
        # 🔨 ACTION : On tue les cookies dès l'arrivée (sur la 1ère page surtout)
        if index == 0 or index % 10 == 0: # On insiste au début et de temps en temps
            if tuer_les_cookies(driver):
                print("   🍪 Bannière Cookies fermée !")
        
        time.sleep(random.uniform(4, 8))

        # 🔨 TENTATIVE DE MEURTRE DE COOKIE
        # On le tente à chaque fois pour être sûr, le script ne plantera pas si y'a rien
        tuer_les_cookies(driver)
        
        # Petit scroll pour charger le contenu (Lazy loading)
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(1)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # --- A. DONNÉES ---
        h1 = soup.find('h1')
        titre_reel = h1.get_text(strip=True) if h1 else titre_csv
        
        description = extraire_description(soup)
        
        # Nettoyage si la description est un message d'erreur APEC
        if "offre n'est plus en ligne" in description.lower() or "erreur inattendue" in description.lower():
            description = "OFFRE_EXPIREE"

        # --- B. TAGS (Salaire / Ville) ---
        tags = []
        salaire_brut = "Non spécifié"
        ville = "Non spécifié"
        
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
        # Si l'offre est expirée, on peut choisir de ne pas la garder, ou de la garder marquée
        if description == "OFFRE_EXPIREE":
            print("   🗑️ Offre expirée, on passe.")
            # On l'ajoute quand même aux "déjà faites" pour ne pas boucler dessus si on relance
            # Mais on ne l'écrit pas dans le CSV final (optionnel, ici je n'écris pas)
            deja_faites.append(url) 
            continue 

        nouvelle_ligne = {
            "Titre": titre_reel,
            "Entreprise": "Apec",
            "Ville": ville,
            "Salaire_Brut": salaire_brut,
            "Details_Tags": details_concat,
            "Description_Complete": description,
            "URL": url
        }
        
        df_new = pd.DataFrame([nouvelle_ligne])
        df_new.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
        
        print(f"   ✅ Sauvegardé (Desc: {len(description)} cars)")
        if salaire_brut != "Non spécifié":
            print(f"   💰 {salaire_brut}")

    except Exception as e:
        print(f"   ❌ Erreur : {e}")

driver.quit()