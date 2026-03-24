import pandas as pd
import json
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

# =========================================================================
# --- 1. CONFIGURATION & SETUP ---
# =========================================================================

# Initialisation de Jinja2
env = Environment(loader=FileSystemLoader('templates'))

NAV_ITEMS = [
    {'id': 'index', 'url': 'index.html', 'label': 'Leaderboard'},
    {'id': 'matches', 'url': 'matches.html', 'label': 'Top Tables'},
    {'id': 'trends', 'url': 'trends.html', 'label': "Player's Journey"},
    {'id': 'about', 'url': 'about.html', 'label': 'Codex'}
]

# Couleurs thématiques
COLORS = {
    "bird": "#67c0c7",
    "fox": "#e6372d",
    "rabbit": "#f7eb5b",
    "mouse": "#f29057"
}

# =========================================================================
# --- 2. FONCTIONS DE RENDU (JINJA2) ---
# =========================================================================

def render_page(template_name, output_name, **kwargs):
    """Génère un fichier HTML à partir d'un template Jinja2."""
    template = env.get_template(template_name)
    
    # On ajoute les variables globales communes à toutes les pages
    full_vars = {
        "nav_items": NAV_ITEMS,
        "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
        **kwargs
    }
    
    html_output = template.render(**full_vars)
    with open(output_name, "w", encoding="utf-8") as f:
        f.write(html_output)
    print(f"  > {output_name} généré.")

# =========================================================================
# --- 3. LOGIQUE DE PRÉPARATION DES DONNÉES ---
# =========================================================================

def get_tier_icon(elo, games):
    """Détermine l'icône selon l'ELO (identique à ton ancien script)."""
    if games < 10: return None, "Unranked"
    if elo >= 1500: return "assets/icons/bird.png", "Bird"
    if elo >= 1400: return "assets/icons/fox.png", "Fox"
    if elo >= 1300: return "assets/icons/rabbit_new.webp", "Rabbit"
    if elo >= 1200: return "assets/icons/mouse_new.webp", "Mouse"
    return None, "Unranked"

def prepare_leaderboard_data(df):
    """Transforme le DataFrame en liste de dictionnaires pour le HTML."""
    players_list = []
    if df.empty: return []
    
    for _, row in df.iterrows():
        icon_path, tier_name = get_tier_icon(row['ELO'], row['Games'])
        players_list.append({
            'Rank': row['Rank'],
            'icon_path': icon_path,
            'display_name': str(row['Player']).split('+')[0].split('#')[0],
            'ELO': row['ELO'],
            'Games': row['Games'],
            'Wins': row['Wins'],
            'Win_Rate': row['Win Rate'],
            'Peak': row['Peak'],
            'Last': row['Last']
        })
    return players_list

# =========================================================================
# --- 4. EXÉCUTION (LE CŒUR DU SCRIPT) ---
# =========================================================================

def main():
    # --- ÉTAPE A : TES CALCULS ELO ---
    # Ici, tu gardes TOUTE ta logique de récupération d'API et de calcul.
    # On suppose que tu as à la fin : 
    # current_final_df, current_matches_df, current_history, etc.
    
    # --- ÉTAPE B : FILTRAGE ---
    # Exemple : display_current_df = current_final_df[current_final_df['Wins'] >= 1].copy()
    
    # --- ÉTAPE C : GÉNÉRATION DES PAGES ---
    print("Démarrage de la génération du site...")

    # 1. Leaderboard Current (LH02)
    render_page(
        "leaderboard.html", 
        "index.html",
        title="Leaderboard • Rootelo",
        page_id="index",
        is_archive=False,
        current_page_base="index",
        main_color=COLORS["rabbit"],
        page_heading="Leaderboard",
        subtitle="LH02 • Apr–Jun 2026",
        description="Minimum 1 win required for display.",
        players=prepare_leaderboard_data(display_current_df)
    )

    # 2. Leaderboard Archive (LH01)
    render_page(
        "leaderboard.html", 
        "index_lh01.html",
        title="Leaderboard • Rootelo",
        page_id="index",
        is_archive=True,
        current_page_base="index",
        main_color=COLORS["fox"],
        page_heading="Leaderboard",
        subtitle="LH01 • Jan–Mar 2026",
        description="Archive de la saison passée.",
        players=prepare_leaderboard_data(display_archive_df)
    )

    # 3. Page About (Codex)
    # Note : Tu devras créer templates/about.html
    render_page(
        "about.html",
        "about.html",
        title="Codex • Rootelo",
        page_id="about",
        main_color=COLORS["bird"],
        page_heading="The Woodland Codex"
    )

    print("Site généré avec succès !")

if __name__ == "__main__":
    # Assure-toi que display_current_df et les autres sont bien définis avant
    # Ou déplace tes calculs à l'intérieur de main()
    main()
