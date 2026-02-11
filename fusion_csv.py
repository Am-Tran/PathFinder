import pandas as pd
import os
from datetime import datetime
import re

# ------------------------------------------------------------------------------------------------------------------------------------------------------

# region 1. --- CONFIGURATION ---

# On se place dynamiquement
current_dir = os.path.dirname(os.path.abspath(__file__))
# Si le script est dans un sous-dossier, on remonte. Sinon on reste là.
if "scrapers" in current_dir:
    project_root = os.path.dirname(os.path.dirname(current_dir)) # Remonte 2 fois (scrapers/nom_dossier)
    if "PathFinder" not in project_root: # Sécurité si structure différente
         project_root = os.path.dirname(current_dir)
else:
    project_root = current_dir

# Chemins des fichiers PROPRES
FILE_FT = os.path.join(project_root, "data", "clean", "offres_francetravail_clean.csv")
FILE_WTTJ = os.path.join(project_root, "data", "clean", "offres_wttj_clean.csv")
FILE_APEC = os.path.join(project_root, "data", "clean", "offres_apec_clean.csv")

OUTPUT_CSV = os.path.join(project_root, "data", "clean", "global_job_market.csv")

# Création du dossier final s'il n'existe pas
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

print("🧪 Démarrage de la fusion...")
# endregion

# ======================================================================================================================================================

#region 2. --- FONCTIONS ---

def normaliser_date(date_str):
    """Force le format AAAA-MM-JJ pour éviter les bugs Streamlit"""
    if pd.isna(date_str) or date_str == "" or str(date_str).lower() == "nan":
        return None
    date_str = str(date_str).strip()
    try:
        # Tente le format français (31/01/2025)
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Tente le format déjà ISO (2025-01-31)
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return None
# --------------------------------------------------        

def extraire_annees_exp(description):
    """
    Extrait le nombre d'années d'expérience du texte.
    Renvoie un entier ou None.
    """
    if pd.isna(description): return None
    description = description.lower()

    annees = None
    #pattern_a = r"(\d{1,2})\s*?(?:-|\s)?\s*?(?:ans|années|years|year).*?(?:exp|expérience|experience)"  
    pattern_a = r"(\d{1,2})\s*(?:-|à)?\s*(?:\d{1,2})?\s*(?:ans|années|years).{0,20}exp"  
    match_a = re.search(pattern_a, description)
    #pattern_b = r"(?:exp|expérience|experience).{0,20}?(\d{1,2})"
    pattern_b = r"exp.{0,20}(\d{1,2})\s*(?:ans|années|years)"
    match_b = re.search(pattern_b, description)

    if match_a:
        try: annees = int(match_a.group(1))
        except ValueError: pass
    elif match_b:
        try: annees = int(match_b.group(1))
        except ValueError: pass
        
    # Filtre de sécurité pour éviter les chiffres aberrants
    if annees is not None and (annees > 15 or annees < 0):
        return None
        
    return annees
# --------------------------------------------------

def nettoyer_contrats(df):
    """
    Nettoie et standardise la colonne Type_Contrat.

    """
    print("✨ Nettoyage et Harmonisation des Contrats...")
    
    # 1. Nettoyage de base : String + Strip + Capitalize
    df["Type_Contrat"] = df["Type_Contrat"].astype(str).str.strip().str.capitalize()

    # 2. Dictionnaire de traduction (Codes -> Libellés propres)
    corrections_contrat = {
        "Mis": "Intérim",
        "Lib": "Freelance",
        "Fra": "Freelance",
        "Ind": "Freelance",
        "Din": "CDI Intérimaire",
        "Cdi": "CDI",
        "Cdd": "CDD",
        "Ddi": "CDD",  # Contrat à Durée Déterminée d'Insertion
        "Cui": "CDD",  # Contrat Unique Insertion
        "Cae": "CDD",  # Contrat d'accompagnement dans l'emploi
        "Stage": "Stage / Alternance",
        "Alternance": "Stage / Alternance",
        "Apprentissage": "Stage / Alternance",
        "Contrat pro": "Stage / Alternance",
        "Stage / alternance": "Stage / Alternance",
        "Professionalisation": "Stage / Alternance",
        "Nan": "Non spécifié"
    }
    df["Type_Contrat"] = df["Type_Contrat"].replace(corrections_contrat)



    # --- PRÉPARATION DES MASQUES (Les "Détecteurs") ---

    # A. DÉTECTEUR CDI & CDD
    mask_source_cdi = df['Type_Contrat'] == "CDI"
    mask_titre_cdi = df['Titre'].astype(str).str.contains(r"\bCDI\b", case=False, regex=True, na=False)
    mask_is_cdi_officiel = mask_source_cdi | mask_titre_cdi

    mask_source_cdd = df['Type_Contrat'] == "CDD"
    mask_titre_cdd = df['Titre'].astype(str).str.contains(r"\bCDD\b", case=False, regex=True, na=False)
    mask_is_cdd_officiel = mask_source_cdd | mask_titre_cdd

    # A. DÉTECTEUR SENIOR / MANAGER (Liste Noire pour Stage)
    regex_titre_senior = r"\b(?:senior|lead|manager|directeur|head of|chef de projet|international|freelance|expert|responsable)\b"
    mask_titre_senior = df['Titre'].astype(str).str.contains(regex_titre_senior, case=False, regex=True, na=False)

    # B. DÉTECTEUR ÉTUDIANT
    regex_etudiants = r"\b(?:stage|stagiaire|internship|alternance|alternant|apprentissage|contrat pro|pfe)\b"    
    mask_titre_etudiant = df['Titre'].astype(str).str.contains(regex_etudiants, case=False, regex=True, na=False)

    # C. DÉTECTEUR CDI CACHÉ (Le plus complexe)
    # 1. Inclusion : On cherche "CDI" ou "Durée indéterminée"
    regex_cdi = r"\b(?:CDI|durée indéterminée)\b"
    mask_contient_cdi = df['Description'].astype(str).str.contains(regex_cdi, case=False, regex=True, na=False)

    # 2. Exclusion : On fuit "possibilité de CDI", "vue sur CDI", etc.
    #regex_cdi_piege = r"(?:possibilit|perspective|débouch|vue|objectif|finalité|suite|embauche|stage|futur|après).{0,30}\bCDI\b"
    #mask_cdi_piege = df['Description'].astype(str).str.contains(regex_cdi_piege, case=False, regex=True, na=False)

    # 3. Résultat : C'est un VRAI CDI Caché
    mask_vrai_cdi_cache = mask_contient_cdi 
    #& (~mask_cdi_piege)


    # --- APPLICATION DES RÈGLES (Ordre Chronologique) ---
    
    df.loc[mask_titre_etudiant, 'Type_Contrat'] = "Stage / Alternance"
    # On écrase "Stage" par CDI si...
    # - La source dit CDI (et ce n'est pas "Stagiaire" explicite)
    # - OU C'est un Senior (Titre)
    # - OU On a trouvé un CDI propre dans la description
    
    mask_force_cdi = (
        (mask_is_cdi_officiel & ~mask_titre_etudiant) |  # Source CDI (sauf si titre "Stagiaire")
        mask_titre_senior |                              # Senior / Expert
        mask_vrai_cdi_cache                              # Description CDI clean
    )
    
    # On applique le CDI uniquement si ce n'est pas déjà détecté comme Freelance    
    mask_final_cdi = mask_force_cdi & (df['Type_Contrat'] != "Freelance")
    
    if mask_final_cdi.sum() > 0:
        df.loc[mask_final_cdi, 'Type_Contrat'] = "CDI"
    
    # 3. Correction Freelance (Le dernier mot)
    regex_freelance = r"\b(?:freelance|indépendant|independant|free-lance|b2b)\b"
    mask_freelance = df['Titre'].astype(str).str.contains(regex_freelance, case=False, regex=True, na=False)
    df.loc[mask_freelance, 'Type_Contrat'] = "Freelance"
    df.loc[mask_is_cdd_officiel, 'Type_Contrat'] = "CDD"

    return df    
# --------------------------------------------------

def determiner_niveau(row):
    """
    Déduit le niveau d'expérience (Etudiant, Junior, Confirmé, Senior) 
    basé sur le salaire (distingue idf des autres zones) et les mots-clés du titre.
    """
    titre = str(row['Titre']).lower() if pd.notna(row['Titre']) else ""
    # desc = str(row['Description']).lower() if pd.notna(row['Description']) else "" 
    lieu = str(row['Ville']).lower() if pd.notna(row['Ville']) else "" 
    salaire = row['Salaire_Annuel']
    contrat = str(row['Type_Contrat']).lower() if pd.notna(row['Type_Contrat']) else ""
    annees = row['Annees_Exp']

    # 1. Extraction des années
    
    if pd.notna(annees):
        if annees > 5: return "Senior"
        if annees > 2: return "Confirmé"

    # 2. Détection des stages ---
    if "Stage / Alternance" in contrat:
        return "En formation"
    
    if any(k in titre for k in ["senior", "lead", "manager", "head of", "directeur", "expert", "principal", "vp", "chef"]):
        return "Senior"       

    # 3. Définition des seuils selon la géographie    
    # Zone A : Paris & IDF
    mots_idf = ['paris', 'île-de-france', 'ile-de-france', 'boulogne', 'courbevoie', 'la défense', '92', '75', '93', '94']
    
    # Zone B : Grandes Métropoles (Marché dynamique)
    mots_metropoles = ['lyon', 'toulouse', 'bordeaux', 'nantes', 'lille', 'aix', 'marseille', 'nice', 'rennes', 'sophia', 'antipolis']

    if any(m in lieu for m in mots_idf):
        # ZONE PARIS
        seuil_junior = 40000
        seuil_senior = 60000
    elif any(m in lieu for m in mots_metropoles):
        # ZONE GRANDES VILLES (Intermédiaire)
        seuil_junior = 37000  # Un junior à Lyon peut toucher 36-37k
        seuil_senior = 52000  # 52k à Bordeaux, c'est clairement un profil Senior
    else:
        # ZONE RESTE DE LA FRANCE
        seuil_junior = 34000
        seuil_senior = 48000

    # --- VERDICT DU SALAIRE ---
    if pd.notna(salaire) and salaire > 0:
        if salaire <= seuil_junior:
            return "Junior"
        elif seuil_junior < salaire < seuil_senior:
            return "Confirmé"
        else:
            return "Senior"    
    
    # --- PAR DEFAUT ---
    if pd.notna(annees) and annees <= 2:
        return "Junior"
    
    # --- FALLBACK : ANALYSE TEXTUELLE ---
    # (Titre)
    
    if any(k in titre for k in ["junior", "débutant", "assistant", "graduate"]):
        return "Junior"
    if "confirmé" in titre:
        return "Confirmé"    

    return "Non spécifié"
# --------------------------------------------------

def detecter_rqth(text):
    if pd.isna(text): return False
    keywords = ["rqth", "handicap", "situation de handicap", "entreprise adaptée"]
    return any(k in text.lower() for k in keywords)

# endregion
# ======================================================================================================================================================

# region 3. --- CHARGEMENT ET STANDARDISATION ---

dataframes = []
cols_globales = [
    "Titre", "Entreprise", "Ville", "Salaire_Annuel", "Type_Contrat", 
    "Teletravail", "Date_Publication", "Date_Expiration", "Source", "URL", "Description"
]


# --- CHARGEMENT DE L'HISTORIQUE ---
if os.path.exists(OUTPUT_CSV):
    print(f"📜 Chargement de l'historique : {OUTPUT_CSV}")
    try:
        df_hist = pd.read_csv(OUTPUT_CSV)
        # On normalise aussi l'historique pour être sûr
        df_hist["Date_Publication"] = df_hist["Date_Publication"].apply(normaliser_date)
        df_hist["Date_Expiration"] = df_hist["Date_Expiration"].apply(normaliser_date)
        dataframes.append(df_hist)
    except:
        print("⚠️ Historique illisible, on repart de zéro.")

# --------------------------------------------------

# --- A. FRANCE TRAVAIL ---
if os.path.exists(FILE_FT):
    print("🔹 Chargement France Travail...")
    df_ft = pd.read_csv(FILE_FT)
    # Renommage pour standardiser
    df_ft = df_ft.rename(columns={
        "Ville_Clean": "Ville",
        "Salaire_Annuel_Estime": "Salaire_Annuel",
        "Description_Propre": "Description"
    })
    # Ajout colonnes manquantes
    df_ft["Teletravail"] = "Non spécifié" 
    df_ft["Date_Publication"] = df_ft["Date_Publication"].apply(normaliser_date)
    df_ft["Date_Expiration"] = df_ft["Date_Expiration"].apply(normaliser_date)
    

    # On gère si certaines colonnes manquent dans le CSV source
    for c in cols_globales:
        if c not in df_ft.columns: df_ft[c] = None
    dataframes.append(df_ft[cols_globales])
else:
    print("⚠️ Fichier France Travail introuvable !")

# --- B. WTTJ ---
if os.path.exists(FILE_WTTJ):
    print("🔹 Chargement WTTJ...")
    df_wttj = pd.read_csv(FILE_WTTJ)
    
    df_wttj = df_wttj.rename(columns={
        "Ville_Clean": "Ville",
        "Salaire_Annuel_Estime": "Salaire_Annuel",
        "Description_Propre": "Description",
        "Date": "Date_Publication"
    })
    
    # Ajout Source et Date (Aujourd'hui)
    df_wttj["Source"] = "Welcome to the Jungle"
    df_wttj["Date_Publication"] = df_wttj["Date_Publication"].apply(normaliser_date)    
    df_wttj["Date_Expiration"] = df_wttj["Date_Expiration"].apply(normaliser_date)
    
    for c in cols_globales:
        if c not in df_wttj.columns: df_wttj[c] = None
    dataframes.append(df_wttj[cols_globales])
else:
    print("⚠️ Fichier WTTJ introuvable !")

# --- C. APEC ---
if os.path.exists(FILE_APEC):
    print("🔹 Chargement APEC...")
    df_apec = pd.read_csv(FILE_APEC)
    
    df_apec = df_apec.rename(columns={
        "Ville_Clean": "Ville",
        "Salaire_Annuel_Estime": "Salaire_Annuel",
        "Description_Propre": "Description",
        "Date": "Date_Publication"
    })
    
    df_apec["Source"] = "Apec"    
    df_apec["Teletravail"] = "Non spécifié"
    df_apec["Date_Publication"] = df_apec["Date_Publication"].apply(normaliser_date)
    df_apec["Date_Expiration"] = df_apec["Date_Expiration"].apply(normaliser_date)
    
    for c in cols_globales:
        if c not in df_apec.columns: df_apec[c] = None
    dataframes.append(df_apec[cols_globales])
else:
    print("⚠️ Fichier APEC introuvable !")
# endregion

# ======================================================================================================================================================

# region 4. --- FUSION ---

if not dataframes:
    print("❌ Aucun fichier chargé. Arrêt.")
    exit()

print("🌪️  Mélange des données...")
df_final = pd.concat(dataframes, ignore_index=True)

# === CORRECTION DE L'ANCIENNETÉ (FIX DURÉE DE VIE) ===

df_final['Date_Publication'] = pd.to_datetime(df_final['Date_Publication'], errors='coerce')
df_final['Date_Publication'] = df_final.groupby('URL')['Date_Publication'].transform('min')

print("🧹 Standardisation des grandes villes (Arrondissements)...")

df_final['Ville'] = df_final['Ville'].astype(str).str.replace(r'(?i)^paris.*', 'Paris', regex=True)
df_final['Ville'] = df_final['Ville'].str.replace(r'(?i)^lyon.*', 'Lyon', regex=True)
df_final['Ville'] = df_final['Ville'].str.replace(r'(?i)^marseille.*', 'Marseille', regex=True)

# Correction spécifique pour "La Défense" qui apparaît parfois comme "Puteaux" ou "Courbevoie"
# (Optionnel, mais utile pour regrouper les offres de ce hub)
# df_final['Ville'] = df_final['Ville'].replace(['Courbevoie', 'Puteaux', 'Nanterre'], 'La Défense')

# --------------------------------------------------

# --- Application des corrections ---

print("✨ Nettoyage des guillemets résiduels...")
cols_text = ['Titre', 'Entreprise', 'Ville']
for col in cols_text:
    # On force en string, on remplace les " et on enlève les espaces vides
    df_final[col] = df_final[col].astype(str).str.replace('"', '', regex=False).str.strip()
    
    # On enlève les "nan" qui apparaissent parfois lors de la conversion string
    df_final[col] = df_final[col].replace('nan', 'Non spécifié')

# Suppression des doublons (basé sur l'URL)
len_avant = len(df_final)
df_final = df_final.drop_duplicates(subset=["URL"], keep='last')
len_apres = len(df_final)

print(f"🧹 Doublons supprimés : {len_avant - len_apres}")

# === NETTOYAGE CONTRATS ===

print("🧮 Extraction des années d'expérience...")
df_final['Annees_Exp'] = df_final['Description'].apply(extraire_annees_exp)
df_final = nettoyer_contrats(df_final)

# === CALCUL DU NIVEAU D'EXPÉRIENCE ===
print("🧠 Calcul des niveaux d'expérience (Analyse Salaires & Texte)...")
# On applique la fonction ligne par ligne (axis=1)
df_final['Niveau'] = df_final.apply(determiner_niveau, axis=1)

# === STACKS ===

keywords = {
        "Python": r"\bpython\b",
        "SQL": r"\bsql\b",
        "Excel": r"\bexcel\b",
        "Power BI": r"power\s?bi", # Accepte "PowerBI" ou "Power BI"
        "Tableau": r"\btableau\b",
        "R": r"\bR\b",             # Attention, peut capter "R&D", mais souvent OK
        "SAS": r"\bsas\b",
        "VBA": r"\bvba\b",
        "AWS": r"\baws\b",
        "Azure": r"\bazure\b",
        "GCP": r"\bgcp\b|google\scloud",
        "Spark": r"\bspark\b",
        "Hadoop": r"\bhadoop\b",
        "Kafka": r"\bkafka\b",
        "Airflow": r"\bairflow\b",
        "Snowflake": r"\bsnowflake\b",
        "Databricks": r"\bdatabricks\b",
        "Docker": r"\bdocker\b",
        "Kubernetes": r"\bkubernetes\b|k8s",
        "Git": r"\bgit\b",
        "Linux": r"\blinux\b",
        "Pandas": r"\bpandas\b",
        "TensorFlow": r"\btensorflow\b",
        "PyTorch": r"\bpytorch\b",
        "Scikit-learn": r"scikit[\s\-]learn|sklearn",
        "Java": r"\bjava\b",       # Exclut Javascript grâce aux \b
        "Scala": r"\bscala\b",
        "C++": r"\bc\+\+",
        "NoSQL": r"no\s?sql|mongo|cassandra",
        "Dbt": r"\bdbt\b"
    }

def detecter_stack(description):
    if pd.isna(description): return ""
    desc_lower = str(description).lower()
    found = []
    for tech, pattern in keywords.items():        
        if re.search(pattern, desc_lower):
            found.append(tech)
            
    return ", ".join(found)

print("🧠 Analyse des compétences Tech...")
df_final['Tech_Stack'] = df_final['Description'].apply(detecter_stack)

# === INCLUSION ===

df_final['Handicap_Friendly'] = df_final['Description'].apply(detecter_rqth)

# endregion
# ======================================================================================================================================================

# region 5. --- SAUVEGARDE ---
df_final.to_csv(OUTPUT_CSV, index=False)

print(f"\n✅ TERMINÉ ! Le fichier global est prêt :")
print(f"👉 {OUTPUT_CSV}")
print("\n📊 STATISTIQUES FINALES :")
print(df_final["Source"].value_counts())
print(f"\n💰 Offres avec salaire : {df_final['Salaire_Annuel'].notna().sum()}")
# endregion