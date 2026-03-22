import pandas as pd
import numpy as np
import json
import os

# --- CONFIGURATION ---
TOURNAMENT_ID = 22  # ID de la Saison LH01
CORRECTIONS_PATH = "Root_Elo_LH01_Corrected_Dates.xlsx"
OUTPUT_RATINGS = "data/lh01_final_ratings.csv"
OUTPUT_HISTORY = "data/lh01_history_full.json"
OUTPUT_MATCHES = "data/lh01_matches_fixed.csv"

def fetch_lh01_data(tournament_id):
    """Récupère les données brutes de l'API (simulé ici)."""
    print(f"🌐 Récupération des données du tournoi {tournament_id}...")
    # Ici, insérez votre logique de fetch (requests.get...)
    # On suppose que cela retourne un DataFrame 'df_raw'
    return df_raw 

def apply_corrections(df, excel_path):
    """Applique les dates corrigées depuis le fichier Excel."""
    if os.path.exists(excel_path):
        print(f"🔍 Application des corrections depuis {excel_path}...")
        df_corr = pd.read_excel(excel_path)
        
        # On crée un dictionnaire {ID_Match: Nouvelle_Date}
        # Assurez-vous que les colonnes dans l'Excel s'appellent 'ID' et 'Corrected_Date'
        date_map = dict(zip(df_corr['ID'], df_corr['Corrected_Date']))
        
        def update_date(row):
            return date_map.get(row['ID'], row['Date'])
        
        df['Date'] = df.apply(update_date, axis=1)
        df['Date'] = pd.to_datetime(df['Date'])
        return df.sort_values('Date')
    else:
        print("⚠️ Fichier de corrections introuvable. Calcul avec dates d'origine.")
        return df

def calculate_elo_and_history(df):
    """Calcule l'ELO final ET l'historique complet pour chaque joueur."""
    elo_ratings = {}      # {Nom: ELO_Actuel}
    player_history = {}   # {Nom: [[Date, ELO], [Date, ELO]]}

    print("🧮 Calcul des trajectoires ELO...")

    for _, match in df.iterrows():
        # 1. Identifier les joueurs du match
        # (Adaptez selon la structure de votre DF : gagnants vs perdants)
        players_in_match = match['Players'] 
        date_str = match['Date'].strftime('%Y-%m-%d %H:%M')

        for p in players_in_match:
            # Initialisation nouveau joueur
            if p not in elo_ratings:
                elo_ratings[p] = 1200
                player_history[p] = [[date_str, 1200]]

        # 2. Logique de calcul ELO (votre formule actuelle)
        # new_elos = calcule_formule_root(match, elo_ratings)
        
        # 3. Mise à jour des dictionnaires
        for p in players_in_match:
            elo_ratings[p] = new_elos[p]
            player_history[p].append([date_str, new_elos[p]])

    return elo_ratings, player_history

def main():
    # 1. Extraction
    df_raw = fetch_lh01_data(TOURNAMENT_ID)

    # 2. Nettoyage et Corrections de dates
    df_fixed = apply_corrections(df_raw, CORRECTIONS_PATH)

    # 3. Traitement ELO
    final_ratings, full_history = calculate_elo_and_history(df_fixed)

    # --- EXPORTS ---

    # A. Pour l'initialisation de LH02 (ELO de départ)
    df_final = pd.DataFrame(list(final_ratings.items()), columns=['Player', 'ELO'])
    df_final.to_csv(OUTPUT_RATINGS, index=False)

    # B. Pour le Player Journey (Graphiques multi-saisons)
    with open(OUTPUT_HISTORY, 'w', encoding='utf-8') as f:
        json.dump(full_history, f, indent=4)

    # C. Pour la liste des matchs (Tableau Archive LH01)
    df_fixed.to_csv(OUTPUT_MATCHES, index=False)

    print(f"\n✅ Migration LH01 terminée !")
    print(f"-> {OUTPUT_RATINGS} (Scores de départ)")
    print(f"-> {OUTPUT_HISTORY} (Historique des courbes)")
    print(f"-> {OUTPUT_MATCHES} (Liste des matchs corrigée)")

if __name__ == "__main__":
    main()
