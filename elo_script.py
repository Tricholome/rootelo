import requests
import pandas as pd
import math
import os

# --- Configuration (Récupération du Token API caché dans GitHub Secrets) ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}

CUTOFF_DATE = '2026-03-20'
TOURNAMENT_ID = 24

# --- 1. Lecture du fichier de corrections (Directement dans le dépôt GitHub) ---
excel_file_path = 'Root_Elo_LH01_Corrected_Dates.xlsx'
df_updates = pd.read_excel(excel_file_path)
df_updates['New_Date'] = pd.to_datetime(df_updates['New_Date'])

# --- 2. Fetch Data depuis l'API ---
all_data = []
next_page_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

while next_page_url:
    try:
        response = requests.get(next_page_url, headers=HEADERS)
        response.raise_for_status()
        page_data = response.json()
        all_data.extend(page_data.get('results', []))
        next_page_url = page_data.get('next')
    except Exception as e:
        print(f"Erreur API: {e}")
        break

# --- 3. Traitement des données & Calcul ELO ---
elo_data = []
for match in all_data:
    participants = match['participants']
    if len(participants) == 4:
        for p in participants:
            elo_data.append({
                'GameID': match['id'],
                'Player': p.get('player'),
                'Tournament Score': float(p.get('tournament_score', 0.0)),
                'Date_Closed': match.get('date_closed')
            })

df = pd.DataFrame(elo_data)
df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

# Application des corrections de dates
game_id_to_new_date = df_updates.set_index('GameID')['New_Date']
mask = df['GameID'].isin(game_id_to_new_date.index)
if mask.any():
    df.loc[mask, 'Date_Closed'] = pd.to_datetime(df.loc[mask, 'GameID'].map(game_id_to_new_date), utc=True)

df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# --- 4. Logique ELO (Simplifiée pour l'exemple, identique à la tienne) ---
elo_ratings = {p: 1200 for p in df['Player'].unique()}
stats = {p: {'games': 0, 'wins': 0.0} for p in df['Player'].unique()}

for game_id, group in df.groupby('GameID', sort=False):
    players = group.to_dict('records')
    if len(players) != 4: continue
    
    total_q = sum([10**(elo_ratings[p['Player']]/400) for p in players])
    updates = {}
    for p in players:
        name = p['Player']
        actual = p['Tournament Score']
        expected = (10**(elo_ratings[name]/400)) / total_q
        
        stats[name]['games'] += 1
        stats[name]['wins'] += actual
        
        # K-Factor
        k = 80 if stats[name]['games'] <= 10 else (40 if stats[name]['games'] <= 50 else 20)
        updates[name] = elo_ratings[name] + k * (actual - expected)
    
    for name, val in updates.items():
        elo_ratings[name] = val

# --- 5. Préparation du classement final ---
res = []
for p, score in elo_ratings.items():
    if stats[p]['wins'] > 0:
        res.append({
            'Player': p,
            'ELO': round(score),
            'Games': stats[p]['games'],
            'Wins': round(stats[p]['wins'], 1),
            'WinRate': f"{(stats[p]['wins']/stats[p]['games']):.1%}"
        })

final_df = pd.DataFrame(res).sort_values(by='ELO', ascending=False)

# --- 6. Génération de la page HTML ---
html_table = final_df.to_html(index=False, classes='leaderboard')
html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Root League Leaderboard</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #121212; color: #eee; text-align: center; padding: 50px; }}
        table {{ margin: 20px auto; border-collapse: collapse; background: #1e1e1e; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 15px 25px; border-bottom: 1px solid #333; }}
        th {{ background: #333; color: #4a90e2; text-transform: uppercase; }}
        tr:hover {{ background: #252525; }}
    </style>
</head>
<body>
    <h1>Root Digital League - Classement ELO</h1>
    {html_table}
    <p style="margin-top: 20px; color: #666;">Dernière mise à jour automatique : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
