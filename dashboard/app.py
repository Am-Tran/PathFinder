import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="PathFinder Job Market",
    page_icon="💼",
    layout="wide"
)

# --- CHARGEMENT DES DONNÉES ---
@st.cache_data
def load_data():
    # Construction du chemin relatif
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    file_path = os.path.join(project_root, "data", "clean", "global_job_market.csv")
    
    if not os.path.exists(file_path):
        st.error(f"❌ Fichier introuvable : {file_path}")
        return None
    
    df = pd.read_csv(file_path)
    return df

df = load_data()

if df is None:
    st.stop()

# --- TITRE ---
st.title("🔎 PathFinder : Analyse du Marché Data")
st.markdown(f"**{len(df)}** offres analysées provenant de **France Travail, APEC et Welcome to the Jungle**.")

# --- SIDEBAR (FILTRES) ---
st.sidebar.header("Filtres")

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

choix_villes = st.sidebar.multiselect(
    "Filtrer par Ville", 
    top_villes, 
    default=[], # On laisse vide au départ pour ne pas surcharger
    placeholder="Toutes les villes (cliquez pour filtrer)"
)

# LOGIQUE INTELLIGENTE :
# Si la liste est vide, on prend TOUT. Sinon, on prend la sélection.
if not choix_villes:
    selected_ville = top_villes # On garde tout le monde
    st.sidebar.caption("🌍 *Toutes les villes affichées*")
else:
    selected_ville = choix_villes
    st.sidebar.caption(f"📍 *{len(choix_villes)} ville(s) filtrée(s)*")


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
st.sidebar.metric(label="Offres filtrées", value=len(df_filtered))

if df_filtered.empty:
    st.warning("Aucune offre ne correspond à ces critères.")
    st.stop()

# --- KPI ---
st.markdown("---")
col1, col2, col3 = st.columns(3)

nb_offres = len(df_filtered)
df_salaires = df_filtered[df_filtered['Salaire_Annuel'].notna()]
salaire_moyen = df_salaires['Salaire_Annuel'].mean()

col1.metric("Offres affichées", nb_offres)
col2.metric("Salaire Moyen Estimé", f"{salaire_moyen:,.0f} €" if nb_offres > 0 and not pd.isna(salaire_moyen) else "N/A")
col3.metric("Offres avec salaire affiché", f"{len(df_salaires)}")

# --- GRAPHE REPARTITION PAR VILLE ---
st.markdown("---")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("📍 Répartition par Ville")
    ville_counts = df_filtered['Ville'].value_counts().head(10).reset_index()
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

# 1. DÉFINITION DES MOTS-CLÉS (Dictionnaire : Nom Aiché -> Regex)
# On utilise des Regex (\b = frontière de mot) pour éviter les faux positifs (ex: "java" dans "javascript")
keywords = {
    "Python": r"\bpython\b",
    "SQL": r"\bsql\b",
    "Excel": r"\bexcel\b",
    "Power BI": r"power\s?bi", # Accepte "PowerBI" ou "Power BI"
    "Tableau": r"\btableau\b",
    "R": r"\bR\b",             # Attention, peut capter "R&D", mais souvent OK
    "SAS": r"\bsas\b",
    "VBA": r"\bvba\b",
    "AWS": r"\baws\b",
    "Azure": r"\bazure\b",
    "GCP": r"\bgcp\b|google\scloud",
    "Spark": r"\bspark\b",
    "Hadoop": r"\bhadoop\b",
    "Kafka": r"\bkafka\b",
    "Airflow": r"\bairflow\b",
    "Snowflake": r"\bsnowflake\b",
    "Databricks": r"\bdatabricks\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bkubernetes\b|k8s",
    "Git": r"\bgit\b",
    "Linux": r"\blinux\b",
    "Pandas": r"\bpandas\b",
    "TensorFlow": r"\btensorflow\b",
    "PyTorch": r"\bpytorch\b",
    "Scikit-learn": r"scikit[\s\-]learn|sklearn",
    "Java": r"\bjava\b",       # Exclut Javascript grâce aux \b
    "Scala": r"\bscala\b",
    "C++": r"\bc\+\+",
    "NoSQL": r"no\s?sql|mongo|cassandra",
    "Dbt": r"\bdbt\b"
}

# 2. CONCATÉNATION DU TEXTE (Titre + Description) pour la recherche
# On met tout en minuscules pour ne pas rater "Python" vs "python"
text_corpus = (df_filtered['Titre'].fillna('') + " " + df_filtered['Description'].fillna('')).str.lower()

# 3. COMPTAGE (Boucle sur les mots-clés)
stack_counts = {}
for tech, pattern in keywords.items():
    # On compte le nombre de lignes qui contiennent le pattern
    count = text_corpus.str.contains(pattern, regex=True).sum()
    if count > 0:
        stack_counts[tech] = count

# 4. CRÉATION DU DATAFRAME ET TRI
df_stack = pd.DataFrame(list(stack_counts.items()), columns=['Tech', 'Mentions'])
df_stack = df_stack.sort_values(by='Mentions', ascending=True) # Croissant pour le bar chart horizontal

# 5. AFFICHAGE DU GRAPHIQUE
if not df_stack.empty:
    fig_stack = px.bar(
        df_stack.tail(10), # .head()
        x='Mentions',
        y='Tech',
        orientation='h',
        text='Mentions',
        title="Top 10 des Compétences techniques",
        color='Mentions',
        color_continuous_scale='blugrn' # Une couleur différente (Rouge/Orange)
    )

    fig_stack.update_layout(
        font=dict(size=taille_police),
        title=dict(font=dict(size=taille_police + 2), x=0.5),
        coloraxis_showscale=False,
        xaxis=dict(
            title_font=dict(size=taille_police),
            tickfont=dict(size=taille_police)
        ),
        yaxis=dict(
            title_font=dict(size=taille_police),
            tickfont=dict(size=taille_police)
        )
    )
    fig_stack.update_traces(textfont_size=taille_police)

    st.plotly_chart(fig_stack, width="stretch", height=600)
else:
    st.info("Aucune compétence technique détectée dans les offres sélectionnées.")

# --- POSITION DES DONUTS ---

st.markdown("---")
col1, col2 = st.columns(2)

# --- GRAPHIQUE CONTRAT ---
with col1:
    st.subheader("📄 Répartition des Contrats")

    fig_contrat = px.pie(
        df_filtered, 
        names='Type_Contrat', 
        title='Répartition par Type de Contrat',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
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
        color_discrete_sequence=px.colors.qualitative.Set3
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
            font=dict(size=taille_police + 2),
            x=0.5
        )
    )

    fig_niveau.update_traces(
        textfont_size=taille_police
    )

    st.plotly_chart(fig_niveau, width="stretch", height=500)

# --- TABLEAU DE DONNÉES ---
st.markdown("---")
st.subheader("📋 Explorateur d'Offres")
# CORRECTION ICI
st.dataframe(df_filtered[['Titre', 'Entreprise', 'Ville', 'Salaire_Annuel', 'Type_Contrat', 'Source', 'URL']], width="stretch")