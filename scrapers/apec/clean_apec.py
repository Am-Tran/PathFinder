import pandas as pd
import os
import re

# --- 1. CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

INPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_apec_full.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "clean", "offres_apec_clean.csv")

print(f"🧹 Démarrage du nettoyage APEC : {INPUT_CSV}")

# --- 2. CHARGEMENT ---
if not os.path.exists(INPUT_CSV):
    print("❌ Fichier introuvable.")
    exit()

df = pd.read_csv(INPUT_CSV)
print(f"✅ Chargé initialement : {len(df)} lignes.")

# --- 3. FONCTIONS DE NETTOYAGE ---

def est_offre_valide(row):
    """
    Détecte si la ligne est une vraie offre ou du 'bruit' (cookies, login, offre expirée).
    Renvoie False si c'est du bruit.
    """
    titre = str(row['Titre']).lower()
    desc = str(row['Description_Complete']).lower()
    entreprise = str(row['Entreprise']).lower()

    # Liste des mots qui prouvent que c'est une page poubelle
    mots_interdits = [
        "votre vie privée", 
        "paramétrer les cookies", 
        "mot de passe oublié", 
        "vous avez déjà un compte",
        "l'offre", # Pour "L'offre n'est plus en ligne"
        "n'est plus en ligne",
        "accès recruteur",
        "erreur inattendue",
        "cette offre n'est plus disponible"
    ]

    # 1. Vérification dans la description
    for mot in mots_interdits:
        if mot in desc:
            return False
    
    # 2. Vérification de l'entreprise (si c'est "SALAIRE" ou vide)
    if "salaire" in entreprise or "vie privee" in entreprise or len(entreprise) < 2:
        return False

    # 3. Vérification contenu trop court (moins de 100 caractères = suspect)
    if len(desc) < 100:
        return False

    return True

def extraire_salaire_apec(texte):
    if pd.isna(texte) or "Non spécifié" in str(texte) or "A négocier" in str(texte):
        return None
    txt = str(texte).lower().replace(',', '.')
    
    # Cas 1 : Fourchette "35 - 45 k€"
    match_range = re.search(r'(\d{2})[ ]?[-|à][ ]?(\d{2})[ ]?k', txt)
    if match_range:
        min_k = float(match_range.group(1))
        max_k = float(match_range.group(2))
        return int((min_k + max_k) / 2 * 1000)

    # Cas 2 : Valeur unique "A partir de 40 k€"
    match_simple = re.search(r'(\d{2})[ ]?k', txt)
    if match_simple:
        val = float(match_simple.group(1))
        if 20 <= val <= 150:
            return int(val * 1000)
    return None

def nettoyer_ville_apec(texte):
    if pd.isna(texte): return "France"
    txt = str(texte)
    if " - " in txt:
        ville = txt.split(" - ")[0]
        ville = re.sub(r'\s\d{2}$', '', ville) 
        return ville.strip()
    return txt.strip()

def detecter_contrat(texte_tags):
    if pd.isna(texte_tags): return "CDI" # Par défaut sur l'APEC
    txt = str(texte_tags).upper()
    mots_cles = ["CDI", "CDD", "INTERIM", "ALTERNANCE", "STAGE", "FREELANCE"]
    for mot in mots_cles:
        if mot in txt:
            return mot.capitalize()
    return "CDI"

def nettoyer_texte(texte):
    if pd.isna(texte): return ""
    # Enlève les gros blocs de texte technique inutiles
    if "votre vie privée" in str(texte).lower():
        return "Description non disponible (Cookie Wall)"
        
    clean = str(texte).replace('\n', ' ').replace('\r', ' ')
    return " ".join(clean.split())

# --- 4. APPLICATION DU FILTRE ET NETTOYAGE ---

print("⚙️ Filtrage des offres invalides (Cookies, Expirées)...")

# On applique le filtre
df['Est_Valide'] = df.apply(est_offre_valide, axis=1)
df_clean = df[df['Est_Valide'] == True].copy()

lignes_supprimees = len(df) - len(df_clean)
print(f"🗑️  Lignes supprimées (Bruit) : {lignes_supprimees}")
print(f"💎 Lignes valides restantes : {len(df_clean)}")

print("⚙️ Transformation des données...")

# Salaire
df_clean['Salaire_Annuel_Estime'] = df_clean['Salaire_Brut'].apply(extraire_salaire_apec)

# Ville
df_clean['Ville_Clean'] = df_clean['Ville'].apply(nettoyer_ville_apec)

# Contrat
df_clean['Type_Contrat'] = df_clean['Details_Tags'].apply(detecter_contrat)

# Nettoyage texte description
df_clean['Description_Propre'] = df_clean['Description_Complete'].apply(nettoyer_texte)

# Nettoyage Titre/Entreprise
df_clean['Titre'] = df_clean['Titre'].astype(str).str.strip()
df_clean['Entreprise'] = df_clean['Entreprise'].astype(str).str.upper().str.strip()

# --- 5. STATS ---
nb_salaires = df_clean['Salaire_Annuel_Estime'].notna().sum()
moyenne = df_clean['Salaire_Annuel_Estime'].mean() if nb_salaires > 0 else 0

print(f"\n📊 Résumé APEC Final :")
print(f"   - Offres propres : {len(df_clean)}")
print(f"   - Salaires trouvés : {nb_salaires}")
if nb_salaires > 0:
    print(f"   - Moyenne : {moyenne:.0f} €")

# --- 6. SAUVEGARDE ---
colonnes_finales = [
    'Titre', 'Entreprise', 'Ville_Clean', 'Type_Contrat', 
    'Salaire_Annuel_Estime', 'URL', 'Description_Propre'
]

df_clean['Source'] = 'Apec'
colonnes_finales.append('Source')

df_clean[colonnes_finales].to_csv(OUTPUT_CSV, index=False)
print(f"\n✅ Terminé ! Fichier propre : {OUTPUT_CSV}")