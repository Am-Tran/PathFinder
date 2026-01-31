import pandas as pd
import re

# ================= CONFIGURATION =================
FICHIER_CIBLE = "data/clean/global_job_market.csv" 
# =================================================

def main():
    print(f"📂 Chargement de {FICHIER_CIBLE}...")
    try:
        df = pd.read_csv(FICHIER_CIBLE)
    except FileNotFoundError:
        print("❌ Fichier introuvable.")
        return

    # Nettoyage
    df['Titre'] = df['Titre'].astype(str).fillna('')
    df['Description'] = df['Description'].astype(str).fillna('')
    if 'Niveau' not in df.columns:
        df['Niveau'] = 'Non spécifié'
    else:
        df['Niveau'] = df['Niveau'].fillna('Non spécifié')

    # Tes catégories officielles
    categories_valides = ['Junior', 'Confirmé', 'Senior', 'Stage / Alternance', 'Non spécifié']

    # On remet à plat tout ce qui n'est pas dans ta liste officielle pour le retrier
    # (Ça corrige aussi les anciens "Lead / Manager" qui deviendront "Senior")
    mask_a_traiter = ~df['Niveau'].isin(categories_valides)
    
    # On force aussi le retraitement des "Non spécifié"
    mask_retraitement = (df['Niveau'] == 'Non spécifié') | mask_a_traiter
    
    nb_a_traiter = len(df[mask_retraitement])
    print(f"📊 Offres à analyser ou revérifier : {nb_a_traiter}")

    # --- LE CERVEAU ---
    def deduire_niveau(row):
        # Si on a déjà un niveau valide (sauf "Non spécifié" qu'on veut revérifier), on garde
        current = str(row['Niveau']).strip()
        if current in categories_valides and current != 'Non spécifié':
            return current

        text_complet = (row['Titre'] + " " + row['Description']).lower()
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

    # --- APPLICATION ---
    print("🧠 Classification stricte (Senior/Confirmé/Junior)...")
    df['Niveau'] = df.apply(deduire_niveau, axis=1)

    # Sauvegarde
    df.to_csv(FICHIER_CIBLE, index=False)
    
    print("-" * 40)
    print(f"✅ Terminé ! {FICHIER_CIBLE} mis à jour.")
    print("Nouvelle répartition :")
    print(df['Niveau'].value_counts())
    print("-" * 40)

if __name__ == "__main__":
    main()