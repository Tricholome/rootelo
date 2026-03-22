import os
import requests
import pandas as pd
import json
from datetime import datetime, date

# --- 1. Configuration ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24  # Season LH01 Tournament ID

CUTOFF_DATE = datetime.strptime("2026-03-31", "%Y-%m-%d").date()

OUTPUT_RATINGS = "data/lh01_final_ratings.csv"
OUTPUT_HISTORY = "data/lh01_history_full.json"
OUTPUT_MATCHES = "data/lh01_matches_fixed.csv"

# --- 2. Load Correction File ---
CORRECTIONS_PATH = 'Root_Elo_LH01_Corrected_Dates.xlsx'
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(CORRECTIONS_PATH):
        df_updates = pd.read_excel(CORRECTIONS_PATH, engine='openpyxl')
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"✅ Loaded {len(game_id_mapping)} corrections.")
except Exception as e:
    print(f"⚠️ Note: Excel skipped: {e}")

# --- 3. Fetch Match Data ---
all_matches = []
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

print(f"🌐 Fetching LH01 data...")
while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except: break

raw_data = [] 
for m in all_matches:
    participants = m.get('participants', [])
    if len(participants) == 4:
        for p in participants:
            raw_data.append({
                'GameID': m['id'],
                'Player': p.get('player'),
                'Score': float(p.get('tournament_score', 0.0)), 
                'Date_Closed': m.get('date_closed')
            })

df = pd.DataFrame(raw_data)
df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

# Corrections de dates
if not game_id_mapping.empty:
    mask = df['GameID'].isin(game_id_mapping.index)
    if mask.any():
        original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
        new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
        df.loc[mask, 'Date_Closed'] = pd.to_datetime(new_dates + ' ' + original_times, utc=True)

df = df[df['Date_Closed'].dt.date <= CUTOFF_DATE].copy()
df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# --- 4. ELO Calculation & Stats ---
elo_ratings = {p: 1200 for p in df['Player'].unique()}
peak_elo = {p: 1200 for p in df['Player'].unique()}
player_stats = {p: {'games': 0, 'wins': 0.0} for p in df['Player'].unique()}
player_history = {p: [["Start", 1200]] for p in df['Player'].unique()}
last_diff = {p: 0 for p in df['Player'].unique()}
archive_matches_list = []

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    current_match_sum = sum([elo_ratings[p['Player']] for p in match_participants])
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
    
    # Pour le fichier Matches (Lineup)
    solo_winners = [p['Player'] for p in match_participants if p['Score'] == 1.0]
    co_winners = [p['Player'] for p in match_participants if p['Score'] == 0.5]
    others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
    
    archive_matches_list.append({
        'MatchID': game_id,
        'Date': current_date,
        'Winner': ", ".join(solo_winners + co_winners),
        'Other Players': ", ".join(others),
        'ELO_Sum': round(current_match_sum)
    })

    # Calcul ELO
    total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
    for p in match_participants:
        name = p['Player']
        actual = p['Score']
        expected = (10**(elo_ratings[name]/400)) / total_q
        
        player_stats[name]['games'] += 1
        player_stats[name]['wins'] += actual
        g = player_stats[name]['games']
        k = 80 if g <= 10 else (40 if g <= 50 else 20)
            
        change = k * (actual - expected)
        elo_ratings[name] += change
        last_diff[name] = change
        if elo_ratings[name] > peak_elo[name]: peak_elo[name] = elo_ratings[name]
        player_history[name].append([current_date, round(elo_ratings[name])])

# --- 5. Export Final Ratings (Leaderboard compatible) ---
results = []
for p, rating in elo_ratings.items():
    g = player_stats[p]['games']
    w = player_stats[p]['wins']
    diff = round(last_diff[p])
    results.append({
        'Rank': 0, 'Player': p, 'ELO': round(rating), 'Games': g,
        'Wins': int(w) if w % 1 == 0 else round(w, 1),
        'Win Rate': f"{(w/g):.1%}", 'Peak': round(peak_elo[p]),
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': (g >= 10 and rating >= 1200)
    })

# Création du classement par Rank
final_df = pd.DataFrame(results).sort_values(by='ELO', ascending=False)
rank = 1
ranks = []
for _, row in final_df.iterrows():
    if row['Qualified']: ranks.append(rank); rank += 1
    else: ranks.append("-")
final_df['Rank'] = ranks

# --- 6. Final Exports ---
final_df.to_csv(OUTPUT_RATINGS, index=False)
pd.DataFrame(archive_matches_list).to_csv(OUTPUT_MATCHES, index=False)
with open(OUTPUT_HISTORY, 'w', encoding='utf-8') as f:
    json.dump(player_history, f)

print(f"✨ ARCHIVES LH01 GÉNÉRÉES AVEC SUCCÈS.")
