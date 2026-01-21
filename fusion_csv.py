import pandas as pd
import os
from datetime import datetime

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

print("🧪 Démarrage de la FUSION TOTALE...")

# --- 2. CHARGEMENT ET STANDARDISATION ---
dataframes = []

# --- A. FRANCE TRAVAIL ---
if os.path.exists(FILE_FT):
    print("   🔹 Chargement France Travail...")
    df_ft = pd.read_csv(FILE_FT)
    # Renommage pour standardiser
    df_ft = df_ft.rename(columns={
        "Ville_Clean": "Ville",
        "Salaire_Annuel_Estime": "Salaire_Annuel",
        "Description_Propre": "Description",
        "Date_Publication": "Date"
    })
    # Ajout colonnes manquantes
    df_ft["Teletravail"] = "Non spécifié" 
    # Sélection stricte des colonnes
    cols = ["Titre", "Entreprise", "Ville", "Salaire_Annuel", "Type_Contrat", "Teletravail", "Date", "Source", "URL", "Description"]
    # On gère si certaines colonnes manquent dans le CSV source
    for c in cols:
        if c not in df_ft.columns: df_ft[c] = None
    dataframes.append(df_ft[cols])
else:
    print("   ⚠️ Fichier France Travail introuvable !")

# --- B. WTTJ ---
if os.path.exists(FILE_WTTJ):
    print("   🔹 Chargement WTTJ...")
    df_wttj = pd.read_csv(FILE_WTTJ)
    
    df_wttj = df_wttj.rename(columns={
        "Ville_Clean": "Ville",
        "Salaire_Annuel_Estime": "Salaire_Annuel",
        "Description_Propre": "Description"
    })
    
    # Ajout Source et Date (Aujourd'hui)
    df_wttj["Source"] = "Welcome to the Jungle"
    df_wttj["Date"] = datetime.today().strftime('%Y-%m-%d')
    
    cols = ["Titre", "Entreprise", "Ville", "Salaire_Annuel", "Type_Contrat", "Teletravail", "Date", "Source", "URL", "Description"]
    for c in cols:
        if c not in df_wttj.columns: df_wttj[c] = None
    dataframes.append(df_wttj[cols])
else:
    print("   ⚠️ Fichier WTTJ introuvable !")

# --- C. APEC ---
if os.path.exists(FILE_APEC):
    print("   🔹 Chargement APEC...")
    df_apec = pd.read_csv(FILE_APEC)
    
    df_apec = df_apec.rename(columns={
        "Ville_Clean": "Ville",
        "Salaire_Annuel_Estime": "Salaire_Annuel",
        "Description_Propre": "Description"
    })
    
    df_apec["Source"] = "Apec"
    df_apec["Date"] = datetime.today().strftime('%Y-%m-%d')
    df_apec["Teletravail"] = "Non spécifié"
    
    cols = ["Titre", "Entreprise", "Ville", "Salaire_Annuel", "Type_Contrat", "Teletravail", "Date", "Source", "URL", "Description"]
    for c in cols:
        if c not in df_apec.columns: df_apec[c] = None
    dataframes.append(df_apec[cols])
else:
    print("   ⚠️ Fichier APEC introuvable !")

# --- 3. FUSION ---

if not dataframes:
    print("❌ Aucun fichier chargé. Arrêt.")
    exit()

print("🌪️  Mélange des données...")
df_final = pd.concat(dataframes, ignore_index=True)

# === LE NETTOYAGE ULTIME ===

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

# --- 4. SAUVEGARDE ---
df_final.to_csv(OUTPUT_CSV, index=False)

print(f"\n✅ TERMINÉ ! Le fichier global est prêt :")
print(f"👉 {OUTPUT_CSV}")
print("\n📊 STATISTIQUES FINALES :")
print(df_final["Source"].value_counts())
print(f"\n💰 Offres avec salaire : {df_final['Salaire_Annuel'].notna().sum()}")