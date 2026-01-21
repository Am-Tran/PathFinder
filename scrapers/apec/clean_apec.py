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

def extraire_ville_regex(row):
    """
    Cherche un motif 'Ville - Dept' dans les tags.
    Prioritaire sur la colonne 'Ville'.
    Unifie toutes les variantes de Paris.
    
    """
    tags = str(row['Details_Tags'])
    ville_trouvee = "France"

    # REGEX : Un mot (avec tirets/espaces) + " - " + 2 chiffres (département)   
    match = re.search(r'(?<!\d)([A-Za-zÀ-ÿ\s-]+)\s-\s(\d{2}\b)', tags)
    
    if match:
        ville = match.group(1).strip()
        # On ignore "Salaire - 35" qui pourrait ressembler à une ville
        if "salaire" not in ville.lower():
            ville_trouvee = ville
    
    # Si regex échoue, on regarde la colonne Ville existante
    ville_existante = str(row['Ville'])
    if ville_existante and "Non spécifié" not in ville_existante and len(ville_existante) > 2:
        if " - " in ville_existante:
            ville_trouvee = ville_existante.split(' - ')[0]
        else:
            ville_trouvee = ville_existante


    #Unification des grandes villes (arrondissements)    
    ville_lower = ville_trouvee.lower()
    
    if "paris" in ville_lower:
        return "Paris"
    if "lyon" in ville_lower:  # Bonus : souvent utile pour "Lyon 3ème", etc.
        return "Lyon"
    if "marseille" in ville_lower:
        return "Marseille"
        
    return ville_trouvee

def extraire_contrat_regex(row):
    """
    Cherche CDI, CDD, etc. partout dans les tags
    """
    tags = str(row['Details_Tags']).upper()
    
    # Ordre d'importance
    if "CDD" in tags: return "CDD"
    if "INTERIM" in tags or "INTÉRIM" in tags: return "Intérim"
    if "FREELANCE" in tags or "INDÉPENDANT" in tags: return "Freelance"
    if "STAGE" in tags: return "Stage"
    if "ALTERNANCE" in tags or "PROFESSIONNALISATION" in tags: return "Alternance"
    if "CDI" in tags: return "CDI"
    
    return "CDI" # Valeur par défaut

def extraire_salaire_apec(texte):
    if pd.isna(texte) or "Non spécifié" in str(texte):
        return None
    txt = str(texte).lower().replace(',', '.')
    
    # Cas 1 : Fourchette "35 - 45 k€"
    match_range = re.search(r'(\d{2})[ ]?[-|à][ ]?(\d{2})[ ]?k', txt)
    if match_range:
        return int((float(match_range.group(1)) + float(match_range.group(2))) / 2 * 1000)

    # Cas 2 : Valeur simple "40 k€"
    match_simple = re.search(r'(\d{2})[ ]?k', txt)
    if match_simple:
        val = float(match_simple.group(1))
        if 20 <= val <= 150: return int(val * 1000)
    return None

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
df_clean['Ville_Clean'] = df_clean.apply(extraire_ville_regex, axis = 1)

# Contrat
df_clean['Type_Contrat'] = df_clean.apply(extraire_contrat_regex, axis = 1)

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