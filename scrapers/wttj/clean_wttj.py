import pandas as pd
import numpy as np
import os
import re
from datetime import datetime

# --- 1. CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

INPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_wttj_full.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "clean", "offres_wttj_clean.csv")

print(f"🧹 Démarrage du nettoyage WTTJ : {INPUT_CSV}")

# --- 2. CHARGEMENT ---
if not os.path.exists(INPUT_CSV):
    print("❌ Fichier introuvable.")
    exit()

df = pd.read_csv(INPUT_CSV, dtype=str)
print(f"✅ Chargé : {len(df)} offres.")

# --- 3. FONCTIONS D'EXTRACTION ---

def extraire_salaire_wttj(texte):
    """
    Extrait les salaires format '45k', '40-50k', '40k-50k'.
    Renvoie un entier annuel.
    """
    if pd.isna(texte): return None
    txt = str(texte).lower()
    
    # Motif pour chercher "XX k" ou "XX-YY k"
    # Ex: 45k, 40-50k, 40 k€
    match = re.search(r'(\d{2})[ ]?[-|à]?[ ]?(\d{2})?[ ]?k', txt)
    
    if match:
        min_val = float(match.group(1)) * 1000
        max_val = match.group(2)
        
        # Si on a une plage (ex: 40-50k), on fait la moyenne
        if max_val:
            max_val = float(max_val) * 1000
            return int((min_val + max_val) / 2)
        else:
            return int(min_val)
            
    return None

def detecter_contrat(texte_vrac):
    """Cherche le type de contrat dans la soupe de tags"""
    if pd.isna(texte_vrac): return "Non spécifié"
    
    mots_cles = ["CDI", "CDD", "Stage", "Alternance", "Freelance", "Apprentissage"]
    for mot in mots_cles:
        # On met des espaces autour pour éviter de trouver 'Stage' dans 'Stagiaire' par erreur
        if mot.lower() in str(texte_vrac).lower():
            return mot
    return "Non spécifié"

def detecter_ville(row):
    """
    Essaie de trouver la ville dans les tags ou le début de la description.
    """
    # Liste des grandes villes Tech en France pour scanner
    grandes_villes = [
        "Paris", "Lyon", "Bordeaux", "Nantes", "Lille", "Toulouse", 
        "Marseille", "Rennes", "Montpellier", "Strasbourg", "Nice", 
        "Aix-en-Provence", "Grenoble", "Levallois-Perret", "Boulogne-Billancourt", 
        "Courbevoie", "La Défense", "Nanterre", "Sophia Antipolis", "Remote"
    ]
    
    sources = [str(row['Ville']), str(row['Experience_Salaire_Infos']), str(row['Description_Complete'])[:300]]
    
    for source in sources:
        if pd.isna(source) or "Non spécifié" in source: continue
        
        for v in grandes_villes:
            if v in source:
                return v
                
    return "France / Remote"


def detecter_teletravail(texte_vrac):
    if pd.isna(texte_vrac): return "Non spécifié"
    txt = str(texte_vrac).lower()
    
    if "télétravail total" in txt or "full remote" in txt:
        return "Total"
    elif "télétravail fréquent" in txt or "télétravail partiel" in txt or "hybride" in txt:
        return "Hybride"
    elif "télétravail ponctuel" in txt:
        return "Ponctuel"
    elif "télétravail" in txt:
        return "Possible"
        
    return "Non spécifié"

def nettoyer_description(texte):
    if pd.isna(texte): return ""
    # Enlève les sauts de ligne excessifs
    clean = str(texte).replace('\n', ' ').replace('\r', ' ')
    # Enlève les gros espaces
    return " ".join(clean.split())


# --- 4. APPLICATION ---

print("⚙️ Extraction des données...")

# Contrat
df['Type_Contrat'] = df['Experience_Salaire_Infos'].apply(detecter_contrat)

# Salaire (On cherche dans les infos ET la description car parfois c'est caché dans le texte)
df['Salaire_Annuel_Estime'] = df['Experience_Salaire_Infos'].apply(extraire_salaire_wttj)

# Ville
df['Ville_Clean'] = df.apply(detecter_ville, axis=1)

# Télétravail
df['Teletravail'] = df['Experience_Salaire_Infos'].apply(detecter_teletravail)

# Description Propre
df['Description_Propre'] = df['Description_Complete'].apply(nettoyer_description)

# Nettoyage Titre et Entreprise
df['Titre'] = df['Titre'].astype(str).str.strip()
df['Entreprise'] = df['Entreprise'].astype(str).str.upper().str.strip()

# Gestion des Dates (Conversion en format date standard YYYY-MM-DD)
if 'Date_Publication' not in df.columns:
    df['Date_Publication'] = datetime.now().strftime("%Y-%m-%d")

# On garde Date_Expiration tel quel (peut être vide)
if 'Date_Expiration' not in df.columns:
    df['Date_Expiration'] = None

df['Source'] = "Welcome to the Jungle"

# --- 5. STATS ---
nb_salaires = df['Salaire_Annuel_Estime'].notna().sum()
moyenne_salaire = df['Salaire_Annuel_Estime'].mean()

print(f"\n📊 Résumé WTTJ :")
print(f"   - Offres traitées : {len(df)}")
print(f"   - Salaires trouvés : {nb_salaires}")
if nb_salaires > 0:
    print(f"   - Moyenne : {moyenne_salaire:.0f} €")

# --- 6. SAUVEGARDE ---
colonnes_finales = [
    'Titre', 'Entreprise', 'Ville_Clean', 'Type_Contrat', 
    'Salaire_Annuel_Estime', 'Teletravail', 
    'URL', 'Description_Propre', 'Date_Publication', 'Date_Expiration',
    'Source'
]

df[colonnes_finales].to_csv(OUTPUT_CSV, index=False)
print(f"\n✅ Terminé ! Fichier propre : {OUTPUT_CSV}")