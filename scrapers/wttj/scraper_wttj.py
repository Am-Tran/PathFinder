import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import os
import json

# --- 0. CONFIGURATION ---
# Calcul automatique des chemins pour éviter les erreurs
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_wttj_complet_url.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_wttj_full.csv")

# --- 1. CHARGEMENT ---
if not os.path.exists(INPUT_CSV):
    print(f"❌ ERREUR : Le fichier {INPUT_CSV} est introuvable.")
    exit()

df_source = pd.read_csv(INPUT_CSV)
# Pour tester :
#df_source = df_source.head(5) 

print(f"✅ Chargement de {len(df_source)} offres.")

# --- 2. INIT FICHIER SORTIE ---
# On prépare les colonnes précises que tu veux
colonnes = ["Titre", "Entreprise", "Ville", "Experience_Salaire_Infos", "Description_Complete", "URL"]

if not os.path.exists(OUTPUT_CSV):
    pd.DataFrame(columns=colonnes).to_csv(OUTPUT_CSV, index=False)
    deja_faites = []
else:
    deja_faites = pd.read_csv(OUTPUT_CSV)["URL"].tolist()

# --- 3. LE ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless") # Laisse commenté pour surveiller

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)

print("🚀 Démarrage de l'extraction...")

# --- 4. BOUCLE ---
for index, row in df_source.iterrows():
    url = row['URL']
    titre_csv = row['Titre']
    
    if url in deja_faites:
        print(f"⏩ Déjà fait : {titre_csv}")
        continue
    
    print(f"\n🔎 ({index + 1}/{len(df_source)}) {titre_csv}")
    
    try:
        driver.get(url)
        time.sleep(random.uniform(4, 7)) # Pause nécessaire
        
        # Scroll pour charger tout le texte
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(1)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # --- A. ENTREPRISE (Via URL - Infaillible) ---
        try:
            entreprise = url.split('/companies/')[1].split('/')[0].replace('-', ' ').upper()
        except:
            entreprise = "INCONNU"

        # --- B. LES INFOS CLÉS (Ville, Expérience, Salaire) ---
        # Sur WTTJ, ces infos sont souvent dans une liste <ul> avec des icônes juste sous le titre.
        # On va récupérer TOUS les éléments de cette liste et les mettre dans une colonne.
        infos_cles = []
        ville = "Non spécifié"
        
        # 1. On cherche d'abord dans le code caché pour Google (JSON-LD)
        # C'est la source la plus fiable pour la localisation précise
        try:
            script_json = soup.find('script', type='application/ld+json')
            if script_json:
                data = json.loads(script_json.string)
                
                # Parfois le JSON est une liste, parfois un dictionnaire unique
                if isinstance(data, list):
                    # On cherche l'objet qui est une offre d'emploi
                    job_data = next((item for item in data if item.get('@type') == 'JobPosting'), None)
                else:
                    job_data = data if data.get('@type') == 'JobPosting' else None
                
                if job_data and 'jobLocation' in job_data:
                    address = job_data['jobLocation'].get('address', {})
                    # On récupère la ville propre
                    ville_json = address.get('addressLocality')
                    if ville_json:
                        ville = ville_json
                        print(f"   🎯 Ville trouvée (JSON) : {ville}")
        except Exception as e:
            # Si le JSON échoue, pas grave, on continue avec la méthode visuelle
            pass

        # 2. On récupère quand même les tags visuels (Contrat, Rythme, Salaire...)
        # Car le JSON ne contient pas toujours le salaire ou le télétravail de façon claire
        try:
            tous_li = soup.find_all('li')
            for li in tous_li:
                texte = li.get_text(strip=True)
                # On ne garde que les "petits" textes (tags)
                if 0 < len(texte) < 50:
                    infos_cles.append(texte)
                    
                    # Si la méthode JSON a échoué (ville toujours "Non spécifié")
                    # On essaie de deviner la ville ici en secours
                    if ville == "Non spécifié":
                        if "Paris" in texte or "Lyon" in texte or "Marseille" in texte or "Lille" in texte or "Bordeaux" in texte or "Nantes" in texte or "Toulouse" in texte:
                             ville = texte
        except:
            pass

        # On transforme la liste en une chaîne de texte propre (ex: "CDI | Paris | > 3 ans | 45k€")
        infos_concatenees = " | ".join(infos_cles)

        # --- C. LA DESCRIPTION (Compétences & Missions) ---
        # On cherche le gros bloc de texte. 
        # Stratégie : On cherche la balise qui contient le mot "Descriptif" ou "Profil"
        description = "Non trouvée"
        
        # On cherche tous les paragraphes et les titres
        # C'est la méthode "Aspirateur" : on prend tout le contenu textuel pertinent
        main_content = soup.find('main')
        if main_content:
            # On prend le texte en gardant les sauts de ligne pour que ce soit lisible
            description = main_content.get_text(separator="\n", strip=True)
        else:
            # Plan B : Si pas de main, on cherche section par section
            sections = soup.find_all('section')
            textes_sections = [s.get_text(separator="\n", strip=True) for s in sections]
            # On garde la plus longue section (c'est forcément la description)
            if textes_sections:
                description = max(textes_sections, key=len)

        # --- SAUVEGARDE ---
        nouvelle_ligne = {
            "Titre": titre_csv,
            "Entreprise": entreprise,
            "Ville": ville,
            "Experience_Salaire_Infos": infos_concatenees, # C'est ICI que tu auras l'XP et le Salaire
            "Description_Complete": description,
            "URL": url
        }
        
        df_new = pd.DataFrame([nouvelle_ligne])
        df_new.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
        
        # Petit feedback visuel
        print(f"   📍 Ville: {ville}")
        print(f"   💼 Infos: {infos_concatenees[:60]}...") # Affiche le début des infos
        print("   ✅ Sauvegardé.")

    except Exception as e:
        print(f"❌ Erreur : {e}")

driver.quit()