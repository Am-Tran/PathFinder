import pandas as pd
import sys
import os
import re
from supabase import create_client
import pytz
from datetime import datetime

# --- 1. CONFIGURATION ---
table_choisie = "Data_Analyst_test"

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

# --- 2. CHARGEMENT ---
print("📥 Téléchargement des offres à nettoyer depuis le Cloud...")

filtres_nettoyage = {
    "source": "APEC",
    "statut": "Collecte"
}

df = load_data(supabase, table_choisie, limit=None, filters = filtres_nettoyage)
if df.empty:
    print("✨ Aucune offre APEC en statut 'Collecte' n'a été trouvée dans ce lot de 100.")
    sys.exit(0)

# --- 3. FONCTIONS DE NETTOYAGE ---

def extraire_ville_regex(row):
    """
    Cherche un motif 'Ville - Dept' dans les tags.
    Prioritaire sur la colonne 'Ville'.
    Unifie toutes les variantes de Paris.
    
    """
    tags = str(row['Description'])
    ville_trouvee = None    

    # REGEX : Un mot (avec tirets/espaces) + " - " + 2 chiffres (département)   
    tags_line = tags.split('DESCRIPTION :')[0]
    tags_list = tags_line.split(' | ')
    
    for tag in tags_list:
        tag = tag.replace('TAGS APEC :', '').strip()        
        # REGEX : Un mot (lettres/tirets) suivi d'un espace OU d'un " - " puis 2 chiffres
        match = re.search(r'^([A-Za-zÀ-ÿ\s-]+?)(?:\s-\s|\s)(\d{2})\b', tag)        
        if match and "€" not in tag and "k" not in tag.lower():
            ville_trouvee = match.group(1).strip()
            break
    
    # Si regex échoue, on regarde la colonne Ville existante
    if ville_trouvee is None:
        ville_existante = str(row['Ville'])
        if ville_existante and "Non spécifié" not in ville_existante and len(ville_existante) > 2:
            if " - " in ville_existante:
                ville_trouvee = ville_existante.split(' - ')[0]
            else:
                ville_trouvee = ville_existante


    #Unification des grandes villes (arrondissements) 
    if ville_trouvee:   
        ville_lower = ville_trouvee.lower()
        
        if "paris" in ville_lower:
            return "Paris"
        if "lyon" in ville_lower:  # Bonus : souvent utile pour "Lyon 3ème", etc.
            return "Lyon"
        if "marseille" in ville_lower:
            return "Marseille"           
        return ville_trouvee
    return None
def extraire_contrat_regex(row):
    """
    Cherche CDI, CDD, etc. partout dans les tags
    """
    description = str(row['Description']).upper()
    tags = description.split('DESCRIPTION :')[0].upper()
    
    # Ordre d'importance
    if "CDD" in tags: return "CDD"
    if "INTERIM" in tags or "INTÉRIM" in tags: return "Intérim"
    if "FREELANCE" in tags or "INDÉPENDANT" in tags: return "Freelance"
    if "STAGE" in tags: return "Stage"
    if "ALTERNANCE" in tags or "PROFESSIONNALISATION" in tags: return "Alternance"
    if "CDI" in tags: return "CDI"
    
    return None # Valeur par défaut

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
    desc = str(row['Description']).lower()
    entreprise = str(row['Entreprise']).lower()

    # Liste des mots qui prouvent que c'est une page poubelle
    mots_interdits = [
        "votre vie privée", 
        "paramétrer les cookies", 
        "mot de passe oublié", 
        "vous avez déjà un compte",
        # Pour "L'offre n'est plus en ligne"
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
try:
    df['Est_Valide'] = df.apply(est_offre_valide, axis=1)
    df_clean = df[df['Est_Valide'] == True].copy()

    lignes_supprimees = len(df) - len(df_clean)
    print(f"🗑️  Lignes supprimées (Bruit) : {lignes_supprimees}")
    print(f"💎 Lignes valides restantes : {len(df_clean)}")

    print("⚙️ Transformation des données...")

    # Date
    df_clean['Date_Publication'] = pd.to_datetime(df_clean['Date_Publication'], format='%d/%m/%Y', errors='coerce').dt.strftime('%Y-%m-%d')   
    date_str = date_actuelle.strftime('%Y-%m-%d')
    df_clean['Date_Publication'] = df_clean['Date_Publication'].fillna(date_str)

    # Salaire
    df_clean['Salaire_Annuel'] = df_clean['Salaire_Annuel'].apply(extraire_salaire_apec)

    # Ville
    df_clean['Ville'] = df_clean.apply(extraire_ville_regex, axis = 1)

    # Contrat
    df_clean['Type_Contrat'] = df_clean.apply(extraire_contrat_regex, axis = 1)

    # Nettoyage texte description
    df_clean['Description'] = df_clean['Description'].apply(nettoyer_texte)

    # Nettoyage Titre/Entreprise
    df_clean['Titre'] = df_clean['Titre'].astype(str).str.strip()
    df_clean['Entreprise'] = df_clean['Entreprise'].astype(str).str.upper().str.strip()

    # Statut
    df_clean['Statut'] = "Prep"
    df_clean['Source'] = 'APEC'
    df_clean['Metier'] = "Data Analyst"
 
except Exception as e:
    print(f"❌ Erreur critique lors de la transformation des données : {e}")
    print("🛑 Arrêt d'urgence du nettoyeur pour protéger la base de données.")
    exit()

# --- 5. STATS ---
nb_salaires = df_clean['Salaire_Annuel'].notna().sum()
moyenne = df_clean['Salaire_Annuel'].mean() if nb_salaires > 0 else 0

print(f"\n📊 Résumé APEC Final :")
print(f"   - Offres propres : {len(df_clean)}")
print(f"   - Salaires trouvés : {nb_salaires}")
if nb_salaires > 0:
    print(f"   - Moyenne : {moyenne:.0f} €")

# --- 6. SAUVEGARDE ---

print("\n🚀 Préparation des données pour Supabase...")

colonnes_supabase = [
    "Titre", "Entreprise", "Ville", "Type_Contrat", 
    "Salaire_Annuel", "Description", "Date_Publication", 
    "Source", "URL", "Statut", "Metier"
]

df_clean = df_clean[colonnes_supabase]
df_clean = df_clean.astype(object).where(pd.notna(df_clean), None)

print("\n🚀 Envoi des données nettoyées vers Supabase...")

erreurs = 0
liste_donnees = df_clean.to_dict(orient='records')

for i in range(0, len(liste_donnees), 1000):
    batch = liste_donnees[i : i + 1000]
    try:
        supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
    except Exception as e:
        erreurs += 1
        if erreurs == 1:
            print("\n🚨 --- ALERTE ROUGE : DÉTAIL DU CRASH --- 🚨")
            print(f"❌ Le message de Supabase : {e}")
            print(f"📦 Le paquet refusé : {batch[0]}")
            print(f"🆔 L'ID ciblé : {batch[0].get('URL', 'URL INTROUVABLE')}")
            print("-------------------------------------------\n")

print(f"\n✅ Nettoyage terminé ! {max(0, len(liste_donnees) - (erreurs*1000))} offres mises à jour.")
if erreurs > 0:
    print(f"⚠️ Il y a eu {erreurs} erreurs lors de l'envoi.")