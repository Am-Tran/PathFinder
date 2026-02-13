import subprocess
import os
import sys
import time
import threading
import pandas as pd

# --- CONFIGURATION ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# On définit les "CHAINES" de tâches par site
# Chaque chaîne s'exécutera toute seule, indépendamment des autres
TASKS = {
    "FRANCE_TRAVAIL": [
        os.path.join(PROJECT_ROOT, "scrapers", "francetravail", "api_francetravail.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "francetravail", "updater_francetravail.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "francetravail", "clean_francetravail.py"),
    ],
    "WTTJ": [
        os.path.join(PROJECT_ROOT, "scrapers", "wttj", "crawler_wttj.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "wttj", "scraper_wttj.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "wttj", "updater_wttj.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "wttj", "clean_wttj.py"),
    ],
    "APEC": [
        os.path.join(PROJECT_ROOT, "scrapers", "apec", "crawler_apec.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "apec", "scraper_apec.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "apec", "updater_apec.py"),
        os.path.join(PROJECT_ROOT, "scrapers", "apec", "clean_apec.py"),
    ]
}

SCRIPT_FUSION = os.path.join(PROJECT_ROOT, "fusion_csv.py")

# --- FONCTION WORKER (Exécutée par chaque Thread) ---
def run_chain(source_name, script_list):
    """
    Exécute une liste de scripts les uns après les autres pour une source donnée.
    """
    print(f"🔵 [{source_name}] Démarrage de la chaîne...")
    
    for script_path in script_list:
        script_name = os.path.basename(script_path)
        
        if not os.path.exists(script_path):
            print(f"❌ [{source_name}] Fichier introuvable : {script_name}")
            return # On arrête cette chaîne
            
        try:
            # On lance le script et on attend qu'il finisse avant de passer au suivant de la liste
            subprocess.run(
                [sys.executable, script_path], 
                check=True                
            )
            print(f"✅ [{source_name}] Étape terminée : {script_name}")
            
        except subprocess.CalledProcessError:
            print(f"❌ [{source_name}] ERREUR CRITIQUE sur {script_name}. Arrêt de la chaîne.")
            return # On arrête tout pour ce site
        except Exception as e:
            print(f"❌ [{source_name}] Erreur imprévue : {e}")
            return
    print(f"🏁 [{source_name}] CHAÎNE TERMINÉE AVEC SUCCÈS !")


# --- FONCTION ORCHESTRATEUR PRINCIPAL ---

def main():
    print("🚀 Démarrage du Pipeline...")
    
    # Variable pour stocker le DataFrame en cours de travail
    # (Doit être définie avant le try pour être accessible dans le except)
    start_global = time.time()
    threads = []

    try:       

        # --- ETAPE 1 : TRAITEMENTS ---        
        
        start_global = time.time()
        print(f"{'='*60}")
        print("⚙️ Démarrage parallèle (3 workers)")
        print(f"{'='*60}")

        threads = []

        # 1. CRÉATION ET LANCEMENT DES THREADS
        for source, scripts in TASKS.items():
            # On crée un Thread pour chaque source
            t = threading.Thread(target=run_chain, args=(source, scripts))
            threads.append(t)
            t.start()

        # 2. ATTENTE (BARRIÈRE)
        # Le script principal attend ici que les 3 threads aient fini
        for t in threads:
            t.join()

        print(f"\n{'='*60}")
        print("⏳ TOUS LES SCRAPERS ONT FINI. LANCEMENT DE LA FUSION...")
        print(f"{'='*60}")

        # 3. LANCEMENT DE LA FUSION (Seulement quand tout est fini)
        try:
            subprocess.run([sys.executable, SCRIPT_FUSION], check=True)
            print("\n🏆 TERMINÉ ! Tout le pipeline s'est exécuté.")
        except Exception as e:
            print(f"❌ Erreur lors de la fusion : {e}")

        duration = time.time() - start_global
        print(f"⏱️ Temps total d'exécution : {duration:.2f} secondes")

    except KeyboardInterrupt:
        print("\n\n🛑 INTERRUPTION MANUELLE (CTRL+C) SUR L'ORCHESTRATEUR")
        print("⚠️  Les sous-processus (scrapers) devraient s'arrêter d'eux-mêmes...")
        # Pas besoin de sauvegarder ici, car ce script ne manipule pas de données.
        # Ce sont les scripts enfants qui géreront leur propre arrêt.
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ ERREUR GLOBALE : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()