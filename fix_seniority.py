import pandas as pd
import re
import os

# ================= CONFIGURATION =================
# On travaille toujours sur le même fichier
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
    
    # On reset les niveaux pour relancer l'analyse complète
    if 'Niveau' not in df.columns:
        df['Niveau'] = 'Non spécifié'
    else:
        df['Niveau'] = df['Niveau'].fillna('Non spécifié')
        # On remet à zéro ceux qui sont flous ou Junior par défaut pour revérifier
        criteres_reset = ['nan', 'inconnu', '', 'non spécifié', 'junior'] 
        # (J'ai ajouté 'junior' au reset au cas où on aurait fait une erreur avant)
        df.loc[df['Niveau'].str.lower().isin(criteres_reset), 'Niveau'] = 'Non spécifié'

    nb_a_traiter = len(df[df['Niveau'] == 'Non spécifié'])
    print(f"📊 Analyse de {nb_a_traiter} offres...")

    # --- LE CERVEAU DU SCRIPT ---
    def deduire_niveau(row):
        # Si on a déjà trouvé un Senior/Lead/Confirmé sûr, on garde.
        if row['Niveau'] not in ['Non spécifié', 'Junior']: 
             return row['Niveau']

        text_complet = (row['Titre'] + " " + row['Description']).lower()
        titre = row['Titre'].lower()

        # 1. ANALYSE TITRE (Priorité Absolue)
        if any(x in titre for x in ['stage', 'intern', 'alternan', 'apprenti']): return "Junior / Stage"
        if any(x in titre for x in ['lead', 'manager', 'head of', 'directeur', 'vp']): return "Lead / Manager"
        if any(x in titre for x in ['senior', 'expert', 'confirmé', 'sr.']): return "Senior"
        
        # 2. ANALYSE DU TEXTE : "Chiffre + Ans" (ex: "5 ans d'xp")
        match_classique = re.search(r'(\d+)[\s\-\/àa]*(?:ans|an|year|année)', text_complet)
        
        # 3. ANALYSE DU TEXTE : "Label : Chiffre" (ex: "Expérience : 5") 👈 C'EST ICI LA NOUTEAUTÉ
        # On cherche "minimum" ou "expérience" suivi de n'importe quoi, puis un chiffre
        match_label = re.search(r'(?:minimum|expérience|experience)[\s\w\']*:?\s*(\d+)', text_complet)

        # On prend le meilleur match (le label est souvent plus précis)
        match = match_label if match_label else match_classique

        if match:
            try:
                annees = int(match.group(1))
                # Filtre anti-bruit (ex: "entreprise de 100 ans")
                if 0 <= annees <= 15: 
                    if annees <= 2: return "Junior"
                    elif 2 < annees < 5: return "Confirmé"
                    elif annees >= 5: return "Senior"
            except:
                pass

        # 4. Mots-clés sémantiques (Dernier recours)
        if any(x in text_complet for x in ['première expérience', 'débutant accepté', 'junior']): return "Junior"
        if any(x in text_complet for x in ['forte expérience', 'significative']): return "Confirmé"

        # 5. Si vraiment rien de rien -> On parie sur Junior
        return "Junior"

    # --- APPLICATION ---
    print("🧠 Scan intelligent (Regex v3 + Mots-clés)...")
    df['Niveau'] = df.apply(deduire_niveau, axis=1)

    # Sauvegarde
    df.to_csv(FICHIER_CIBLE, index=False)
    
    print("-" * 40)
    print(f"✅ Terminé ! Fichier mis à jour : {FICHIER_CIBLE}")
    # Petit check de stats pour voir la répartition
    print("Nouvelle répartition :")
    print(df['Niveau'].value_counts())
    print("-" * 40)

if __name__ == "__main__":
    main()