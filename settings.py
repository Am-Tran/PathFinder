import streamlit as st

# Palette 1 : "Corporate" (Sérieux, tons bleus/gris/froids)
PALETTE_CORPORATE = [
    "#2c3e50", # Bleu nuit
    "#3498db", # Bleu clair
    "#95a5a6", # Gris
    "#e74c3c", # Rouge (pour le contraste)
    "#34495e", # Ardoise
    "#1abc9c", # Turquoise
    "#ecf0f1", # Blanc cassé
    "#bdc3c7"  # Argent
]

# Palette 2 : "Vibrant" (Pop, moderne, très contrasté)
PALETTE_VIBRANT = [
    "#6c5ce7", # Violet
    "#00b894", # Vert menthe
    "#fdcb6e", # Moutarde
    "#e17055", # Corail
    "#d63031", # Rouge vif
    "#0984e3", # Bleu électrique
    "#e84393", # Rose
    "#2d3436"  # Anthracite
]

# Palette 3 : "Pastel" (Doux, lisible, apaisant)
PALETTE_PASTEL = [
    "#81ecec", # Cyan pâle
    "#a29bfe", # Lavande
    "#ffeaa7", # Crème
    "#fab1a0", # Pêche
    "#ff7675", # Saumon
    "#dfe6e9", # Gris perle
    "#74b9ff", # Bleu ciel
    "#55efc4"  # Menthe pâle
]

# Palette 3 : "Pastel" (Doux, lisible, apaisant)
PALETTE_PASTEL = [
    "#2980b9", # Bleu Pro
    "#00b894", # Vert Menthe
    "#ff7675", # Rouge Doux
    "#2d3436", # Gris Sombre
    "#e17055", # Orange Vif
    "#f1c40f", # Jaune
    "#2ecc71", # Vert
    "#9b59b6"  # Violet
    "#3498db", # Bleu
    "#1abc9c", # Turquoise
    "#e74c3c"  # Rouge
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