import requests
import pandas as pd
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# --- CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
dotenv_path = os.path.join(root_dir, '.env')
load_dotenv(dotenv_path)

CLIENT_ID = os.getenv("FT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
CSV_PATH = os.path.join(root_dir, "data", "enriched", "offres_francetravail_full.csv")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERREUR : Clés France Travail introuvables dans .env")
    exit()

if not os.path.exists(CSV_PATH):
    print(f"❌ Pas de fichier : {CSV_PATH}")
    exit()

# --- CHARGEMENT ---
print("🔄 Chargement du fichier...")
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', dtype=str)

# Vérification colonne Date_Expiration
if 'Date_Expiration' not in df.columns:
    df['Date_Expiration'] = None

# On cherche les offres SANS date d'expiration
mask_a_verifier = df['Date_Expiration'].isna() | (df['Date_Expiration'] == "") | (df['Date_Expiration'] == "nan")
indices_a_verifier = df[mask_a_verifier].index

print(f"📊 Total offres : {len(df)}")
print(f"🕵️  Offres à vérifier via API : {len(indices_a_verifier)}")

if len(indices_a_verifier) == 0:
    print("✅ Tout est déjà à jour.")
    exit()

# --- AUTHENTIFICATION ---
def get_token():
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "api_offresdemploiv2 o2dsoffre"
    }
    try:
        r = requests.post(url, headers=headers, data=data)
        if r.status_code == 200:
            return r.json()['access_token']
        else:
            print(f"❌ Erreur Token : {r.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur connexion : {e}")
        return None

token = get_token()
if not token: exit()

# --- BOUCLE DE VÉRIFICATION ---
print("\n🚀 Démarrage de la vérification API...")
compteur_morts = 0
compteur_vivants = 0
modifications = False
api_base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/"

for i, idx in enumerate(indices_a_verifier):
    try:
        # 1. On récupère l'ID propre        
        offer_id = df.at[idx, 'id'] if 'id' in df.columns and pd.notna(df.at[idx, 'id']) else None
        
        if not offer_id:
            # Tentative d'extraction depuis l'URL (ex: .../detail/1234567)
            url = str(df.at[idx, 'URL'])
            if "detail/" in url:
                offer_id = url.split("detail/")[-1].split("/")[0]
        
        if not offer_id:
            print(f"⚠️  Ligne {idx} : Impossible de trouver l'ID de l'offre.")
            continue

        # 2. Appel API
        headers = {"Authorization": f"Bearer {token}"}        
        
        r = requests.get(api_base_url + offer_id, headers=headers)

        # 3. Verdict
        # Code 200 = L'offre existe et on reçoit ses infos -> VIVANTE
        # Code 204 (No Content) ou 404 (Not Found) = L'offre n'existe plus -> MORTE
        
        titre = str(df.at[idx, 'Titre'])[:20]
        
        if r.status_code == 200:
            print(f"✅ [{i+1}] {offer_id} : ACTIVE")
            compteur_vivants += 1
            
        elif r.status_code == 204 or r.status_code == 404:
            print(f"❌ [{i+1}] {offer_id} : EXPIRÉE")
            df.at[idx, 'Date_Expiration'] = datetime.now().strftime("%d/%m/%Y")
            compteur_morts += 1
            modifications = True
            
        elif r.status_code == 401: # Token expiré
            print("🔄 Token expiré, renouvellement...")
            token = get_token()
            
        elif r.status_code == 429: # Trop de requêtes
            print("⏳ Trop vite ! Pause de 5 sec...")
            time.sleep(5)
            
        else:
            print(f"⚠️  [{i+1}] {offer_id} : Erreur API {r.status_code}")

        # Petite pause pour être gentil avec l'API (10 offres par seconde max)
        time.sleep(0.2)
        
        # Sauvegarde intermédiaire
        if modifications and i > 0 and i % 50 == 0:
            df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
            modifications = False
            print("   💾 Sauvegarde auto...")

    except Exception as e:
        print(f"⚠️ Erreur script : {e}")

# --- FIN ---
df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
print(f"\n🏁 FIN : {compteur_morts} expirées / {compteur_vivants} actives.")