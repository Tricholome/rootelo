import os
import json
import pandas as pd

DATA_DIR = "data"
SEASONS = ["lh01", "lh02"]
OUTPUT_CSV = os.path.join(DATA_DIR, "all_seasons_players_deltas.csv")

all_records = []

for season in SEASONS:
    file_path = os.path.join(DATA_DIR, f"{season}_history_full.json")
    
    if not os.path.exists(file_path):
        print(f"⚠️ Fichier introuvable pour {season.upper()} : {file_path}")
        continue
        
    print(f"📊 Traignement de la saison {season.upper()}...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        player_history = json.load(f)
        
    for player, history in player_history.items():
        for i in range(1, len(history)):
            prev_entry = history[i - 1]
            current_entry = history[i]
            
            label = current_entry[0]
            current_elo = current_entry[1]
            prev_elo = prev_entry[1]
            
            # Calcul du gain ou de la perte nette
            delta = current_elo - prev_elo
            
            # Extraction sécurisée de l'ID du match (si présent dans la structure)
            match_id = current_entry[2] if len(current_entry) > 2 else None
            
            # On ignore les lignes de configuration ("Start", "Final" ou ajustements sans match)
            if label in ["Start", "Final"] or match_id is None:
                continue
                
            all_records.append({
                "Season": season.upper(),
                "MatchID": match_id,
                "Player": player,
                "Delta": round(delta, 2)
            })

if all_records:
    df_analysis = pd.DataFrame(all_records)
    
    # Tri par saison puis par ID de match pour avoir un historique propre
    df_analysis = df_analysis.sort_values(by=["Season", "MatchID"]).reset_index(drop=True)
    
    # Export final en CSV
    df_analysis.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"✅ Extraction terminée ! {len(df_analysis)} lignes exportées dans : {OUTPUT_CSV}")
else:
    print("❌ Aucun match valide n'a pu être extrait. Vérifie le format de tes fichiers JSON.")
