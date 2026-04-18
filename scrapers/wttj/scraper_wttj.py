import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import os
import json
from datetime import datetime
from tqdm import tqdm

# --- 0. CONFIGURATION ---
# Calcul automatique des chemins pour éviter les erreurs
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

INPUT_CSV = os.path.join(project_root, "data", "raw", "offres_wttj_url.csv")
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
colonnes = ["Titre", "Entreprise", "Ville", "Experience_Salaire_Infos", "Description_Complete", "URL", "Date_Publication"]

if not os.path.exists(OUTPUT_CSV):
    # On s'assure que le dossier de destination existe sur GitHub Actions
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    pd.DataFrame(columns=colonnes).to_csv(OUTPUT_CSV, index=False)
    deja_faites = []
else:
    try:
        df_exist = pd.read_csv(OUTPUT_CSV)
        # Si la colonne Date manque, on l'ajoute
        if "Date_Publication" not in df_exist.columns:
            print("⚠️ Ajout de la colonne 'Date_Publication' au fichier existant...")
            df_exist["Date_Publication"] = None
            df_exist = df_exist.reindex(columns=colonnes)
            df_exist.to_csv(OUTPUT_CSV, index=False)
            
        deja_faites = df_exist["URL"].tolist()
    except Exception as e:
        print(f"⚠️ Fichier corrompu ou vide : {e}. On repart à zéro.")
        deja_faites = []

# --- 3. LE ROBOT ---
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--headless") # Laisse commenté pour surveiller

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_window_size(1920, 1080)

print("🚀 Démarrage de l'extraction...")

# --- 4. BOUCLE ---
try:
    for index, row in tqdm(df_source.iterrows(), desc = "Scraping WTTJ"):
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
            date_pub = None
            
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
                    
                    if job_data:
                        if 'jobLocation' in job_data:
                            address = job_data['jobLocation'].get('address', {})
                            # On récupère la ville propre
                            ville_json = address.get('addressLocality')
                            if ville_json:
                                ville = ville_json
                                print(f"   🎯 Ville trouvée (JSON) : {ville}")
                        if 'datePosted' in job_data:                        
                            date_pub = job_data['datePosted'].split('T')[0]
                            print(f"   📅 Date trouvée (JSON) : {date_pub}")
            except Exception as e:
                # Si le JSON échoue, pas grave, on continue avec la méthode visuelle
                pass
            # SI PAS DE DATE TROUVÉE DANS LE JSON -> DATE DU JOUR
            if not date_pub:
                date_pub = datetime.now().strftime("%Y-%m-%d")
                print(f"   📅 Date introuvable -> Utilisation date du jour : {date_pub}")

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
                            mots_cles_bannis = [
                    "CDI", "CDD", "Stage", "Alternance", "Freelance", "Apprentissage", # Contrats
                    "Temps plein", "Temps partiel", "Partiel", # Rythme
                    "Télétravail", "Remote", "Hybride", # Mode de travail
                    "ans", "xp", "expérience", # Expérience
                    "k€", "€", "salaire", # Salaire
                    "bac", "master", "diplôme", # Etudes                
                    "annonce", "sponsorisé", "pub", "cookie", "paramètre", "login", "connexion" # Interface & Pubs
                ]            
                            # Si le texte ne contient AUCUN des mots bannis, c'est probablement la ville !
                            # (On vérifie aussi que ce n'est pas un texte trop long ou vide)
                            est_banni = any(banni.lower() in texte.lower() for banni in mots_cles_bannis)
                            
                            if not est_banni and len(texte) < 30:
                                if not any(char.isdigit() for char in texte):
                                    ville = texte                            
                                # On ajoute un petit print pour vérifier
                                # print(f"   📍 Ville devinée par élimination : {ville}")
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
                "URL": url,
                "Date_Publication": date_pub
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
    print("\n🏁 Extraction terminée.")
except KeyboardInterrupt:
    print("\n\n🛑 Interruption manuelle détectée (Ctrl+C) !")
    print("💾 Pas de panique : Les offres traitées jusqu'ici sont bien sauvegardées.")

except Exception as e:
    # Ça attrape les autres erreurs (crash global imprévu)
    print(f"\n❌ Erreur critique du script : {e}")

finally:
    # Ce bloc s'exécute TOUJOURS (que ça finisse bien, que ça plante, ou que tu arrêtes)
    if 'driver' in locals():
        driver.quit()
    print("\n🤖 Robot rentré au garage. Fin du programme.")
    print("Fin du scraper_wttj ==> Lancer le updater_wttj")

