import pandas as pd
import os
import re
import sys
from supabase import create_client
import pytz
from datetime import datetime

# --- 1. CONFIGURATION ---
table_choisie = "Data_Analyst"

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)
from utils import fetch_key, load_data

print("☁️ Initialisation de Supabase...")
supabase_url = fetch_key("SUPABASE_URL")
supabase_key = fetch_key("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)


timezone_fr = pytz.timezone('Europe/Paris')
date_actuelle = datetime.now(timezone_fr).date()
date_du_jour = pd.to_datetime(date_actuelle)

# --- 2. CHARGEMENT ---
print("📥 Récupération des offres France Travail depuis Supabase...")
filtres_ft = {
    "source": "France Travail",
    "statut": "Collecte"
}
df = load_data(supabase, table_name=table_choisie, limit = None, filters=filtres_ft)
if df.empty:
    print("✨ La base de données est vide.")
    sys.exit(0)


if df.empty:
    print("✨ Aucune offre France Travail trouvée dans la base.")
    sys.exit(0)
print(f"✅ Chargé : {len(df)} offres brutes.")

# --- 3. FONCTIONS DE NETTOYAGE ---

def nettoyer_salaire(texte):
    """
    Nettoyage intelligent qui gère : Annuel, Mensuel, Taux Horaire, et TJM (Freelance).
    Renvoie un Salaire ANNUEL estimé (int).
    """
    if pd.isna(texte) or "Non affiché" in str(texte) or "Confidentiel" in str(texte):
        return None
    
    txt = str(texte).lower().replace(' ', '').replace(',', '.') # On standardise
    
    # 1. On cherche un nombre (y compris décimaux comme 11.65)
    # On cherche d'abord les gros chiffres (> 1000)
    match_gros = re.search(r'(\d{4,6})', txt)
    # On cherche les petits chiffres (pour TJM ou Horaire)
    match_petit = re.search(r'(\d{2,3}(?:\.\d+)?)', txt) 

    valeur = 0
    type_detecte = "Inconnu"

    # --- SCÉNARIO 1 : C'est clairement Annuel ---
    if "annuel" in txt or "an" in txt:
        if match_gros:
            valeur = float(match_gros.group(1))
            type_detecte = "Annuel"

    # --- SCÉNARIO 2 : C'est Mensuel ---
    elif "mensuel" in txt or "mois" in txt:
        if match_gros: # Ex: 2500
            valeur = float(match_gros.group(1)) * 12
            type_detecte = "Mensuel"
        elif match_petit: # Cas rare
            valeur = float(match_petit.group(1)) * 12
            type_detecte = "Mensuel"

    # --- SCÉNARIO 3 : C'est un Taux Horaire (SMIC, Intérim) ---
    elif "horaire" in txt or "heure" in txt:
        if match_petit:
            # 11.65€/h * 151.67h * 12 mois
            valeur = float(match_petit.group(1)) * 151.67 * 12
            type_detecte = "Horaire"

    # --- SCÉNARIO 4 : C'est un TJM (Freelance / Jour) ---
    elif "jour" in txt or "tjm" in txt or "j/" in txt:
        if match_petit: # Ex: 400
            valeur = float(match_petit.group(1)) * 220 # ~220 jours ouvrés
            type_detecte = "TJM"
        elif match_gros and float(match_gros.group(1)) < 1000: # Ex: 500 écrit comme 500
             valeur = float(match_gros.group(1)) * 220
             type_detecte = "TJM"

    # --- SCÉNARIO 5 : Pas de mot clé, on devine par la taille du chiffre ---
    else:
        if match_gros:
            v = float(match_gros.group(1))
            if v > 15000: # Probablement annuel
                valeur = v
                type_detecte = "Deviné Annuel"
            elif 1200 < v < 8000: # Probablement mensuel
                valeur = v * 12
                type_detecte = "Deviné Mensuel"

    # --- SÉCURITÉ / FILTRE ---
    # On rejette si c'est absurde (< SMIC mi-temps ou > PDG du CAC40 pour un analyste)
    # SMIC Annuel Brut ~21 203€. On accepte à partir de 15k (temps partiel/stage)
    if valeur < 15000 or valeur > 200000:
        return None
    
    # Sécurité anti-année : si le chiffre est entre 1980 et 2030 ET qu'on a "Deviné", on rejette
    if 1980 <= valeur <= 2030 and "Deviné" in type_detecte:
        return None

    return int(valeur)

# def extraire_dept(texte):
#     # Entrée: "92 - Courbevoie" -> Sortie: "92"
#     if pd.isna(texte): return "Inconnu"
#     if " - " in str(texte):
#         return str(texte).split(" - ")[0].strip()
#     return "Inconnu"

def extraire_ville(texte):
    # Entrée: "92 - Courbevoie" -> Sortie: "Courbevoie"
    if pd.isna(texte): return "Inconnu"
    ville_brute = str(texte)
    if " - " in str(ville_brute):
        parties = str(ville_brute).split(" - ")
        if len(parties) > 1:
            ville_brute = parties[1]
    regex_arrondissements = r'(?i)\s*(?:cedex\s*)?\d{1,2}(?:er|e|ème|eme)?(?:\s*arrondissement)?\b'
    ville_propre = re.sub(regex_arrondissements, '', ville_brute)
    ville_propre = re.sub(r'[\s\-,]+$', '', ville_propre).strip()
    if not ville_propre:
        return "Inconnu"
    return ville_propre

def nettoyer_date(texte):
    # Entrée: "2026-01-13T14:48..." -> Sortie: "2026-01-13"
    if pd.isna(texte): return None
    return str(texte).split('T')[0]

def nettoyer_texte(texte):
    # Enlève les \n et les espaces multiples
    if pd.isna(texte): return ""
    clean = str(texte).replace('\n', ' ').replace('\r', ' ')
    return " ".join(clean.split())


# --- 4. APPLICATION DU NETTOYAGE ---

print("⚙️ Traitement des colonnes...")

# Date
df['Date_Publication'] = df['Date_Publication'].apply(nettoyer_date)

# Localisation
#df['Departement'] = df['Ville'].apply(extraire_dept)
df['Ville'] = df['Ville'].apply(extraire_ville)

#Titre
df['Titre'] = df['Titre'].astype(str).str.replace('"', '', regex=False).str.strip()
df['Entreprise'] = df['Entreprise'].astype(str).str.replace('"', '', regex=False).str.strip()

# Salaire
df['Salaire_Annuel'] = df['Salaire_Annuel'].apply(nettoyer_salaire)

# Description (Pour lecture facile)
df['Description'] = df['Description'].apply(nettoyer_texte)

# Date expiration
if 'Date_Expiration' not in df.columns:
    df['Date_Expiration'] = None
else:
    # On s'assure que c'est propre (pas de "nan" string)
    df['Date_Expiration'] = df['Date_Expiration'].apply(nettoyer_date)

df["Statut"] = "Prep"

# --- 5. STATISTIQUES RAPIDES ---
nb_salaires = df['Salaire_Annuel'].notna().sum()
moyenne_salaire = df['Salaire_Annuel'].mean()

print(f"\n📊 Résumé après nettoyage :")
print(f"   - Offres avec salaire détecté : {nb_salaires} / {len(df)}")
if nb_salaires > 0:
    print(f"   - Salaire moyen estimé : {moyenne_salaire:.0f} €/an")

# --- 6. SAUVEGARDE ---
print("\n🚀 Envoi des données nettoyées vers Supabase...")
colonnes_supabase = [
    "Titre", "Entreprise", "Ville", "Type_Contrat", 
    "Salaire_Annuel", "Description", "Date_Publication", 
    "Date_Expiration", "Source", "URL", "Statut", "Metier"
]
df_clean = df[colonnes_supabase].copy()
df_clean = df_clean.astype(object).where(pd.notna(df_clean), None)

erreurs = 0
liste_donnees = df_clean.to_dict(orient='records')

for i in range(0, len(liste_donnees), 1000):
    batch = liste_donnees[i : i + 1000]
    try:
        # Le upsert mettra à jour la ligne entière d'un seul coup grâce à la clé "URL"
        supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
    except Exception as e:
        erreurs += 1
        if erreurs == 1:
            print("\n🚨 --- ALERTE ROUGE : DÉTAIL DU CRASH --- 🚨")
            print(f"❌ Le message de Supabase : {e}")
            print(f"📦 Le paquet refusé : {batch[0]}")
            print(f"🆔 L'ID ciblé : {batch[0].get('URL', 'URL INTROUVABLE')}")
            print("-------------------------------------------\n")

print(f"\n✅ Nettoyage terminé ! {max(0, len(liste_donnees) - (erreurs*1000))} offres passées au statut 'Prep'.")
if erreurs > 0:
    print(f"⚠️ Il y a eu {erreurs} erreurs lors de l'envoi.")