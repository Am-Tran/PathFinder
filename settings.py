import streamlit as st

# Palette 1 : "Corporate" (Sérieux, tons bleus/gris/froids)
palette_a = [
    "#2c3e50", # Bleu nuit
    "#3498db", # Bleu clair    
    "#ff7675", # Rouge Doux
    "#00b894", # Vert Menthe
    "#f1c40f", # Jaune
    "#1abc9c", # Turquoise
    "#9864d3", # Blanc cassé
    "#bdc3c7"  # Argent
]

# Palette 2 : "Vibrant" (Pop, moderne, très contrasté)
palette_b = [
    "#DB4B4B", # Rouge Rosé
    "#EFF86E", # Jaune Citron pâle
    "#A7BCFF", # Bleu Pervenche
    "#FFBA74",  # Orange Abricot
    "#75FFFE", # Cyan Électrique
    "#B96229", # Orange Brûlé / Bronze
    "#EF5580", # Rose Framboise    
    "#A0E9FA" # Bleu Ciel Glacé
]

# Palette 3
palette_c = [
    "#4BDBDB", # Cyan
    "#a29bfe", # Lavande
    "#f8dc7f", # Crème
    "#fab1a0", # Pêche
    "#ff7675", # Saumon
    "#2980b9", # Bleu Pro
    "#55efc4",  # Menthe pâle
    "#74b9ff" # Bleu ciel
]


# Fonction utilitaire pour mapper une palette à une liste de catégories
def get_color_map(categories, palette):
    """
    Associe chaque catégorie à une couleur de la palette.
    Ex: categories=['CDI', 'CDD'], palette=PALETTE_VIBRANT
    Retourne {'CDI': '#6c5ce7', 'CDD': '#00b894'}
    """
    # On boucle sur les couleurs (cycle) si on a plus de catégories que de couleurs
    return {cat: palette[i % len(palette)] for i, cat in enumerate(categories)}


def charger_style():
    """
    Injecte le CSS personnalisé pour l'apparence des onglets et espacements.
    """
    st.markdown("""
    <style>
        /* 1. boutons des onglets (tabs) */
        button[data-baseweb="tab"] {
        background-color: #f0000; /* Gris clair par défaut */        
        margin-right: 30px;        /* ⬅️ C'EST ICI : Écart entre les boutons */        
    }
        /* 3. Espace entre les onglets et le contenu */
        div[data-baseweb="tab-panel"] {
        padding-top: 40px; /* Tu peux augmenter à 40px ou 50px si tu veux plus d'air */
    }
</style>
""", unsafe_allow_html=True)