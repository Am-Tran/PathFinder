import os
import pandas as pd

def sauvegarde_securisee(df, chemin_fichier):
    """
    Sauvegarde un DataFrame de manière atomique pour éviter la corruption.
    1. Écrit dans un fichier .tmp
    2. Renomme le .tmp en .csv (opération instantanée et sûre)
    """
    if df is None or df.empty:
        print("⚠️ [Utils] Pas de données à sauvegarder.")
        return

    chemin_temp = chemin_fichier + ".tmp"
    
    try:
        print(f"💾 [Utils] Sauvegarde en cours vers {os.path.basename(chemin_fichier)} ...")
        
        # 1. Écriture dans le fichier temporaire
        df.to_csv(chemin_temp, index=False, encoding='utf-8-sig')
        
        # 2. Remplacement atomique
        if os.path.exists(chemin_temp):
            os.replace(chemin_temp, chemin_fichier)
            print("✅ [Utils] Sauvegarde réussie (Fichier sécurisé).")
            
    except Exception as e:
        print(f"❌ [Utils] ERREUR CRITIQUE lors de la sauvegarde : {e}")
    finally:
        # Nettoyage
        if os.path.exists(chemin_temp):
            try:
                os.remove(chemin_temp)
            except:
                pass

def prepare_environment():
    """Crée les dossiers nécessaires s'ils n'existent pas."""
    folders = ["data/raw", "data/enriched", "data/clean"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Dossier créé : {folder}")