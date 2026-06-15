import pandas as pd
import re
import os
import sys
import unicodedata
from supabase import create_client
import pytz
from datetime import datetime

# ================= CONFIGURATION =================
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

# =================================================

def normaliser_unicode(texte):
    if not isinstance(texte, str):
        return texte
    # 1. Normalise les caractères (ex: les accents composés)
    texte = unicodedata.normalize('NFKC', texte)
    # 2. Remplace les espaces insécables et autres joyeusetés par des espaces standards
    texte = texte.replace('\xa0', ' ').replace('\u202f', ' ')
    return texte


categories_valides = ['Stage / Alternance', 'Junior', 'Confirmé', 'Senior', 'Non spécifié']

def deduire_niveau(row):
    # Si on a déjà un niveau valide (sauf "Non spécifié" qu'on veut revérifier), on garde
    current = str(row['Niveau']).strip()
    if current in categories_valides and current != 'Non spécifié':
        return current
    
    desc = row.get('Description', '')
    if pd.isna(desc):
        desc = ""

    text_complet = (str(row['Titre']) + " " + str(row['Description'])).lower()
    titre = row['Titre'].lower()

    # 1. ANALYSE TITRE (Les mots-clés forts)
    
    # STAGE / ALTERNANCE
    if any(x in titre for x in ['stage', 'intern', 'alternan', 'apprenti']): 
        return "Stage / Alternance"
    
    # SENIOR (Inclut désormais les Leads, Managers, Directeurs, Experts)
    if any(x in titre for x in ['senior', 'sr.', 'lead', 'manager', 'head of', 'directeur', 'vp', 'expert']): 
        return "Senior"
    
    # CONFIRMÉ
    if any(x in titre for x in ['confirmé', 'confirmed', 'medior', 'intermédiaire']): 
        return "Confirmé"
    
    # JUNIOR
    if any(x in titre for x in ['junior', 'débutant', 'graduate', 'associate']): 
        return "Junior"
    
    # 2. ANALYSE ANNÉES (Regex v3)
    # Regex A : "5 ans" ou "5 years"
    match_classique = re.search(r'(\d+)[\s\-\/àa]*(?:ans|an|year|année)', text_complet)
    # Regex B : "Expérience : 5"
    match_label = re.search(r'(?:minimum|expérience|experience)[\s\w\']*:?\s*(\d+)', text_complet)

    match = match_label if match_label else match_classique

    if match:
        try:
            annees = int(match.group(1))
            if 0 <= annees <= 15: 
                if annees <= 2: return "Junior"
                elif 2 < annees < 5: return "Confirmé" 
                elif annees >= 5: return "Senior"
        except:
            pass

    # 3. Mots-clés sémantiques description
    if any(x in text_complet for x in ['forte expérience', 'significative', 'solid experience']): return "Confirmé"
    if any(x in text_complet for x in ['première expérience', 'débutant accepté']): return "Junior"

    # 4. Si on ne sait pas -> On reste honnête
    return "Non spécifié"

# -----------------------------------------------------------------------------------------------------------------------------

def extraire_salaire_wttj(infos_str):
    """ Extrait le salaire de la colonne fourre-tout de WTTJ """
    if pd.isna(infos_str): return None
    # Regex pour chercher "45k", "40-50k", "45 k€"
    # On nettoie un peu la chaîne avant
    txt = str(infos_str).lower().replace(',', '.')
    
    match_k = re.search(r'(\d{2,3})[ ]?k', txt)
    if match_k:
        val = float(match_k.group(1))
        # Filtre anti-bruit (évite de prendre "2 jours" pour 2k salaire)
        if 20 <= val <= 150:
            return int(val * 1000)
    return None

# -----------------------------------------------------------------------------------------------------------------------------

def extraire_contrat_wttj(infos_str):
    """ Extrait le contrat de la desciption """
    txt = str(infos_str).upper()
    if "CDI" in txt: return "CDI"
    if "CDD" in txt: return "CDD"
    if "STAGE" in txt: return "Stage"
    if "ALTERNANCE" in txt or "APPRENTISSAGE" in txt: return "Alternance"
    if "FREELANCE" in txt or "INDÉPENDANT" in txt: return "Freelance"
    return "Non spécifié"

# -----------------------------------------------------------------------------------------------------------------------------

def extraire_ville_wttj(infos_str):
    """ Extrait la ville de la desciption """
    if not isinstance(infos_str, str):
        return "Non spécifié"    
    
    # 1. On découpe en lignes et on enlève les espaces vides
    lignes = [l.strip() for l in infos_str.split('\n') if l.strip()]
    
    # 2. Mots qui indiquent que ce n'est PAS une ville
    mots_interdits = ["télétravail", "salaire", "visibilité", "contenu", "résumé", "poste", "remote", "mois"]
    contrats = ["stage", "alternance", "cdi", "cdd", "apprentissage", "freelance", "intérim", "interim"]    

    for i, ligne in enumerate(lignes):
        ligne_lower = ligne.lower()
        
        # On cherche la ligne qui EST exactement un type de contrat
        if any(c == ligne_lower for c in contrats):
            
            # On va regarder les lignes suivantes (max 2 lignes après)
            for offset in [1, 2]:
                index_suivant = i + offset
                
                if index_suivant < len(lignes):
                    candidat = lignes[index_suivant]
                    candidat_lower = candidat.lower()
                    
                    # CONDITION : Pas de chiffres (ton critère) + Pas de mots poubelles
                    # On vérifie aussi que ce n'est pas un autre contrat par erreur
                    if not any(char.isdigit() for char in candidat) and \
                       not any(p in candidat_lower for p in mots_interdits) and \
                       candidat_lower not in contrats:
                        
                        # Si ça commence par une Majuscule, c'est notre ville
                        if re.match(r"^[A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ]", candidat):
                            return candidat
    
    return "Non spécifié"

# def corriger_ville(row):
#     ville_actuelle = str(row.get('Ville', '')).lower()
    
#     # Si la ville est une erreur de WTTJ ou qu'elle est vide
#     if "visibilité" in ville_actuelle or ville_actuelle in ["", "none", "non spécifié"]:
#         return extraire_ville_wttj(row['Description_Complete'])
    
#     # Sinon, on garde la ville d'origine (Paris, Lyon, etc.)
#     return row['Ville']

# -----------------------------------------------------------------------------------------------------------------------------

def nettoyer_texte(texte):
    if pd.isna(texte) or texte == "":
        return None
    return " ".join(str(texte).split())

# -----------------------------------------------------------------------------------------------------------------------------

def main():
    # --- CHARGEMENT ---

    print("☁️ Récupération des offres actives depuis Supabase...")
    filters_wttj_clean= {
    "source": "Welcome to the Jungle",
    "statut": "Collecte",
    "only_active": True
    }
    df = load_data(supabase, table_name=table_choisie, limit=None, filters = filters_wttj_clean)    

    # df = df_base[
    #     (df_base['Source'] == 'Welcome to the Jungle') & 
    #     (df_base['Date_Expiration'].isna()) &
    #     (df_base['Date_Publication'] == date_actuelle)
    # ].copy()

    print(f"🕵️ {len(df)} offres à vérifier dans la base de données.")
    if len(df) == 0:
        print(" ⚠️ Il n'y a aucune offre active de WTTJ.")
        exit()
    
    for col in ['Titre', 'Description', 'Ville']:
        if col in df.columns:
            df[col] = df[col].apply(normaliser_unicode)   
    

    # Nettoyage
    df['Titre'] = df['Titre'].fillna('Non spécifié').astype(str)      
    df['Description'] = df['Description'].apply(nettoyer_texte)
    df['Entreprise'] = df['Entreprise'].str.upper().str.strip()
    # df['Source'] = 'Welcome to the Jungle'

    print("⚙️ Extraction des villes manquantes...")
    mask_ville_manquante = (
    (df['Ville'].isna()) | 
    (df['Ville'] == "") |
    (df['Ville'].str.contains("visibilité", case=False, na=True)) |
    (df['Ville'] == "Non spécifié")
    )
    df.loc[mask_ville_manquante, 'Ville'] = df.loc[mask_ville_manquante, 'Description'].apply(extraire_ville_wttj) 


    print("⚙️ Extraction Salaires & Contrats...")
    if 'Salaire_Annuel' not in df.columns:
        df['Salaire_Annuel'] = None
    mask_contrat = df['Type_Contrat'].isna() | (df['Type_Contrat'] == "Non spécifié") | (df['Type_Contrat'] == "")
    if mask_contrat.any():
        df.loc[mask_contrat, 'Type_Contrat'] = df.loc[mask_contrat, 'Description'].apply(extraire_contrat_wttj)
    mask_salaire = df['Salaire_Annuel'].isna()
    if mask_salaire.any():
        df.loc[mask_salaire, 'Salaire_Annuel'] = df.loc[mask_salaire, 'Description'].apply(extraire_salaire_wttj)       
        
    print("🧠 Calcul des niveaux...")
    if 'Niveau' not in df.columns:
        df['Niveau'] = 'Non spécifié'
    else:
        df['Niveau'] = df['Niveau'].fillna('Non spécifié')
    df['Niveau'] = df.apply(deduire_niveau, axis=1)
    df['Statut'] = "Prep"

    print("\n🚀 Préparation des données pour Supabase...")   
    colonnes_supabase = [
        "Titre", "Entreprise", "Ville", "Type_Contrat", 
        "Salaire_Annuel", "Description", "Date_Publication", 
        "Date_Expiration", "Source", "URL", "Niveau", "Statut"
    ]

    df_clean = df[colonnes_supabase].copy()
    for col in ["Date_Publication", "Date_Expiration"]:
        if col in df_clean.columns:            
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').dt.strftime('%Y-%m-%d')
    df_clean = df_clean.astype(object).where(pd.notna(df_clean), None)
    
    print("\n🚀 Envoi des données nettoyées vers Supabase...")
    
    erreurs = 0
    offres_sauvegardees = 0
    liste_donnees = df_clean.to_dict(orient='records')
    
    for i in range(0, len(liste_donnees), 1000):
        batch = liste_donnees[i : i + 1000]
        try:
            supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
            offres_sauvegardees += len(batch)
        except Exception as e:
            erreurs += 1
            if erreurs == 1:
                print("\n🚨 --- ALERTE ROUGE : DÉTAIL DU CRASH --- 🚨")
                print(f"❌ Le message de Supabase : {e}")
                print(f"📦 Le paquet refusé : {batch[0]}")
                print(f"🆔 L'ID ciblé : {batch[0].get('URL', 'URL INTROUVABLE')}")
                print("-------------------------------------------\n")

    print(f"\n✅ Nettoyage terminé ! {offres_sauvegardees} offres mises à jour.")
    if erreurs > 0:
        print(f"⚠️ Il y a eu {erreurs} erreurs lors de l'envoi.")

if __name__ == "__main__":
    main()