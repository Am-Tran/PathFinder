import requests
from bs4 import BeautifulSoup

# 1. URL de recherche (Data Analyst)
url = "https://www.free-work.com/fr/tech-it/jobs?query=Data%20analyst"

# 2. Masque (User-Agent)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # SUR FREE-WORK :
    # Les titres des jobs sont souvent dans des balises <h3> ou des liens <a> avec une classe spécifique.
    # Mais une astuce solide est de chercher tous les liens qui contiennent "/jobs/" dans leur adresse.
    
    jobs_found = []
    
    # On cherche tous les liens (<a>) de la page
    all_links = soup.find_all('a')
    
    for link in all_links:
        href = link.get('href') # On récupère l'adresse du lien
        
        # Si le lien existe et qu'il contient "/jobs/", c'est probablement une offre
        if href and '/tech-it/jobs/' in href and len(link.get_text().strip()) > 5:
            titre = link.get_text().strip()
            
            # Petite astuce pour éviter les doublons (titre affiché 2 fois)
            if titre not in jobs_found:
                jobs_found.append(titre)
                print(f"Trouvé : {titre}")

    print(f"\nTotal : {len(jobs_found)} offres trouvées.")

else:
    print("Erreur de connexion :", response.status_code)