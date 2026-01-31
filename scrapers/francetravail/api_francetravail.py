import requests
import pandas as pd
import time
import os
from dotenv import load_dotenv

# --- 1. CONFIGURATION (Remplis tes infos) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
dotenv_path = os.path.join(root_dir, '.env')
load_dotenv(dotenv_path)
CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERREUR : Clés France Travail introuvables. Vérifiez le fichier .env")
    exit()

nom_fichier = "offres_francetravail_full.csv"
CSV_PATH = os.path.join(root_dir, "data", "enriched", nom_fichier)

# --- 2. AUTHENTIFICATION (Récupération du Token) ---
url_auth = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
headers_auth = {"Content-Type": "application/x-www-form-urlencoded"}
params_auth = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "api_offresdemploiv2 o2dsoffre"
}

print("🔑 Authentification...")
resp_auth = requests.post(url_auth, headers=headers_auth, data=params_auth)
if resp_auth.status_code != 200:
    print("❌ Erreur Auth:", resp_auth.text)
    exit()

token = resp_auth.json()['access_token']
print("✅ Token valide.")

# --- 3. CHARGEMENT DE L'HISTORIQUE ---
existing_ids = set()
df_old = pd.DataFrame()

if os.path.exists(CSV_PATH):
    print(f"📂 Lecture du fichier existant : {CSV_PATH}")
    df_old = pd.read_csv(CSV_PATH, dtype=str)
    
    # On essaye de trouver la colonne ID (souvent appelée 'id' ou 'Reference')
    # Ajustez le nom si votre CSV a un nom de colonne différent pour l'identifiant
    if 'id' in df_old.columns:
        existing_ids = set(df_old['id'].tolist())
    elif 'URL' in df_old.columns:
        # Si on n'a pas l'ID, on extrait l'ID depuis l'URL (souvent à la fin)        
        existing_ids = set(df_old['URL'].apply(lambda x: x.split('/')[-1] if isinstance(x, str) else ""))
    
    print(f"📚 {len(existing_ids)} offres déjà en mémoire (on ne les recopiera pas).")
else:
    print("✨ Aucun fichier existant, on commence à zéro.")

# --- 3. LA BOUCLE DE RÉCUPÉRATION ---
url_search = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
headers_search = {
    "Authorization": "Bearer " + token,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

liste_mots_cles = [
    "Data Analyst", 
    "Data Scientist", 
    "Business Analyst", 
    "Business Intelligence",
    "Analyste de données"
]
all_offres_data = [] # On va stocker toutes les offres ici
ids_recuperes = set() #Enlever les doublons

for mot in liste_mots_cles:
    print(f"\n🔎 Recherche pour : '{mot}'")
    start = 0
    step = 140 # Le max autorisé par l'API par appel    
    continuing = True

    while continuing:
        
        # On définit la plage (ex: 0-149, puis 150-299)
        end = start + step - 1
        params_search = {
            "motsCles": mot,
            "range": f"{start}-{end}"
        }
        
        print(f"📡 Récupération de {start} à {end}...", end=" ")
        
        response = requests.get(url_search, headers=headers_search, params=params_search)
        
        if response.status_code == 200 or response.status_code == 206:
            data = response.json()
            resultats = data.get('resultats', [])
            
            # Si la liste est vide, on arrête
            if not resultats:
                print("Vide. Fin.")                
                break
                
            count_new = 0   
                        
            # Nettoyage et Ajout à la liste principale
            for offre in resultats:
                # DÉDOUBLONNAGE : On vérifie l'ID de l'offre
                offer_id = offre.get('id')
                if offer_id in existing_ids:
                    continue
                if offer_id not in ids_recuperes:
                    info = {
                    "id": offer_id,
                    "Titre": offre.get('intitule'),
                    "Entreprise": offre.get('entreprise', {}).get('nom', 'Confidentiel'),
                    "Ville": offre.get('lieuTravail', {}).get('libelle'),
                    "Type_Contrat": offre.get('typeContrat'),
                    "Salaire": offre.get('salaire', {}).get('libelle', 'Non affiché'),
                    "Date_Creation": offre.get('dateCreation'),
                    "URL": offre.get('origineOffre', {}).get('urlOrigine'),
                    "Description": offre.get('description'),
                    "Source": "France Travail",
                    "Date_Expiration": ""
                    }
                    all_offres_data.append(info)
                    ids_recuperes.add(offer_id)
                    count_new += 1

            print(f"   ✅ {len(resultats)} reçues dont {count_new} nouvelles.")
            if len(resultats) < step:
                print("🏁 Dernière page détectée.")
                break

            # Logique de pagination            
            if response.status_code == 200:
                print("🏁 Dernière page atteinte.")
                continuing = False
            else:
                # On prépare le prochain tour
                start += step
                # Petite pause pour être poli avec le serveur
                time.sleep(0.3) 
                
    else:
        print(f"❌ Erreur {response.status_code}. Arrêt.")
        print(response.text)
        continuing = False

# --- 4. SAUVEGARDE FINALE ---
print(f"\n Bilan : {len(all_offres_data)} offres collectées au total.")

if all_offres_data:
    df = pd.DataFrame(all_offres_data)    
    df.to_csv(CSV_PATH, index=False, encoding='utf-8')
    print(f"💾 Sauvegardé dans '{nom_fichier}'")
    print("Fin de api_francetravail ==> Lancer updater_francetravail")
else:
    print("⚠️ Rien à sauvegarder.")