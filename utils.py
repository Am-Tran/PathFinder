import os
import pandas as pd

def sauvegarde_securisee(df, chemin_fichier):
    """
    Sauvegarde un DataFrame de manière atomique pour éviter la corruption.
    1. Écrit dans un fichier .tmp
    2. Renomme le .tmp en .csv (opération instantanée et sûre)
    Nécessite os, pandas as pd
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
    """
    Crée les dossiers nécessaires s'ils n'existent pas.
    Nécessite os
    """
    folders = ["data/raw", "data/enriched", "data/clean"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Dossier créé : {folder}")



def fetch_key(key_name):
    """
    Récupère une variable d'environnement de manière sécurisée.
    Fonctionne en Local (.env), sur GitHub Actions (Secrets), et sur Streamlit.
    Nécessite os
    """
    # 1. Chargement du fichier local .env si on est sur ton ordinateur
    if os.path.exists(".env"):
        from dotenv import load_dotenv
        load_dotenv() # Ne surcharge pas les variables existantes (ex: celles de GitHub)

    # 2. Tentative classique (OS / GitHub Actions / .env)
    val = os.getenv(key_name)
    if val: 
        return val  
    
    # 3. Tentative de secours via Streamlit (Si la fonction est appelée par le Dashboard)
    try:
        import streamlit as st
        if key_name in st.secrets:
            return st.secrets[key_name]
    except ImportError:
        pass # Streamlit n'est pas installé dans le robot (Updaters), c'est normal, on ignore.
    except Exception as e:
        print(f"⚠️ Erreur de lecture des secrets Streamlit : {e}")

    # 4. Échec
    print(f"❌ AVERTISSEMENT : La clé '{key_name}' est introuvable.")
    return None


def load_data(_client, table_name="Data_Analyst", batch_size=1000):
    """
    Télécharge toutes les données d'une table Supabase proprement.
    Gère la pagination automatiquement et renvoie un DataFrame nettoyé.
    Nécessite pandas as pd
    """
    try:
        all_rows = []
        start = 0
        
        while True:
            response = (
                _client
                .table(table_name)
                .select("*")
                .range(start, start + batch_size - 1)
                .execute()
            )
            
            batch = response.data
            if not batch: # Si la réponse est vide, on a tout lu
                break
                
            all_rows.extend(batch)

            # Si le lot retourné est plus petit que batch_size, on a atteint la fin
            if len(batch) < batch_size:
                break

            start += batch_size

        # Conversion en DataFrame
        df = pd.DataFrame(all_rows)
        
        if df.empty:
            print(f"⚠️ Aucune donnée trouvée dans la table {table_name}.")
            return df # On retourne le DataFrame vide

        # --- SÉCURITÉ ET NETTOYAGE ---
        if "Source" in df.columns:
            df["Source"] = df["Source"].astype(str).str.strip()
            
        for col in ["Date_Publication", "Date_Expiration"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    except Exception as e:
        print(f"❌ Erreur critique lors du chargement Supabase : {e}")
        return pd.DataFrame() # Retourne un DataFrame vide pour éviter le crash du script parent



    


