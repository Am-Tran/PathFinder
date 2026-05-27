import requests
import pandas as pd
import time
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# --- 1. CONFIGURATION (Remplis tes infos) ---
table_choisie = "Data_Analyst"

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))

if root_dir not in sys.path:
    sys.path.append(root_dir)
from utils import fetch_key, mapping_metier

CLIENT_ID = fetch_key("FT_CLIENT_ID")
CLIENT_SECRET = fetch_key("FT_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERREUR : Clés France Travail introuvables. Vérifiez le fichier .env")
    exit()

print("☁️ Initialisation de Supabase...")
supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

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


# --- 3. LA BOUCLE DE RÉCUPÉRATION ---
url_search = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
url_offre_id = "https://candidat.francetravail.fr/offres/recherche/detail/"
headers_search = {
    "Authorization": "Bearer " + token,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# mapping_metier = {
#     "Data Analyst": "Data Analyst",
#     "Analyste de données": "Data Analyst",
#     "Data Scientist": "Data Scientist",
#     "Business Analyst": "Business Analyst",
#     "Business Intelligence": "Business Analyst"
# }
all_offres_data = [] # On va stocker toutes les offres ici
existing_ids = set()
ids_recuperes = set() #Enlever les doublons


for mot in mapping_metier.keys():
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
                if offer_id in existing_ids or offer_id in ids_recuperes:
                    continue
                url_offre = offre.get('origineOffre', {}).get('urlOrigine') or f"{url_offre_id}{offer_id}"
                info = {
                "Titre": offre.get('intitule'),
                "Entreprise": offre.get('entreprise', {}).get('nom', 'Confidentiel'),
                "Ville": offre.get('lieuTravail', {}).get('libelle'),
                "Salaire_Annuel": offre.get('salaire', {}).get('libelle', 'Non affiché'),
                "Type_Contrat": offre.get('typeContrat'),
                "Date_Publication": offre.get('dateCreation'),
                "Source": "France Travail",
                "URL": url_offre,
                "Description": offre.get('description'),
                "Metier": mapping_metier[mot]
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
            elif response.status_code == 206:
                # 206 = Contenu partiel, il y a encore des résultats
                start += step
                time.sleep(0.3) 
            else:
                # Cas théoriquement impossible ici car filtré par le if initial
                continuing = False 
                
        else:
            print(f"❌ Erreur {response.status_code}. Arrêt.")
            print(response.text)
            continuing = False

# --- 4. ENVOI VERS SUPABASE ---
print(f"\n🚀 Bilan : {len(all_offres_data)} offres collectées au total.")

if all_offres_data:
    try:
        # On envoie par paquets de 1000 pour ne pas saturer l'API
        for i in range(0, len(all_offres_data), 1000):
            batch = all_offres_data[i:i+1000]
            supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
            
        print("✅ SUCCÈS CLOUD : Base de données mise à jour avec les offres France Travail.")
        print("Fin de api_francetravail ==> Lancer clean_francetravail")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi à Supabase : {e}")
else:
    print("⚠️ Aucune offre à envoyer.")