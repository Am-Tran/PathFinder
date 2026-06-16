from __future__ import annotations
import json
import re
import httpx
from bs4 import BeautifulSoup
import requests
import pandas as pd
import time
import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import lxml
import pytz
from datetime import datetime

# --- CONFIGURATION SUPABASE ---
table_choisie = "Data_Analyst"

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))

if root_dir not in sys.path:
    sys.path.append(root_dir)
from utils import fetch_key, mapping_metier, load_data

timezone_fr = pytz.timezone('Europe/Paris')
date_actuelle = datetime.now(timezone_fr).date()

# --- 1. CONFIGURATION ALGOLIA ---

# Clés publiques
ALGOLIA_APP_ID = "CSEKHVMS53"
ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
ALGOLIA_INDEX_FR = "wttj_jobs_production_fr_published_at_desc"
ALGOLIA_URL = (
    f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/"
    f"{ALGOLIA_INDEX_FR}/query"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",  # pas brotli (httpx nécessite la lib `brotli` pour ça)
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}
ALGOLIA_HEADERS = {
    **DEFAULT_HEADERS,
    "x-algolia-application-id": ALGOLIA_APP_ID,
    "x-algolia-api-key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
    "Referer": "https://www.welcometothejungle.com/",
    "Origin": "https://www.welcometothejungle.com",
}

ALGOLIA_FILTERS = "offices.country_code:FR"

def standardiser_metier(titre: str) -> str | None:
    """Cherche un métier connu dans le titre. Renvoie le métier standard, ou None."""
    if not titre:
        return None
    titre_lower = titre.lower()
    for cle, metier_standard in mapping_metier.items():
        if cle.lower() in titre_lower:
            return metier_standard
    return None

def _hit_to_raw(hit: dict) -> dict | None:
    """Convertit un hit Algolia en RawOffer."""
    title = hit.get("name") or hit.get("title")
    if not title:
        return None
    metier_propre = standardiser_metier(title)
    if not metier_propre:
        return None
    org = hit.get("organization") or {}
    company = org.get("name")
    offices = hit.get("offices") or []
    office = offices[0] if offices else {}
    city = office.get("city") or office.get("locality")    
    org_slug = org.get("slug")
    job_slug = hit.get("slug") or hit.get("reference")
    contract = hit.get("contract_type")
    url = (
        f"https://www.welcometothejungle.com/fr/companies/{org_slug}/jobs/{job_slug}"
        if org_slug and job_slug else None
    )
    if not url:
        return None
    description_longue = fetch_detail(url, hit)      

    return {
        "Titre": title,
        "Entreprise": company,
        "Ville": city,
        "Source": "Welcome to the Jungle",
        "URL": url,
        "Type_Contrat": standardiser_contrat(contract),
        "Date_Publication": hit.get("published_at"),
        "Description": description_longue,
        "Metier" : metier_propre,
        "Statut" : "Collecte"
    }

def fetch_list(*, keywords: list[str], max_pages: int = 5, urls_existantes: set = None) -> list[dict]:
        """Recherche via l'API Algolia publique de WTTJ.
        Renvoie une liste de dictionnaires prêts pour Supabase
        Filtre client : mots-clés IA/data (au cas où Algolia laisse passer du bruit).
        """
        results = []
        seen_urls = set(urls_existantes) if urls_existantes else set()

        with httpx.Client(headers=ALGOLIA_HEADERS, timeout=20.0, http2=True) as client:
            for kw in keywords:
                for page in range(max_pages):
                    body = {
                        "query": kw,
                        "filters": ALGOLIA_FILTERS,
                        "hitsPerPage": 50,
                        "page": page,
                    }
                    try:
                        resp = client.post(ALGOLIA_URL, json=body)
                        resp.raise_for_status()
                    except httpx.HTTPError as e:
                        print(f"⚠️ Arrêt de la requête Algolia : {e}")
                        break
                    data = resp.json()
                    hits = data.get("hits", [])
                    if not hits:
                        break

                    new_in_page = 0
                    for hit in hits:
                        off = _hit_to_raw(hit)
                        if not off:
                            continue
                        if off["URL"] and off["URL"] in seen_urls:
                            continue                   
                        
                        if off["URL"]:
                            seen_urls.add(off["URL"])
                            results.append(off)
                            new_in_page += 1

                    # Si on a moins de pages que prévu, arrêter
                    if data.get("nbPages", 0) <= page + 1:
                        break
                    if new_in_page == 0:
                        # Page entière déjà vue / tout filtré
                        break

                    time.sleep(0.8)

        return results


def fetch_detail(url: str, hit: dict) -> str | None:
    """Récupère la description complète via une simple requête HTTP."""
    description = None
    def _to_str(v):
        if not v:
            return ""
        if isinstance(v, list):
            return "\n".join(str(x) for x in v)
        return str(v)
    try:
        desc_parts = [_to_str(hit.get(k)) for k in ("summary", "profile", "key_missions")]
        description = "\n\n".join(p for p in desc_parts if p).strip() or None

        # Nettoyage HTML si présent (certains champs contiennent du HTML)
        if description and ("<" in description and ">" in description):
            description = BeautifulSoup(description, "lxml").get_text(separator="\n", strip=True)
            description = re.sub(r"\n{3,}", "\n\n", description)
        if description and len(description) > 300:
            return description

    except Exception as e:
        print(f"Erreur lors de la lecture de l'offre {url}: {e}")        
    try:
        # Petite pause pour ne pas stresser leur serveur
        time.sleep(0.5) 
        resp = httpx.get(url, headers=DEFAULT_HEADERS, timeout=10.0)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Méthode A : Les blocs ciblés
            blocs = []
            desc_block = soup.find(attrs={"data-testid": "job-section-description"})
            if desc_block:
                blocs.append("MISSIONS :\n" + desc_block.get_text(separator="\n", strip=True))
                
            profile_block = soup.find(attrs={"data-testid": "job-section-profile"})
            if profile_block:
                blocs.append("PROFIL RECHERCHÉ :\n" + profile_block.get_text(separator="\n", strip=True))
                
            if blocs:
                text_scrap = "\n\n".join(blocs)
                if len(text_scrap) > 300:
                    return text_scrap
                    
            # Méthode B : Fallback bourrin sur <article> ou <main>
            for tag in ['article', 'main']:
                content = soup.find(tag)
                if content:
                    text_scrap = content.get_text(separator="\n", strip=True)
                    if len(text_scrap) > 300:
                        return text_scrap

    except Exception as e:
        print(f"Erreur HTTP (fallback) pour {url}: {e}")
        
    # Si vraiment le web scraping échoue, on renvoie le bout de texte d'Algolia même s'il est court, 
    # c'est mieux que rien (ou None si c'est totalement vide)
    return description if description else None

def standardiser_contrat(contrat: str) -> str | None:
    """Standardise les types de contrat en français."""
    if not contrat:
        return None
    contrat = contrat.lower()
    if "full_time" in contrat:
        return "CDI"
    elif "temporary" in contrat:
        return "CDD"
    elif "freelance" in contrat:
        return "Freelance"
    elif "internship" in contrat or "apprenticeship" in contrat:
        return "Stage / Alternance"
    else:
        return None

def main():
    print("☁️ Initialisation de Supabase...")
    supabase_url = fetch_key("SUPABASE_URL")
    supabase_key = fetch_key("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        print("❌ ERREUR : Clés Supabase introuvables.")
        sys.exit(1)
    supabase = create_client(supabase_url, supabase_key)

    print("📥 Récupération du stock actuel pour éviter les doublons...")
    filters_wttj= {
    "source": "Welcome to the Jungle",
    "statut": "Actif",
    "column": "URL"
    }
    df_base = load_data(supabase, table_name=table_choisie, limit=None, filters = filters_wttj)
    urls_connues = set()
    if not df_base.empty:
        urls_connues = set(df_base['URL'].dropna())
    print(f"🛡️ {len(urls_connues)} offres WTTJ déjà en base. Elles seront ignorées.")
    print("🚀 Lancement du Scraper WTTJ...")    
    
    keywords = list(mapping_metier.keys())    
    print(f"🔍 Requêtes Algolia prévues pour : {keywords}")
    
    # C'est ICI que l'on remplit l'argument 'keywords' (le fameux kw de la boucle)
    offres_a_inserer = fetch_list(keywords=keywords, max_pages=3, urls_existantes=urls_connues)
    
    print(f"✅ Scraping terminé ! {len(offres_a_inserer)} offres validées.")
    
    # Injection dans Supabase
    if offres_a_inserer:
        # print("\n🔍 PREUVE PYTHON : Voici ce qu'on envoie à Supabase :")
        # print(offres_a_inserer[0])
        # print("\n")
        try:
            for i in range(0, len(offres_a_inserer), 1000):
                batch = offres_a_inserer[i:i+1000]
                supabase.table(table_choisie).upsert(batch, on_conflict="URL").execute()
            print("🎉 Données poussées avec succès sur Supabase !")
        except Exception as e:
            print(f"❌ Erreur lors de l'insertion Supabase : {e}")
    else:
        print("⚠️ Aucune offre trouvée correspondant aux critères.")


# --- EXÉCUTION DU SCRIPT ---

if __name__ == "__main__":  
    main()