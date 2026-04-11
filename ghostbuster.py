import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# 1. --- CONNEXION ---
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# On cible la date d'aujourd'hui (celle de l'erreur du Ghostbuster)
date_jour = datetime.now().strftime("%Y-%m-%d")
print(f"🚑 Démarrage de l'opération Résurrection pour la date du {date_jour}...")

# 2. --- RECHERCHE DES VICTIMES ---
victimes = []
start = 0
batch_size = 1000

while True:
    # On cherche toutes les offres qui ont été marquées comme expirées aujourd'hui
    response = supabase.table("Data_Analyst") \
        .select("URL") \
        .eq("Date_Expiration", date_jour) \
        .range(start, start + batch_size - 1) \
        .execute()
    
    batch = response.data
    if not batch: 
        break
    
    victimes.extend(batch)
    
    if len(batch) < batch_size: 
        break
    start += batch_size

print(f"🧟 Offres trouvées à ressusciter : {len(victimes)}")

# 3. --- LA RÉSURRECTION ---
if len(victimes) > 0:
    print("✨ Nettoyage de la date d'expiration en base de données...")
    
    # On prépare le paquet : on renvoie les URL avec une Date_Expiration vide (None)
    payload = [{"URL": offre["URL"], "Date_Expiration": None} for offre in victimes]
    
    for i in range(0, len(payload), batch_size):
        batch = payload[i:i+batch_size]
        supabase.table("Data_Analyst").upsert(batch, on_conflict="URL").execute()
        print(f"   ✅ {len(batch)} offres ressuscitées...")
        
    print("🎉 Sauvetage terminé ! Va rafraîchir ton application Streamlit, tout est redevenu normal.")
else:
    print("✅ Aucune offre à ressusciter trouvée pour cette date.")