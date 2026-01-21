import pandas as pd
import os
import re

# --- 1. CONFIGURATION ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

# Chemins (Adapter si ton script n'est pas dans un sous-dossier scrapers/...)
INPUT_CSV = os.path.join(project_root, "data", "enriched", "offres_francetravail_complet.csv")
OUTPUT_CSV = os.path.join(project_root, "data", "clean", "offres_francetravail_clean.csv")

print(f"🧹 Démarrage du nettoyage pour : {INPUT_CSV}")

# --- 2. CHARGEMENT ---
try:
    df = pd.read_csv(INPUT_CSV)
    print(f"✅ Chargé : {len(df)} offres brutes.")
except FileNotFoundError:
    print("❌ Fichier introuvable. Vérifie le chemin.")
    exit()

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

def extraire_dept(texte):
    # Entrée: "92 - Courbevoie" -> Sortie: "92"
    if pd.isna(texte): return "Inconnu"
    if " - " in str(texte):
        return str(texte).split(" - ")[0].strip()
    return "Inconnu"

def extraire_ville(texte):
    # Entrée: "92 - Courbevoie" -> Sortie: "Courbevoie"
    if pd.isna(texte): return "Inconnu"
    if " - " in str(texte):
        parties = str(texte).split(" - ")
        if len(parties) > 1:
            return parties[1].strip()
    return str(texte)

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
df['Date_Publication'] = df['Date_Creation'].apply(nettoyer_date)

# Localisation
df['Departement'] = df['Ville'].apply(extraire_dept)
df['Ville_Clean'] = df['Ville'].apply(extraire_ville)

#Titre
df['Titre'] = df['Titre'].astype(str).str.replace('"', '', regex=False).str.strip()
df['Entreprise'] = df['Entreprise'].astype(str).str.replace('"', '', regex=False).str.strip()

# Salaire
df['Salaire_Annuel_Estime'] = df['Salaire'].apply(nettoyer_salaire)

# Description (Pour lecture facile)
df['Description_Propre'] = df['Description'].apply(nettoyer_texte)

# --- 5. STATISTIQUES RAPIDES ---
nb_salaires = df['Salaire_Annuel_Estime'].notna().sum()
moyenne_salaire = df['Salaire_Annuel_Estime'].mean()

print(f"\n📊 Résumé après nettoyage :")
print(f"   - Offres avec salaire détecté : {nb_salaires} / {len(df)}")
if nb_salaires > 0:
    print(f"   - Salaire moyen estimé : {moyenne_salaire:.0f} €/an")

# --- 6. SAUVEGARDE ---
# On sélectionne les colonnes propres pour le fichier final
colonnes_finales = [
    'Titre', 'Entreprise', 'Ville_Clean', 'Departement', 
    'Type_Contrat', 'Salaire_Annuel_Estime', 'Date_Publication', 
    'URL', 'Description_Propre', 'Source'
]

# On filtre si certaines colonnes n'existent pas (sécurité)
cols_existantes = [c for c in colonnes_finales if c in df.columns]

df[cols_existantes].to_csv(OUTPUT_CSV, index=False)
print(f"\n✅ Terminé ! Fichier propre enregistré ici :")
print(f"👉 {OUTPUT_CSV}")