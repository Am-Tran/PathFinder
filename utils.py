import os
import pandas as pd

mapping_metier = {
    "Data Analyst": "Data Analyst",
    "Analyste de données": "Data Analyst",
    "Data Scientist": "Data Scientist",
    "Business Analyst": "Business Analyst",
    "Business Intelligence": "Business Analyst",
    #"Data Engineer": "Data Engineer"
}

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


def load_data(_client, table_name="Data_Analyst", batch_size=1000, limit=None, filters=None):
    """
    Télécharge les données d'une table Supabase proprement.
    Mettre les filtres dans un dictionnaire.
    """
    if filters is None:
        filters = {}
    try:
        all_rows = []
        start = 0
        
        while True:
            if filters.get("column"):
                query = _client.table(table_name).select(filters["column"])
            else:
                query = _client.table(table_name).select("*")
            if filters.get("source"):
                query = query.eq("Source", filters["source"])                
            if filters.get("only_active"):                
                query = query.is_("Date_Expiration", "null")            
            if filters.get("statut"):
                query = query.eq("Statut", filters["statut"])
            if filters.get("date_pub"):
                query = query.eq("Date_Publication", filters["date_pub"])
            if limit is not None:
                # Mode Test : On prend juste ce qui est demandé et on s'arrête
                query = query.order("Date_Publication", desc=True)
                response = query.limit(limit).execute()
                all_rows.extend(response.data)
                break 
            else:
                # Mode Production : Exécution paginée pour tout récupérer
                response = query.range(start, start + batch_size - 1).execute()
            
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

def upsert_data(_client, table_choisie, liste_donnees):
    """Envoie la mémoire tampon vers Supabase d'un seul coup."""
    if not liste_donnees:
        print("⚠️ Aucune donnée en mémoire à sauvegarder.")
        return
        
    print(f"\n🚀 Envoi de {len(liste_donnees)} offres vers Supabase...")
    try:
        # On envoie par paquets de 1000 pour respecter les limites du réseau
        for i in range(0, len(liste_donnees), 1000):
            batch = liste_donnees[i : i + 1000]
            _client.table(table_choisie).upsert(batch, on_conflict="URL").execute()
            
        print(f"✅ SUCCÈS CLOUD : {len(liste_donnees)} Offres sauvegardées.")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi à Supabase : {e}")


import msvcrt
import time

def verifier_pause_manuelle():
    """Met en pause si '1' est pressé, et attend 'Entrée' pour reprendre."""
    
    # 1. On vérifie si une touche a été pressée dans la console (sans bloquer le code)
    if msvcrt.kbhit():
        touche = msvcrt.getch() # On capture la touche
        
        # 2. Si c'est la touche '1' (lue comme du binaire b'1')
        if touche == b'1':
            print("\n⏸️ PAUSE MANUELLE ACTIVÉE.")
            print("👉 Résolvez le problème sur le navigateur, puis appuyez sur 'Entrée' dans cette console pour reprendre...")
            
            # 3. On bloque le script dans une boucle infinie
            while True:
                # On attend une nouvelle frappe
                if msvcrt.kbhit():
                    touche_reprise = msvcrt.getch()
                    # Si c'est la touche 'Entrée' (le retour chariot b'\r')
                    if touche_reprise == b'\r':
                        print("▶️ REPRISE DU SCRIPT.\n")
                        break # On casse la boucle, le script reprend !
                
                time.sleep(0.1) # Petite pause pour ne pas faire chauffer le processeur


import msvcrt
import time
import sys
import winsound

def verifier_blocage_et_pause(driver):
    """Détecte un Time-out DataDome, nettoie la session et attend avant de reprendre."""
    
    source = driver.page_source.lower()   
   
    if "data-dd" in source or "captcha" in source or "restreint" in source:
        print("\n🚨 ALERTE ROUGE : Blocage DataDome détecté (Time-out) !", file=sys.stderr)
        #winsound.Beep(1000, 1000)
        
        # 1. Nettoyage total de la mémoire
        print("🧹 Nettoyage des cookies et du stockage local...", file=sys.stderr)
        driver.delete_all_cookies()
        try:
            driver.execute_script("window.localStorage.clear();")
            driver.execute_script("window.sessionStorage.clear();")
        except:
            pass # Si le script javascript échoue, on ignore
        
        # 2. Mise en pause de 10 minutes
        print("⏳ Mise en pause de 10 minutes pour purger l'IP...", file=sys.stderr)
        for minute in range(10, 0, -1):
            print(f"   ... reprise dans {minute} minute(s)", file=sys.stderr)
            time.sleep(60) 
            
        # 3. Reprise
        print("▶️ REPRISE DU SCRIPT. Rechargement de la page...", file=sys.stderr)
        driver.refresh()
        
        # On laisse à la nouvelle page le temps d'apparaître
        time.sleep(3)