import pandas as pd
import os
from datetime import datetime
import re

# --- 1. CONFIGURATION ---
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

# --- FONCTION DE CLASSIFICATION (NIVEAU) ---
def determiner_niveau(row):
    """
    Déduit le niveau d'expérience (Etudiant, Junior, Confirmé, Senior) 
    basé sur le salaire (distingue idf des autres zones) et les mots-clés du titre.
    """
    titre = str(row['Titre']).lower() if pd.notna(row['Titre']) else ""
    desc = str(row['Description']).lower() if pd.notna(row['Description']) else "" 
    lieu = str(row['Ville']).lower() if pd.notna(row['Ville']) else "" 
    salaire = row['Salaire_Annuel']
    contrat = str(row['Type_Contrat']).lower() if pd.notna(row['Type_Contrat']) else ""

    # --- 2. DÉTECTION STAGE (Priorité absolue) ---
    mots_stage = ["stage", "internship", "alternance", "alternant", "stagiaire", "apprentissage", "contrat pro"]
    if any(k in contrat for k in mots_stage) or any(k in titre for k in mots_stage) or any(k in desc for k in mots_stage):
        return "Stage / Alternance"

    # --- 3. DÉFINITION DES SEUILS SELON LA GÉOGRAPHIE ---
    # Liste des mots qui indiquent la région parisienne
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

    # --- 4. LE VERDICT DU SALAIRE ---
    if pd.notna(salaire) and salaire > 0:
        if salaire <= seuil_junior:
            return "Junior"
        elif seuil_junior < salaire < seuil_senior:
            return "Confirmé"
        else:
            return "Senior"

    # --- 5. FALLBACK : ANALYSE TEXTUELLE ---
    # (Titre)
    if any(k in titre for k in ["senior", "lead", "manager", "head of", "directeur", "expert", "principal", "vp"]):
        return "Senior"
    if any(k in titre for k in ["junior", "débutant", "assistant", "graduate"]):
        return "Junior"
    if "confirmé" in titre:
        return "Confirmé"

    # (Description - Années)
    pattern = r"(\d{1,2})\s*?(?:-|\s)?\s*?(?:ans|années|years|year)"
    match = re.search(pattern, desc)
    if match:
        annees = int(match.group(1))
        if annees < 3: return "Junior"
        elif 3 <= annees <= 5: return "Confirmé"
        else: return "Senior"

    return "Non spécifié"

# --- 2. CHARGEMENT ET STANDARDISATION ---
dataframes = []
cols_globales = [
    "Titre", "Entreprise", "Ville", "Salaire_Annuel", "Type_Contrat", 
    "Teletravail", "Date_Publication", "Date_Expiration", "Source", "URL", "Description"
]

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
        "Description_Propre": "Description"
    })
    
    # Ajout Source et Date (Aujourd'hui)
    df_wttj["Source"] = "Welcome to the Jungle"
    df_wttj["Date"] = datetime.today().strftime('%Y-%m-%d')
    
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
    
    for c in cols_globales:
        if c not in df_apec.columns: df_apec[c] = None
    dataframes.append(df_apec[cols_globales])
else:
    print("⚠️ Fichier APEC introuvable !")

# --- 3. FUSION ---

if not dataframes:
    print("❌ Aucun fichier chargé. Arrêt.")
    exit()

print("🌪️  Mélange des données...")
df_final = pd.concat(dataframes, ignore_index=True)

# === LE NETTOYAGE ===

print("✨ Nettoyage et Harmonisation des Contrats...")

# 1. Nettoyage de base : String + Strip (enlève espaces) + Capitalize (Cdi, Stage, Cdd...)
# Cela regroupe automatiquement "cdi", "CDI" et "Cdi" sous la forme "Cdi"
df_final["Type_Contrat"] = df_final["Type_Contrat"].astype(str).str.strip().str.capitalize()

# 2. Dictionnaire de traduction et remise en forme (Cdi -> CDI)
# Note : Comme on a fait .capitalize() juste avant, "MIS" est devenu "Mis" et "LIB" est devenu "Lib"
corrections_contrat = {
    "Mis": "Intérim",
    "Lib": "Freelance",
    "Din": "CDI Intérimaire",
    "Cdi": "CDI",  # On remet en majuscules
    "Cdd": "CDD",  # On remet en majuscules
    "Nan": "Non spécifié" # Gère les valeurs vides
}

print("🧹 Standardisation des grandes villes (Arrondissements)...")

df_final['Ville'] = df_final['Ville'].astype(str).str.replace(r'(?i)^paris.*', 'Paris', regex=True)
df_final['Ville'] = df_final['Ville'].str.replace(r'(?i)^lyon.*', 'Lyon', regex=True)
df_final['Ville'] = df_final['Ville'].str.replace(r'(?i)^marseille.*', 'Marseille', regex=True)

# Correction spécifique pour "La Défense" qui apparaît parfois comme "Puteaux" ou "Courbevoie"
# (Optionnel, mais utile pour regrouper les offres de ce hub)
# df_final['Ville'] = df_final['Ville'].replace(['Courbevoie', 'Puteaux', 'Nanterre'], 'La Défense')

# 3. Application des corrections
df_final["Type_Contrat"] = df_final["Type_Contrat"].replace(corrections_contrat)
print("✨ Nettoyage des guillemets résiduels...")
cols_text = ['Titre', 'Entreprise', 'Ville']
for col in cols_text:
    # On force en string, on remplace les " et on enlève les espaces vides
    df_final[col] = df_final[col].astype(str).str.replace('"', '', regex=False).str.strip()
    
    # On enlève les "nan" qui apparaissent parfois lors de la conversion string
    df_final[col] = df_final[col].replace('nan', 'Non spécifié')

# Suppression des doublons (basé sur l'URL)
len_avant = len(df_final)
df_final = df_final.drop_duplicates(subset=["URL"])
len_apres = len(df_final)

print(f"🧹 Doublons supprimés : {len_avant - len_apres}")

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

# --- 4. SAUVEGARDE ---
df_final.to_csv(OUTPUT_CSV, index=False)

print(f"\n✅ TERMINÉ ! Le fichier global est prêt :")
print(f"👉 {OUTPUT_CSV}")
print("\n📊 STATISTIQUES FINALES :")
print(df_final["Source"].value_counts())
print(f"\n💰 Offres avec salaire : {df_final['Salaire_Annuel'].notna().sum()}")