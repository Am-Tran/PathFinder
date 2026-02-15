import pandas as pd
import re
import os
import sys

# ================= CONFIGURATION =================

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))


INPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_wttj_full.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "clean", "offres_wttj_clean.csv")

if project_root not in sys.path:
    sys.path.append(project_root)
from utils import sauvegarde_securisee

# =================================================
categories_valides = ['Stage / Alternance', 'Junior', 'Confirmé', 'Senior', 'Non spécifié']

def deduire_niveau(row):
    # Si on a déjà un niveau valide (sauf "Non spécifié" qu'on veut revérifier), on garde
    current = str(row['Niveau']).strip()
    if current in categories_valides and current != 'Non spécifié':
        return current

    text_complet = (str(row['Titre']) + " " + str(row['Description_Complete'])).lower()
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
    """ Extrait le contrat de la colonne fourre-tout """
    txt = str(infos_str).upper()
    if "CDI" in txt: return "CDI"
    if "CDD" in txt: return "CDD"
    if "STAGE" in txt: return "Stage"
    if "ALTERNANCE" in txt or "APPRENTISSAGE" in txt: return "Alternance"
    if "FREELANCE" in txt or "INDÉPENDANT" in txt: return "Freelance"
    return "Non spécifié"

# -----------------------------------------------------------------------------------------------------------------------------

def nettoyer_texte(texte):
    if pd.isna(texte): return ""
    return " ".join(str(texte).split())

# -----------------------------------------------------------------------------------------------------------------------------

def main():
    print(f"📂 Chargement de {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print("❌ Fichier introuvable.")
        return
    
    # Filtre offres actives
    mask_active = df['Date_Expiration'].isna() | (df['Date_Expiration'] == "") | (df['Date_Expiration'] == "nan")
    df = df[mask_active].copy()
    print(f"💎 Offres actives : {len(df)}")

    # Nettoyage
    df['Titre'] = df['Titre'].astype(str).fillna('')
    df['Description_Propre'] = df['Description_Complete'].apply(nettoyer_texte)
    df['Entreprise'] = df['Entreprise'].str.upper().str.strip()
    df['Source'] = 'Welcome to the Jungle'

    print("⚙️ Extraction Salaires & Contrats...")
    if 'Experience_Salaire_Infos' in df.columns:
        df['Salaire_Annuel_Estime'] = df['Experience_Salaire_Infos'].apply(extraire_salaire_wttj)
        df['Type_Contrat'] = df['Experience_Salaire_Infos'].apply(extraire_contrat_wttj)
    else:
        print("⚠️ Colonne 'Experience_Salaire_Infos' introuvable. Pas de salaire extrait.")
        df['Salaire_Annuel_Estime'] = None
        df['Type_Contrat'] = "Non spécifié"
    
    print("🧠 Calcul des niveaux...")
    if 'Niveau' not in df.columns:
        df['Niveau'] = 'Non spécifié'
    else:
        df['Niveau'] = df['Niveau'].fillna('Non spécifié')
    df['Niveau'] = df.apply(deduire_niveau, axis=1)

    # Tes catégories officielles    
    cols_finales = [
        'Titre', 'Entreprise', 'Ville', 'Type_Contrat', 
        'Salaire_Annuel_Estime', 'Niveau', 'Description_Propre', 
        'URL', 'Date_Publication','Date_Expiration', 'Source'
    ]
    for col in cols_finales:
        if col not in df.columns:
            df[col] = None

    df_clean = df[cols_finales]

    # Sauvegarde
    #df.to_csv(OUTPUT_CSV, index=False)
    sauvegarde_securisee(df_clean, OUTPUT_CSV)
    
    print("-" * 40)
    print(f"✅ Terminé ! {OUTPUT_CSV} mis à jour.")
    print("Nouvelle répartition :")
    print(df['Niveau'].value_counts())
    print("-" * 40)

if __name__ == "__main__":
    main()