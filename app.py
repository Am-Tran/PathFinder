import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import settings


# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="PathFinder Job Market",
    page_icon="🚀",
    layout="wide"
)

# --- STYLE CUSTOM ---

settings.charger_style()

# --- CHARGEMENT DES DONNÉES ---
@st.cache_data
def load_data():
    file_path = "data/clean/global_job_market.csv"   
    if not os.path.exists(file_path):
        st.error(f"❌ Fichier introuvable : {file_path}")
        return None    
    try:
        df = pd.read_csv(file_path)
        df['Date_Publication'] = pd.to_datetime(df['Date_Publication'], errors='coerce')
        df['Date_Expiration'] = pd.to_datetime(df['Date_Expiration'], errors='coerce')
        return df

        
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
        return None

df = load_data()

if df is None:
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
ordre_niveaux = ["Stage / Alternance", "Junior", "Confirmé", "Senior", "Non spécifié"]
niveau_list = [n for n in ordre_niveaux if n in df['Niveau'].unique()]

choix_niveau = st.sidebar.multiselect(
    "Niveau de Séniorité", 
    niveau_list, 
    default=[], 
    placeholder="Tous les niveaux"
)
selected_niveau = choix_niveau if choix_niveau else niveau_list

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

# --- APPLICATION DES FILTRES ---
df_filtered = df[
    (df['Source'].isin(selected_source)) &
    (df['Type_Contrat'].isin(selected_contrat)) &
    (df['Ville'].isin(selected_ville)) &
    (df['Niveau'].isin(selected_niveau))
]
# Affichage du nombre de résultats en temps réel dans la sidebar
st.sidebar.markdown("---")


if df_filtered.empty:
    st.warning("Aucune offre ne correspond à ces critères.")
    st.stop()

# --- 4. GESTION DES ONGLETS ---
tab_actuel, tab_trends = st.tabs(["⚡ Aujourd'hui", "📅 Évolution & Tendances"])

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


    # --- ANALYSE DES STACKS (Compétences) ---
    st.markdown("---")
    st.subheader("🛠️ Les Technologies les plus demandées")   
        
    stack_data = df_active['Tech_Stack'].dropna().str.split(', ').explode()

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
            title='Niveau de Séniorité',
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

           
            # --- GRAPHIQUE VOLUME ---
            st.markdown("#### 📈 Dynamique des Recrutements")
            volume_par_mois = df_trends.groupby('Mois').size().reset_index(name='Nombre d\'offres')
            
            fig_evol = px.area(
                df_weekly,
                x='Semaine',
                y='Nombre d\'offres',
                markers=True, 
                title="Évolution du nombre d'offres publiées"
                )
            fig_evol.update_layout(
                font=dict(size=taille_police),
                title=dict(font=dict(size=taille_police + 2)),
                xaxis=dict(tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                yaxis=dict(tickfont=dict(size=taille_police), title_font=dict(size=taille_police)),
                hovermode="x unified"
                )
            st.plotly_chart(fig_evol, width="stretch")

            st.divider() # Ligne de séparation visuelle

            # --- ANALYSE DES STACKS ---
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

                st.plotly_chart(fig_tech, width="stretch")

                st.divider() # Séparation visuelle
            
                # --- GRAPHIQUE TYPES DE CONTRATS ---
                
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

                st.plotly_chart(fig_contrat, width="stretch")
    else:
        st.info("Sélectionnez au moins une compétence pour voir l'évolution.")
            

        #st.warning("Pas assez de données historiques pour afficher les tendances.")