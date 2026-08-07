import os
import sys
import requests
from datetime import datetime
from supabase import create_client

# --- CONFIGURATION ---
table_choisie = "Data_Analyst"

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, load_data, mapping_metier, upsert_data

supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
if not supabase_url or not supabase_key:
    print("❌ ERREUR : Clés Supabase introuvables.")
    sys.exit(1)
supabase = create_client(supabase_url, supabase_key)

print("📥 Récupération du stock actuel pour éviter les doublons...")
filters_apec_crawler= {
    "source": "APEC",
    "statut": "Actif",
    "column": "URL"
}
df_base = load_data(supabase, table_name=table_choisie, limit=None, filters=filters_apec_crawler)
ids_connus = set()
if not df_base.empty:
    ids_connus = set(df_base['URL'].dropna())
print(f"🛡️ {len(ids_connus)} offres APEC déjà en base. Elles seront ignorées.")
print("🚀 Lancement du Crawler APEC (Mode API Turbo)...")

# --- MAPPING METIER ---

def standardiser_metier(titre):
    if not titre: return "Data Analyst"
    titre_lower = titre.lower()
    for cle, metier in mapping_metier.items():
        if cle.lower() in titre_lower:
            return metier
    return "Data Analyst"

# --- PARAMÈTRES DE L'API ---
URL_API = "https://www.apec.fr/cms/webservices/rechercheOffre"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.apec.fr"
}

urls_trouvees_ce_jour = []
urls_uniques_session = set() # Sécurité anti-doublons
SEUIL_TOLERANCE = 50 # On peut se permettre de checker plus loin vu la vitesse

# On boucle sur nos mots-clés principaux
for recherche in ["data analyst", "business analyst", "data scientist"]:
    print(f"\n🔎 Recherche pour le mot-clé : '{recherche.upper()}'")
    start_index = 0
    compteur_doublons = 0
    
    while True:
        payload = {
            "typesConvention": ["143684", "143685", "143686", "143687", "143706"],
            "typeClient": "CADRE",
            "sorts": [{"type": "DATE", "direction": "DESCENDING"}], # On trie par date pour avoir les plus récentes !
            "pagination": {"range": 100, "startIndex": start_index}, # On demande 100 offres d'un coup
            "activeFiltre": True,
            "motsCles": recherche
        }
        
        response = requests.post(URL_API, headers=HEADERS, json=payload)
        
        if response.status_code != 200:
            print(f"❌ Erreur API ({response.status_code}). Arrêt de la boucle.")
            break
            
        data = response.json()
        resultats = data.get('resultats', [])
        
        if not resultats:
            print("🏁 Plus aucune offre retournée par l'API.")
            break
            
        nouveautés_page = 0
        mapping_contrat = {
            101888: "CDI",
            101887: "CDD",
            20053: "Alternance",
            101930: "Intérim"
        }

        for offre in resultats:
            numero = offre.get('numeroOffre')
            if not numero:
                continue
                
            full_url = f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{numero}"
            titre = offre.get('intitule', None)
            code_contrat = offre.get('typeContrat')
            metier = standardiser_metier(titre)
            contrat_texte = mapping_contrat.get(code_contrat, None)            
            date_brut = offre.get('datePublication', None)
            date_publication = date_brut.split('T')[0] if date_brut else None # Déjà au format "YYYY-MM-DD"            
            
            if (full_url not in ids_connus) and (full_url not in urls_uniques_session):
                urls_uniques_session.add(full_url)
                
                # On récupère direct les infos bonus fournies par l'API !
                urls_trouvees_ce_jour.append({
                    "URL": full_url,
                    "Source": "APEC",
                    "Statut": "Cible",
                    "Metier": metier,
                    "Titre": titre,
                    "Entreprise": offre.get('nomCommercial', 'Non affiché'),
                    "Ville": offre.get('lieuTexte', 'Inconnu'),
                    "Salaire_Annuel": offre.get('salaireTexte', 'Non affiché'),
                    "Type_Contrat": contrat_texte,
                    "Date_Publication": date_publication
                })
                nouveautés_page += 1
                compteur_doublons = 0
            else:
                compteur_doublons += 1
                
        print(f"✅ {len(resultats)} analysées -> {nouveautés_page} nouvelles retenues.")
        
        if len(resultats) < 100:
            print("🏁 Dernière page atteinte.")
            break
            
        if compteur_doublons >= SEUIL_TOLERANCE:
            print(f"🛑 Trop de doublons ({compteur_doublons}), on passe au mot-clé suivant.")
            break
            
        start_index += 100

# --- SAUVEGARDE SUPABASE ---
if urls_trouvees_ce_jour:
    print(f"\n📤 Envoi de {len(urls_trouvees_ce_jour)} nouvelles offres vers Supabase...")
    upsert_data(supabase, table_choisie, urls_trouvees_ce_jour)