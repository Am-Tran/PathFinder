import requests
import pandas as pd
import os
import sys
import re
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import random
from supabase import create_client

# --- CONFIGURATION ---

table_choisie = "Data_Analyst"
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, load_data

supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

CLIENT_ID = fetch_key("FT_CLIENT_ID")
CLIENT_SECRET = fetch_key("FT_CLIENT_SECRET")
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
            print(f"❌ Erreur Token : {r.status_code} : {r.text}")
            return None
    except Exception as e:
        print(f"❌ Erreur connexion : {e}")
        return None
token = get_token()
if not token:
    print("No token")
    exit()

timezone_fr = pytz.timezone('Europe/Paris')
date_actuelle = datetime.now(timezone_fr).date()
date_du_jour = pd.to_datetime(date_actuelle)

# --- CHARGEMENT ---

print("☁️ Récupération des offres actives depuis Supabase...")
filtres_ft_update = {
    "source": "France Travail",
    "statut": "Actif",
    "column": "URL, Date_Publication"
}
df_base = load_data(supabase, table_name=table_choisie, limit = None, filters=filtres_ft_update)
if df_base.empty or 'Date_Publication' not in df_base.columns:
    print("⚠️ Impossible de récupérer les données ou timeout Supabase. Arrêt du script.")
    sys.exit(1)
df_base = df_base[df_base['Date_Publication'].dt.date != date_actuelle]

print(f"🕵️ {len(df_base)} offres à vérifier dans la base de données.")
if len(df_base) == 0:
    print(" ⚠️ Il n'y a aucune offre active de FranceTravail.")
    sys.exit(0)
# ------------------------------------------------------------------------------------------------------------------------------------------------------

# --- FONCTION SCRAPING ---

def verif_url(offer_id):
    """
    Vérifie si la page publique de l'offre affiche 'Cette offre n'est plus disponible'.
    Renvoie False si l'offre est morte sur le site web.
    Renvoie True si l'offre semble encore en ligne.
    """
    url_publique = f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"
    
    # Headers pour ressembler à un vrai navigateur (évite le blocage)
    headers_browser = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # On ne télécharge que le HTML
        r_web = requests.get(url_publique, headers=headers_browser, timeout=5)
        if r_web.status_code not in [200, 404]:
            print(f"   🛡️ [DEBUG] Bloqué par le pare-feu France Travail ! Code HTTP : {r_web.status_code}")
            return True # Dans le doute, on garde
        if r_web.status_code == 200:            
            signes_mort = [                                
                "le numéro d'offre saisi n'existe pas.",                
                "(offre clôturée)",                                
                "n'est plus en ligne"                
            ]            
            
            soup = BeautifulSoup(r_web.text, 'html.parser')            
            h1_tag = soup.find("h1")

            if not h1_tag:
                # Pas de titre du tout ? Très suspect pour une offre d'emploi.
                return False
            
            titre_brut = h1_tag.get_text().lower().strip()
            titre_texte = re.sub(r'\s+', ' ', titre_brut)
            titre_texte = titre_texte.replace("’", "'").replace("´", "'")
                        
            if any(mot in titre_texte for mot in signes_mort):
                return False # OFFRE MORTE (Web)
            return True
        if r_web.status_code == 404:
            return False
                
        return True # OFFRE VIVANTE (ou erreur web, dans le doute on garde)
        
    except Exception as e:
        print(f"   ⚠️ Impossible de vérifier le web pour {offer_id}: {e}")
        return True # Dans le doute, on garde
    

# --- BOUCLE DE VÉRIFICATION ---
print("\n🚀 Démarrage de la vérification Web...")
compteur_morts = 0
compteur_vivants = 0

api_base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/"
offres_a_mettre_a_jour = []
liste_offres = df_base.to_dict(orient='records')

for i, offre in enumerate(liste_offres):
    try:
        url = offre.get('URL')
        if not url:
            print(f"⚠️  Ligne {i} : Pas d'URL trouvée.")
            continue
        offer_id = None
        # 1. On récupère l'ID propre 
        if "detail/" in url:
            offer_id = url.split("detail/")[-1].split("/")[0]            
        if not offer_id:
            print(f"⚠️  Ligne {i} : Impossible de trouver l'ID depuis l'URL ({url}).")
            continue       
        
        # Vérif API mortes
        headers = {"Authorization": f"Bearer {token}"}      
        r = requests.get(api_base_url + offer_id, headers=headers)
        est_morte = False
        if r.status_code == 401: # Token expiré
            print("🔄 Token expiré, renouvellement...")
            token = get_token()
            # L'offre ne sera pas vérifiée aujourd'hui mais elle le sera demain
            continue              
                    
        if r.status_code == 204 or r.status_code == 404:
            print(f"❌ [{i+1}] {offer_id} : EXPIRÉE")                     
            est_morte = True

        elif r.status_code == 200:                                   
            print(f"🔍 [{i+1}] {offer_id} : API 200 OK... Vérification Web...")            
            est_visible_web = verif_url(offer_id)

            if est_visible_web:
                print(f"✅ [{i+1}] {offer_id} : ACTIVE (Confirmé Web)")
                compteur_vivants += 1
            else:
                print(f"❌ [{i+1}] {offer_id} : FANTÔME (Active API mais Morte Web) -> Mise à jour : Date_Expiration")                
                est_morte = True
            
            # Petite pause pour pas se faire bannir IP par le site web
            sleep_time = random.uniform(3, 6)
            print(f"⏳ Pause de {sleep_time:.2f} sec...")
            time.sleep(sleep_time)   
              
        elif r.status_code == 429: # Trop de requêtes
            print("⏳ Trop vite ! Pause de 5 sec...")
            # L'offre ne sera pas vérifiée aujourd'hui mais elle le sera demain
            time.sleep(5)
            
        else:
            print(f"⚠️  [{i+1}] {offer_id} : Erreur API {r.status_code}")
            continue
        
        # --- PANIER DE MISE À JOUR ---
        if est_morte:
                compteur_morts += 1
                offres_a_mettre_a_jour.append({
                    "URL": url, # La clé pour que Supabase sache quelle ligne modifier
                    "Date_Expiration": datetime.now().strftime("%Y-%m-%d"), # Format ISO standard
                    "Statut": "Archivé"
                })   

        # Petite pause pour être gentil avec l'API (10 offres par seconde max)
        time.sleep(0.2)
        
        

    except Exception as e:
        print(f"⚠️ Erreur script : {e}")
    except KeyboardInterrupt:
        print("\n🛑 Arrêt manuel !")        
        break


# --- ENVOI FINAL VERS SUPABASE ---
if offres_a_mettre_a_jour:
    filtre_anti_doublons = {}
    for offre in offres_a_mettre_a_jour:
        url_de_loffre = offre['URL']
        filtre_anti_doublons[url_de_loffre] = offre
    offres_uniques = list(filtre_anti_doublons.values())
    print(f"\n📤 Envoi de {len(offres_uniques)} mises à jour vers Supabase...")
    # On envoie par paquets de 1000 (limite Supabase)
    for i in range(0, len(offres_uniques), 1000):
        batch = offres_uniques[i : i + 1000]
        supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
    print("✅ Base de données synchronisée !")
else:
    print("\n✅ Aucune offre à mettre à jour.")

print(f"\n🏁 FIN : {compteur_morts} expirées / {compteur_vivants} actives.")