import pandas as pd
import os
from datetime import datetime

# --- CONFIGURATION ---

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
CSV_PATH = os.path.join(project_root, "data", "enriched", "offres_apec_full.csv")

if not os.path.exists(CSV_PATH):
    print("❌ Fichier introuvable.")
    exit()

# Chargement
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig', dtype=str)
print(f"📂 Fichier chargé : {len(df)} offres au total.")

# --- OPTIONS DE RÉPARATION ---
print("\nQue voulez-vous faire ?")
print("1. Annuler UNIQUEMENT les suppressions d'aujourd'hui (Recommandé)")
print("2. Tout remettre à zéro (Considérer TOUTES les offres comme vivantes)")
choix = input("👉 Tapez 1 ou 2 : ")

compteur = 0

if choix == "1":
    date_jour = datetime.now().strftime("%d/%m/%Y")
    print(f"\n🔍 Recherche des offres marquées expirées le {date_jour}...")
    
    # On cherche les lignes où Date_Expiration est égale à aujourd'hui
    mask = df['Date_Expiration'] == date_jour
    compteur = mask.sum()
    
    # On remplace par NaN (vide)
    df.loc[mask, 'Date_Expiration'] = None
    print(f"🚑 {compteur} offres ont été ressuscitées (Date effacée).")

elif choix == "2":
    print("\n⚠️ ATTENTION : Cela va réactiver l'intégralité de votre historique.")
    confirm = input("Êtes-vous sûr ? (oui/non) : ")
    if confirm.lower() == "oui":
        compteur = df['Date_Expiration'].notna().sum()
        df['Date_Expiration'] = None # On vide toute la colonne
        print(f"✨ {compteur} offres ont été réactivées (Toute la colonne effacée).")
    else:
        print("Annulé.")
        exit()

else:
    print("Choix invalide.")
    exit()

# --- SAUVEGARDE ---
if compteur > 0:
    df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
    print("✅ Fichier sauvegardé et corrigé !")
else:
    print("🤷 Aucune modification n'était nécessaire.")