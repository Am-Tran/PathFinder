import os
from dotenv import load_dotenv
from supabase import create_client

# Charger les variables d'environnement
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

# Initialiser le client
supabase = create_client(url, key)

try:
    # On tente de lire une ligne de ta table Data_Analyst
    # Note : Vérifie bien que les majuscules correspondent au nom de ta table
    response = supabase.table("Data_Analyst").select("URL", "Titre").limit(1).execute()
    
    print("✅ Connexion réussie !")
    if response.data:
        print(f"Donnée trouvée : {response.data[0]['Titre']}")
    else:
        print("La table est connectée mais vide.")

except Exception as e:
    print(f"❌ Erreur : {e}")
try:
    # Change "Data_Analyst" par le nom exact de ta table si besoin
    response = supabase.table("Data_Analyst").select("URL").limit(1).execute()
    print("✅ Bravo ! Ton code communique parfaitement avec Supabase.")
except Exception as e:
    print(f"❌ Erreur : {e}")