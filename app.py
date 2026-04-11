import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import settings
from dotenv import load_dotenv
from supabase import create_client


# region 1. --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="PathFinder Job Market",
    page_icon="🚀",
    layout="wide"
)

# --- STYLE CUSTOM ---

settings.charger_style()

# --- CHARGEMENT DES DONNÉES ---

if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

# Petite fonction dédiée pour chasser la clé, peu importe où Streamlit la cache
def fetch_key(key_name):
    # Tentative 1 : L'environnement système (le plus robuste sur le Cloud)
    val = os.getenv(key_name)
    if val: 
        return val
    
    # Tentative 2 : Le coffre-fort Streamlit (avec try/except, sans utiliser .get)
    try:
        return st.secrets[key_name]
    except Exception:
        return None

SUPA_URL = fetch_key("SUPABASE_URL")
SUPA_KEY = fetch_key("SUPABASE_KEY")

if not SUPA_URL or not SUPA_KEY:
    # Ce message nous dira exactement ce qui est vide si ça plante encore
    st.error(f"❌ Échec critique. Environnement: {'SUPABASE_URL' in os.environ} | Secrets: {len(st.secrets)}")
    st.stop()


@st.cache_resource(ttl=43200)
def get_supabase_client(url, key):   
    # 3. Le crash-test bavard
    if not url or not key:
        # Ça va afficher sur l'écran la liste des mots-clés que Streamlit connaît
        st.error(f"❌ Clés introuvables. Ce que Streamlit voit : {list(st.secrets.keys())}")
        st.stop()        
    return create_client(url, key)


@st.cache_data(ttl=43200)
def load_data(_client, batch_size=1000):
    try:
        all_rows = []
        start = 0
        while True:
            end = start + batch_size - 1
            response = (
                _client
                .table("Data_Analyst")
                .select("*")
                .range(start, end)
                .execute()
            )
            batch = response.data
            if not batch:
                break
            all_rows.extend(batch)

            # Si le lot retourné est plus petit que batch_size,
            # on a atteint la fin
            if len(batch) < batch_size:
                break

            start += batch_size

        df = pd.DataFrame(all_rows)
        if not df.empty:
            if "Source" in df.columns:
                df["Source"] = df["Source"].astype(str).str.strip()
            for col in ["Date_Publication", "Date_Expiration"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    except Exception as e:
        st.error(f"Erreur lors du chargement Supabase : {e}")
        return pd.DataFrame()


    
supabase = get_supabase_client(SUPA_URL, SUPA_KEY)
with st.spinner('🚀 Synchronisation avec la base de données Pathfinder...'):
    df = load_data(supabase)

if df.empty:
    st.warning("⚠️ Aucune donnée trouvée dans la base.")
    st.stop()

# --- TITRE ---
st.title("🔎 PathFinder : Analyse du Marché Data")
st.markdown(f"**{len(df)}** offres analysées provenant de **France Travail, APEC** et **Welcome to the Jungle**.")

# --- SIDEBAR (FILTRES) ---
#st.sidebar.header("Filtres").venv

# 1. Filtre Source
source_list = df['Source'].unique().tolist()
choix_source = st.sidebar.multiselect(
    "Source", 
    source_list, 
    default=[], 
    placeholder="Toutes les sources"
)
selected_source = choix_source if choix_source else source_list

# 2. Filtre Contrat
contrat_list = sorted(df['Type_Contrat'].dropna().unique().tolist())
choix_contrat = st.sidebar.multiselect(
    "Type de Contrat", 
    contrat_list, 
    default=[], 
    placeholder="Tous les contrats"
)
selected_contrat = choix_contrat if choix_contrat else contrat_list

# 3. Filtre Ville (Top 20)
top_villes = df['Ville'].value_counts().head(20).index.tolist()
ville_list = df['Ville'].dropna().unique().tolist()

choix_ville = st.sidebar.multiselect(
    "Filtrer par Ville", 
    top_villes, 
    default=[], 
    placeholder="Toutes les villes"
)
selected_ville = choix_ville if choix_ville else ville_list

# 4. Filtre Niveau
ordre_niveaux = ["En formation", "Junior", "Confirmé", "Senior", "Non spécifié"]
niveau_list = [n for n in ordre_niveaux if n in df['Niveau'].unique()]

choix_niveau = st.sidebar.multiselect(
    "Niveau de Séniorité", 
    niveau_list, 
    default=[], 
    placeholder="Tous les niveaux"
)
selected_niveau = choix_niveau if choix_niveau else niveau_list

# --- Filtre Inclusion ---
st.write("")
st.write("")
c1, c2 = st.sidebar.columns([0.5, 0.7])
with c1:
    # Ton titre (le margin-bottom réduit l'espace sous le titre pour l'alignement)
    st.markdown("### ♿ Inclusion")

with c2:
    # label_visibility="hidden" cache le texte par défaut de la checkbox
    rqth_only = st.checkbox("Inclusion", label_visibility="hidden")

# --- PARAMÈTRES D'AFFICHAGE ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Affichage")
taille_police = st.sidebar.slider(
    "Taille du texte des graphes", 
    min_value=10, 
    max_value=30, 
    value=17, # Valeur par défaut
    step=1
)

st.sidebar.markdown("---")
st.sidebar.header("🔄 Données")
if st.sidebar.button("Forcer la mise à jour"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

# --- APPLICATION DES FILTRES ---
df_filtered = df[
    (df['Source'].isin(selected_source)) &
    (df['Type_Contrat'].isin(selected_contrat)) &
    (df['Ville'].isin(selected_ville)) &
    (df['Niveau'].isin(selected_niveau))
]

if rqth_only:    
    df_filtered = df_filtered[df_filtered['Handicap_Friendly'] == True]

if df_filtered.empty:
    st.warning("Aucune offre ne correspond à ces critères.")
    st.stop()

# --- 4. GESTION DES ONGLETS ---
tab_actuel, tab_trends, tab_a_propos = st.tabs(["⚡ Aujourd'hui", "📅 Évolution & Tendances", "ℹ️ À propos de PathFinder"])

# endregion
# region 2. Onglet 1
# ====================================================================
# ONGLET 1 : MARCHÉ ACTUEL
# ====================================================================
with tab_actuel:
    st.markdown("### 🎯 Marché actuel")
    df_active = df_filtered[df_filtered['Date_Expiration'].isna()]

    # --- KPI ---
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    nb_offres = len(df_active)
    df_salaires = df_active[df_active['Salaire_Annuel'].notna()]
    salaire_moyen = df_salaires['Salaire_Annuel'].mean()

    col1.metric("Offres affichées",
                nb_offres,
                help="Nombre d'offres actuellement en ligne (non expirées) correspondant à vos filtres de la barre latérale."
                )
    col2.metric("Salaire Moyen Estimé",
                f"{salaire_moyen:,.0f} €" if nb_offres > 0 and not pd.isna(salaire_moyen) else "N/A",
                help="Moyenne des salaires bruts annuels extraits. Pour les fourchettes (ex: 40-50k), la valeur moyenne est utilisée."
                )
    col3.metric("Offres avec salaire affiché",
                f"{len(df_salaires)}",
                help="Nombre d'offres qui mentionnent explicitement un salaire. Le salaire moyen est calculé uniquement sur cet échantillon."
                )

    # --------------------------------------------------
    # --- GRAPHE REPARTITION PAR VILLE ---
    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("📍 Répartition par Ville")
        ville_counts = df_active['Ville'].value_counts().head(10).reset_index()
        ville_counts.columns = ['Ville', 'Nombre']
        ville_counts = ville_counts.sort_values(by="Nombre", ascending=True)
        fig_ville = px.bar(ville_counts, x='Nombre', y='Ville', orientation='h', color='Nombre', title="Top 10 Villes")
        fig_ville.update_layout(                
            font=dict(size=taille_police),
            title=dict(
                font=dict(size=taille_police + 2),
                x=0.5
            ),
            coloraxis_showscale=False,
            xaxis=dict(
                title_font=dict(size=taille_police), # Le mot "Offres"
                tickfont=dict(size=taille_police)    # Les chiffres 0, 10, 20...
            ),
            yaxis=dict(
                title_font=dict(size=taille_police), # Le mot "Ville"
                tickfont=dict(size=taille_police)    # Les mots Paris, Lyon...
            )
        )
        fig_ville.update_traces(textfont_size=taille_police)
        # CORRECTION ICI : width="stretch" au lieu de use_container_width
        st.plotly_chart(fig_ville, width="stretch")

    # --- GRAPHE SALAIRES PAR SOURCE ---
    with col_g2:
        st.subheader("💰 Distribution des Salaires")
        if not df_salaires.empty:
            fig_salaire = px.box(
                df_salaires,
                x='Source',
                y='Salaire_Annuel',
                color='Source',
                title="Salaires par Source",
                color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_salaire.update_layout(
            font=dict(size=taille_police), # Taille globale
            title=dict(font=dict(size=taille_police + 2), x=0.5),
            showlegend=False, # Souvent inutile sur un boxplot coloré par X, ça gagne de la place
            
            # Axe X (Sources : Indeed, Glassdoor...)
            xaxis=dict(
                title_font=dict(size=taille_police),
                tickfont=dict(size=taille_police)
            ),
            # Axe Y (Montants : 30k, 40k...)
            yaxis=dict(
                title_font=dict(size=taille_police),
                tickfont=dict(size=taille_police)
            )
        )
            st.plotly_chart(fig_salaire, width="stretch")
        else:
            st.info("Pas assez de données de salaire pour afficher le graphique.")

    # --------------------------------------------------
    # --- ANALYSE DES STACKS (Compétences) ---
    st.markdown("---")
    st.subheader("🛠️ Les Technologies les plus demandées")   
        
    stack_data = df_active['Tech_Stack'].dropna().str.split(', ').explode()
    stack_data = stack_data.str.strip()
    stack_data = stack_data[stack_data != ""]

    # 2. Calcul nombre occurences
    stack_series = stack_data.value_counts().reset_index()
    stack_series.columns = ['Tech', 'Mentions']

    # 3. On trie pour que le .tail(10) prenne bien les plus grands
    stack_series = stack_series.sort_values(by='Mentions', ascending=True)  

    # --- LE GRAPHIQUE STACKS TECH---    

    if not stack_series.empty:
        fig_stack = px.bar(
            stack_series.tail(10), # Prend les 10 plus grands (car trié ascendant)
            x='Mentions',
            y='Tech',
            orientation='h',
            text='Mentions',
            title="🏆 Top 10 des Compétences Techniques",
            color='Mentions',
            color_continuous_scale='blugrn' 
        )

        fig_stack.update_layout(
            font=dict(size=taille_police),
            title=dict(font=dict(size=taille_police + 2), x=0.5), # +4 pour que le titre soit un peu plus gros
            coloraxis_showscale=False,
            xaxis=dict(
                title="Nombre d'offres",
                title_font=dict(size=taille_police),
                tickfont=dict(size=taille_police)
            ),
            yaxis=dict(
                title="",
                title_font=dict(size=taille_police),
                tickfont=dict(size=taille_police)
            ),
            plot_bgcolor='rgba(0,0,0,0)' # Fond transparent pour faire propre
        )
        
        # Met le texte (nombre) à l'extérieur de la barre pour la lisibilité
        fig_stack.update_traces(textfont_size=taille_police, textposition='outside')

        st.plotly_chart(fig_stack, width="stretch")
    else:
        st.info("Aucune compétence technique détectée dans les offres sélectionnées.")
    
    # --------------------------------------------------

    # --- POSITION DES DONUTS ---

    st.markdown("---")
    col1, col2 = st.columns(2)

    # --- GRAPHIQUE CONTRAT ---
    with col1:
        st.subheader("📄 Répartition des Contrats")

        fig_contrat = px.pie(
            df_active, 
            names='Type_Contrat', 
            title='Répartition par Type de Contrat',
            hole=0.4,            
            color_discrete_sequence=settings.palette_c
        )

        fig_contrat.update_layout(
            margin=dict(l=20, r=20, t=90, b=160),
            font=dict(size=taille_police),
            legend=dict(
                font=dict(size=taille_police),
                orientation="h",   # Légende horizontale
                yanchor="top",     
                y=-0.5,            # On la place juste en dessous du graph
                xanchor="center",  
                x=0.5              # On la centre
            ),
            title=dict(
                font=dict(size=taille_police + 2), # Le titre un peu plus gros par défaut
                x=0.5
            )
        )

        fig_contrat.update_traces(
            textfont_size=taille_police # On force la taille des chiffres internes
        )

        st.plotly_chart(fig_contrat, width="stretch", height=500)

    # --- GRAPHIQUE EXP ---
    with col2:
        st.subheader("🎓 Niveau de Séniorité Ciblé")

        fig_niveau = px.pie(
            df_filtered, 
            names='Niveau', 
            title='Répartition par Séniorité',
            hole=0.4,
            color_discrete_sequence=settings.palette_b
        )

        fig_niveau.update_layout(
            margin=dict(l=20, r=20, t=90, b=160),
            font=dict(size=taille_police),        
            legend=dict(
                font=dict(size=taille_police),
                orientation="h",
                yanchor="top",
                y=-0.5,
                xanchor="center",
                x=0.5
            ),
            title=dict(
                font=dict(size=taille_police +2),
                x=0.5
            )
        )

        fig_niveau.update_traces(
            textfont_size=taille_police
        )

        st.plotly_chart(fig_niveau, width="stretch", height=500)

    # --- TABLEAU DE DONNÉES ---
    # Ctrl + : 
    st.markdown("---")
    with st.expander("📋 Explorateur d'Offres"):    

        colonnes_a_afficher = [
            'Titre', 
            'Ville', 
            'Type_Contrat', 
            'Teletravail',
            'Date_Publication', 
            'URL'              # ou 'URL' selon ton fichier
        ]
        cols_final = [c for c in colonnes_a_afficher if c in df_active.columns]

        st.dataframe(
        df_active[cols_final],
        width="stretch", # Prend toute la largeur
        hide_index=True,          # Cache la colonne d'index (0, 1, 2...)
        
        # 3. Configuration de l'affichage (Liens et Formats)
        column_config={
            "Date_Publication": st.column_config.DateColumn(
                "Date", 
                format="DD/MM/YYYY"
            ),
            "URL": st.column_config.LinkColumn(
                "🔗Lien", display_text="https://(.*?)/" # On garde simple pour l'instant
            ),
            # Optionnel : Renommer les en-têtes pour faire joli
            "Type_Contrat": st.column_config.TextColumn("Contrat"),
            "Teletravail": st.column_config.TextColumn("Télétravail"),
        }
        )
# endregion
# region 3. Onglet 2
# ====================================================================
# ONGLET 2 : ANALYSE TEMPORELLE
# ====================================================================
with tab_trends:  

    st.markdown("### ⏳ Historique et Tendances")
    #st.info("Cette vue inclut toutes les offres (actives et expirées) pour analyser l'évolution.")
    
    # 1. Évolution du volume d'offres par mois
    # On groupe par mois (M) sur la date de publication
    df_trends = df_filtered.dropna(subset=['Date_Publication']).copy()
    df_trends['Date_Publication'] = pd.to_datetime(df_trends['Date_Publication'])
        
    if not df_trends.empty:
        df_trends['Mois'] = df_trends['Date_Publication'].dt.to_period('M').astype(str)        

        # =========================================================
        # ✂️ FILTRE TEMPOREL (On coupe le début trop vide)
        # =========================================================
        # On s'assure que c'est bien un format date
        df_trends['Date_Publication'] = pd.to_datetime(df_trends['Date_Publication'])
        
        # On ne garde que ce qui est APRES start_date
        start_date = '2025-09-01'
        df_trends = df_trends[df_trends['Date_Publication'] >= start_date]

        # Marqueurs historiques
        Date_debut = "2026-01-26"

        # =========================================================

        # Si jamais le filtre est trop violent et qu'il ne reste rien :
        if df_trends.empty:
            st.warning(f"Pas assez de données après le {start_date} pour afficher les tendances.")
        else:
            df_trends['Semaine'] = df_trends['Date_Publication'].dt.to_period('W').apply(lambda r: r.start_time)
            df_weekly = df_trends.groupby('Semaine').size().reset_index(name="Nombre d'offres")

            # --- CALCUL DES KPIs HISTORIQUES ---
        
            # 1. Volume total sur la période
            total_offres = len(df_trends)        
            # 2. Nombre d'entreprises uniques
            # On normalise un peu (strip/upper) pour éviter de compter "Google" et "GOOGLE " en double
            nb_entreprises = df_trends['Entreprise'].str.strip().str.upper().nunique()
            
            # 3. Durée de vie moyenne des offres (Vélocité)
            # On ne garde que celles qui ont une date d'expiration (donc les offres finies/archivées)
            df_finished = df_trends.dropna(subset=['Date_Expiration']).copy()
            
            if not df_finished.empty:
                # Calcul de la différence en jours
                df_finished['Duree_Vie'] = (df_finished['Date_Expiration'] - df_finished['Date_Publication']).dt.days
                # On filtre les durées négatives (bugs de dates) ou nulles
                avg_duree = df_finished[df_finished['Duree_Vie'] > 0]['Duree_Vie'].mean()
                label_duree = f"{avg_duree:.0f} jours"
            else:
                label_duree = "N/A"

# ------------------------------------------------------------------------------------------------------------------------------------------------------

            # --- AFFICHAGE DU BANDEAU ---
            st.markdown("---")
            kpi1, kpi2, kpi3 = st.columns(3)

            kpi1.metric(
                label="Volume Analysé",
                value=f"{total_offres}",
                help="Nombre total d'offres (actives et expirées) dans l'historique filtré."
            )

            kpi2.metric(
                label="Entreprises Uniques",
                value=f"{nb_entreprises}",
                help="Nombre d'entreprises distinctes ayant publié au moins une offre."
            )

            kpi3.metric(
                label="Durée de vie moyenne",
                value=label_duree,
                help="Temps moyen entre la publication et l'expiration d'une offre."
            )
            
            st.markdown("---")

            st.info("ℹ️ **Note de lecture :** Le pic observé fin janvier correspond à l'initialisation de la base de données (récupération de l'historique des offres actives).")
           
# ------------------------------------------------------------------------------------------------------------------------------------------------------

            # ===== GRAPHIQUE VOLUME =====
            st.markdown("#### 📈 Dynamique des Recrutements")
            volume_par_mois = df_trends.groupby('Mois').size().reset_index(name='Nombre d\'offres')
            
            fig_evol = px.area(
                df_weekly,
                x='Semaine',
                y='Nombre d\'offres',
                markers=True, 
                title="Évolution du nombre d'offres publiées",
                color_discrete_sequence=["#ffba74"]               
                )
            fig_evol.update_layout(
                font=dict(size=taille_police),
                title=dict(font=dict(size=taille_police + 2)),
                xaxis=dict(tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                yaxis=dict(tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                hovermode="x unified"
                )
            fig_evol.add_vline(
                x=Date_debut, 
                line_width=2, 
                line_dash="dash", 
                line_color= "#2980b9"
                )
            fig_evol.add_annotation(
                x=Date_debut,
                y=1.05, # Juste au-dessus du graphe
                yref="paper", # Coordonnée relative (1.0 = haut du graphe)
                text="Initialisation (Stock)",
                showarrow=False,
                font=dict(color="#2980b9", size=taille_police)
                )
            st.plotly_chart(fig_evol, width="stretch")

            

            st.divider() # Ligne de séparation visuelle

# ------------------------------------------------------------------------------------------------------------------------------------------------------

            # ===== ANALYSE DES STACKS =====
            st.markdown("#### 🔥 Popularité des compétences Tech")
            tech_series = df_trends['Tech_Stack'].dropna().str.split(', ').explode()
            technos_dispo = sorted(tech_series.dropna().unique())

            # --- Sélection par défaut ---
            # On veut afficher Python et SQL par défaut, MAIS seulement s'ils existent dans la liste
            # (Sinon ça plante si tu filtres sur un métier qui n'utilise pas Python)
            default_choices = ["Python", "SQL", "Power BI", "Excel", "Tableau"]
            valid_defaults = [t for t in default_choices if t in technos_dispo]

            # --- Multiselect ---
            selected_techs = st.multiselect(
                "Comparer les technos :", 
                technos_dispo, 
                default=valid_defaults
            )

            # --- Boucle de calcul ---
            if selected_techs:
                # On prépare l'index avec tous les mois
                #all_months = sorted(df_trends['Mois'].unique())
                all_weeks = sorted(df_trends['Semaine'].unique())
                data_tech = pd.DataFrame(index=all_weeks)

                for tech in selected_techs:
                    # On utilise la colonne Tech_Stack
                    mask = df_trends['Tech_Stack'].str.contains(tech, case=False, regex=False, na=False)
                    counts = df_trends[mask].groupby('Semaine').size()
                    data_tech[tech] = counts

                data_tech = data_tech.fillna(0)           
                
                fig_tech = px.line(
                    data_tech, 
                    markers=True, 
                    title="Évolution des technologies demandées",
                    color_discrete_sequence=settings.palette_c,
                    height=650
                )
                fig_tech.update_layout(
                    font=dict(size=taille_police),
                    title=dict(font=dict(size=taille_police + 2)),
                    xaxis=dict(title="Mois", tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                    yaxis=dict(title="Nombre d'offres", tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                    legend=dict(font=dict(size=taille_police)),
                    hovermode="x unified"
                )
                fig_tech.add_vline(
                    x=Date_debut, 
                    line_width=2, 
                    line_dash="dash", 
                    line_color= "#2980b9"
                    )
                fig_tech.add_annotation(
                    x=Date_debut,
                    y=1.05, # Juste au-dessus du graphe
                    yref="paper", # Coordonnée relative (1.0 = haut du graphe)
                    text="Initialisation (Stock)",
                    showarrow=False,
                    font=dict(color="#2980b9", size=taille_police)
                    )
            
                st.plotly_chart(fig_tech, width="stretch")

                st.divider() # Séparation visuelle
            
# ------------------------------------------------------------------------------------------------------------------------------------------------------

                # ===== GRAPHIQUE TYPES DE CONTRATS =====
                
                st.markdown("#### 📜 Évolution des Types de Contrats")

                # 1. Préparation des données (Pivot pour gérer les mois vides)
                # On groupe par Mois et Contrat, puis on 'unstack' pour avoir les contrats en colonnes
                # fill_value=0 est CRUCIAL : si un mois n'a pas de "Stage", ça met 0 au lieu de rien
                evol_contrat = df_trends.groupby(['Semaine', 'Type_Contrat']).size().unstack(fill_value=0)

                # 2. Création du graphique Plotly
                fig_contrat = px.line(
                    evol_contrat, 
                    markers=True, 
                    title="Répartition des contrats dans le temps",
                    color_discrete_sequence=settings.palette_b,
                    height=600 # Une hauteur moyenne suffit ici
                )

                # 3. Application du style (Cohérent avec les autres graphs)
                fig_contrat.update_layout(
                    font=dict(size=taille_police),
                    title=dict(font=dict(size=taille_police + 2)),
                    xaxis=dict(title="Semaine", tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                    yaxis=dict(title="Nombre d'offres", tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                    legend=dict(title="Type de Contrat", font=dict(size=taille_police)),
                    hovermode="x unified"
                )

                fig_contrat.add_vline(
                    x=Date_debut, 
                    line_width=2, 
                    line_dash="dash", 
                    line_color= "#2980b9"
                    )
                fig_contrat.add_annotation(
                    x=Date_debut,
                    y=1.05, # Juste au-dessus du graphe
                    yref="paper", # Coordonnée relative (1.0 = haut du graphe)
                    text="Initialisation (Stock)",
                    showarrow=False,
                    font=dict(color="#2980b9", size=taille_police)
                    )

                st.plotly_chart(fig_contrat, width="stretch")
    else:
        st.info("Sélectionnez au moins une compétence pour voir l'évolution.")
            

        #st.warning("Pas assez de données historiques pour afficher les tendances.")

# endregion
# region 4. Onglet 3
# ====================================================================
# ONGLET 3 : A PROPOS
# ====================================================================
with tab_a_propos:
   st.markdown("""
    <div style="text-align: justify; max-width: 950px;">
               
    **PathFinder** est une pipeline de données ETL (Extract, Transform, Load) automatisé et un tableau de bord interactif conçu pour monitorer les tendances du marché de l'emploi Data en France.
               
    #### 💡 Pourquoi ce projet ?
    Trouver son premier poste implique de traiter un grand volume d'informations souvent éparpillées.  
    Au lieu de multiplier les recherches manuelles sur différentes plateformes, j'ai développé cet outil pour répondre à des besoins concrets :
    * **Centraliser :** Regrouper les opportunités de France Travail, l'APEC et Welcome to the Jungle au sein d'une interface unique pour optimiser le temps de recherche.
    * **Dédoublonner :** Éviter de lire plusieurs fois la même annonce publiée sur des plateformes différentes.
    * **Analyser :** Mieux comprendre quelles sont les compétences (Tech Stack) réellement demandées aujourd'hui.
    * **Monitorer :** Suivre l'évolution du marché dans le temps (volume d'annonces, types de contrats, durée de vie moyenne des offres) pour dégager de véritables tendances de fond.
               
    
    #### 🛠️ Architecture & Stack Technique
    Ce projet couvre l'ensemble du cycle de vie de la donnée (du Data Engineering à la Data Analytics) :
    
    * **Collecte & Automatisation :** Scraping quotidien automatisé via des pipelines *GitHub Actions*.
    * **Stockage :** Base de données Cloud relationnelle gérée sur *Supabase*.
    * **Traitement :** Nettoyage, harmonisation et filtrage dynamique avec *Pandas*.
    * **Visualisation :** Interface interactive propulsée par *Streamlit*.
    
    #### 🎯 La stratégie derrière les données
    Conçu pour rendre la recherche d'emploi la plus pertinente possible au-delà de la simple centralisation, l'outil intègre des filtres de ciblage précis (ville, contrat, niveau d'expérience).  
    En parallèle, il analyse en profondeur d'autres métriques clés des offres : le nombre d'années d'expérience minimal exigé, ainsi que le salaire proposé 
    (en appliquant des tranches de revenus adaptées selon que le poste se situe en région parisienne, dans une grande métropole ou ailleurs en France). 
    Cette analyse permet de s'adapter à un marché complexe et de décrypter les véritables attentes que peuvent avoir différentes entreprises derrière un même intitulé. 
    En croisant ces informations, PathFinder permet de dénicher des opportunités cachées et de postuler de manière plus stratégique.
    
    ---
    *Code source et détails de l'architecture disponibles sur GitHub.*
    
    </div>
    """, unsafe_allow_html=True)
# endregion 