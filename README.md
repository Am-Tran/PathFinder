PathFinder : L'Analyseur du Marché de l'Emploi Data

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![Status](https://img.shields.io/badge/Status-Active-success)

**PathFinder** est une pipeline de données ETL (Extract, Transform, Load) et un dashboard interactif conçu pour **monitorer les tendances** du marché de l'emploi Data en France.
Plutôt que de naviguer sur plusieurs sites différents, ce dashboard regroupe et nettoie les données de **trois plateformes clés** (France Travail, APEC, Welcome to the Jungle) pour offrir une vision globale et centralisée des opportunités accessibles.

 * `🔗 (https://pathfinder-data.streamlit.app/)`

---

## Pourquoi ce projet ?

La recherche d'un premier emploi ou d'une alternance est souvent un parcours du combattant. J'ai créé cet outil pour répondre à des besoins concrets :
1.  **Centraliser :** Ne plus avoir à ouvrir 10 onglets par jour pour surveiller les mêmes mots-clés.
2.  **Dédoublonner :** Éviter de lire trois fois la même annonce publiée sur des sites différents.
3.  **Analyser :** Mieux comprendre quelles sont les compétences (Tech Stack) réellement demandées aux juniors aujourd'hui.

---

## Architecture & Pipeline

Le projet fonctionne de manière autonome via une suite de scripts Python exécutés de manière **hebdomadaire** (avec une architecture prête pour un passage en quotidien) :

### 1. Extraction (Scraping)
Des robots spécialisés récupèrent les offres sur des sources institutionnelles et Tech :
* **France Travail** (via API/Web)
* **Welcome to the Jungle** (WTTJ)
* **APEC**

### 2. Transformation & Nettoyage
* **Déduplication :** Identification des doublons via URL canoniques.
* **Harmonisation :** Standardisation des formats de dates et de lieux pour permettre le filtrage.
* **Gestion Temporelle (Persistance Historique):**
    * Si une offre est republiée, le système conserve la **date de publication originale** (la plus ancienne) pour calculer la vraie durée de vie.
    * Le statut (Actif/Expiré), lui, est mis à jour à la date la plus récente.
* **Ciblage Junior :**
    * Analyse sémantique des descriptions et titres pour identifier spécifiquement les opportunités ouvertes aux débutants (0-3 ans d'expérience).
    * Cohérence économique (utilisation des seuils salariaux pour confirmer qu'un poste est ouvert à un niveau d'entrée).


### 3. Visualisation (Streamlit)
Une application web interactive structurée en deux volets principaux :
* **Moteur de Recherche :** Filtrage dynamique des offres par mots-clés (Stack technique), localisation et type de contrat.
* **Market Intelligence :** Tableaux de bord pour visualiser les tendances du marché: **volume d'offres, typologie des contrats et stack technique.**

---

## Challenges Techniques & Solutions

### Le biais "Stock vs Flux"
Lors de l'initialisation de la base de données fin janvier 2026, j'ai observé un pic massif de 1800+ offres, suivi d'une chute à ~160 offres/semaine.
* **Analyse :** Ce n'était pas un effondrement du marché, mais la distinction entre le **Stock** (historique accumulé) et le **Flux** (nouvelles offres réelles).
* **Solution :** Implémentation de marqueurs visuels dans les graphiques pour distinguer la phase d'initialisation de la phase de croisière.

### Persistance des données
Mise en place d'un système de fusion (`pandas.concat` + `drop_duplicates`) robuste pour éviter l'écrasement de l'historique lors des mises à jour régulières.

---

## Stack Technique

* **Langage :** Python
* **Data Engineering :** Pandas, NumPy
* **Scraping :** Requests, BeautifulSoup
* **Visualisation :** Plotly Express, Streamlit
* **Versioning :** Git & GitHub

---

## Roadmap / Améliorations futures
- [x] **Extraction :** Scraping fonctionnel de 3 sources.
- [x] **Visualisation :** Dashboard Streamlit opérationnel.
- [x] **Déploiement :** Mise en production de l'application (Streamlit Cloud) pour accès public.
- [x] **Parsing :** Parsing avancé des salaires (Regex) pour normaliser toutes les rémunérations en Brut Annuel.
- [ ] **Base de données :** Passage du stockage CSV vers PostgreSQL (Supabase) pour fiabiliser les données et gérer la montée en charge.
- [ ] **Automatisation :** Fréquence : Passage d'un scraping hebdomadaire à un scraping quotidien (automatisé via GitHub Actions).
- [ ] **Sources :** Intégration de nouvelles plateformes.

👤 **Auteur**
* **Développé par Am-Tran** -[Mon LinkedIn](https://www.linkedin.com/in/am%C3%A9lie-tran-981325a5/)
