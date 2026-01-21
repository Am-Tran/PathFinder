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
selected_source = st.sidebar.multiselect("Source", source_list, default=source_list)

# 2. Filtre Contrat
contrat_list = df['Type_Contrat'].dropna().unique().tolist()
selected_contrat = st.sidebar.multiselect("Type de Contrat", contrat_list, default=contrat_list)

# 3. Filtre Ville (Top 20)
top_villes = df['Ville'].value_counts().head(20).index.tolist()
selected_ville = st.sidebar.multiselect("Ville (Top 20)", top_villes, default=top_villes)

# --- APPLICATION DES FILTRES ---
df_filtered = df[
    (df['Source'].isin(selected_source)) &
    (df['Type_Contrat'].isin(selected_contrat)) &
    (df['Ville'].isin(selected_ville))
]

# --- KPI ---
st.markdown("---")
col1, col2, col3 = st.columns(3)

nb_offres = len(df_filtered)
df_salaires = df_filtered[df_filtered['Salaire_Annuel'].notna()]
salaire_moyen = df_salaires['Salaire_Annuel'].mean()

col1.metric("Offres affichées", nb_offres)
col2.metric("Salaire Moyen Estimé", f"{salaire_moyen:,.0f} €" if nb_offres > 0 and not pd.isna(salaire_moyen) else "N/A")
col3.metric("Offres avec salaire affiché", f"{len(df_salaires)}")

# --- GRAPHIQUES ---
st.markdown("---")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("📍 Répartition par Ville")
    ville_counts = df_filtered['Ville'].value_counts().head(10).reset_index()
    ville_counts.columns = ['Ville', 'Nombre']
    fig_ville = px.bar(ville_counts, x='Nombre', y='Ville', orientation='h', color='Nombre', title="Top 10 Villes")
    fig_ville.update_layout(yaxis={'categoryorder':'total ascending'})
    # CORRECTION ICI : width="stretch" au lieu de use_container_width
    st.plotly_chart(fig_ville, width="stretch")

with col_g2:
    st.subheader("💰 Distribution des Salaires")
    if not df_salaires.empty:
        fig_salaire = px.box(df_salaires, x='Source', y='Salaire_Annuel', color='Source', title="Salaires par Source")
        # CORRECTION ICI
        st.plotly_chart(fig_salaire, width="stretch")
    else:
        st.info("Pas assez de données de salaire pour afficher le graphique.")

# --- GRAPHIQUE CONTRAT ---
st.subheader("📜 Types de Contrats")
contrat_counts = df_filtered['Type_Contrat'].value_counts().reset_index()
contrat_counts.columns = ['Type', 'Nombre']
fig_contrat = px.pie(contrat_counts, values='Nombre', names='Type', title="Répartition des Contrats", hole=0.4)
# CORRECTION ICI
st.plotly_chart(fig_contrat, width="stretch")

# --- TABLEAU DE DONNÉES ---
st.markdown("---")
st.subheader("📋 Explorateur d'Offres")
# CORRECTION ICI
st.dataframe(df_filtered[['Titre', 'Entreprise', 'Ville', 'Salaire_Annuel', 'Type_Contrat', 'Source', 'URL']], width="stretch")