import os
import requests
import pandas as pd
import json
from datetime import datetime, date

# =========================================================================
# --- 1. CONFIGURATION ---
# =========================================================================
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24  # Season LH01 Tournament ID

# Set cutoff for archive season
CUTOFF_DATE = datetime.strptime("2026-04-01", "%Y-%m-%d").date()

# Define paths matching main.py structure
DATA_DIR = "data"
CORRECTIONS_PATH = os.path.join(DATA_DIR, "lh01_corrections.csv")
OUTPUT_RATINGS   = os.path.join(DATA_DIR, "lh01_final_ratings.csv")
OUTPUT_HISTORY   = os.path.join(DATA_DIR, "lh01_history_full.json")
OUTPUT_MATCHES   = os.path.join(DATA_DIR, "lh01_matches_fixed.csv")

# =========================================================================
# --- 2. LOAD CORRECTIONS ---
# =========================================================================
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(CORRECTIONS_PATH):
        # Aligned to use CSV like main.py
        df_updates = pd.read_csv(CORRECTIONS_PATH, parse_dates=['New_Date'])
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            game_id_mapping.index = game_id_mapping.index.astype(int) # Safecasting for mask
            print(f"✅ Loaded {len(game_id_mapping)} corrections.")
except Exception as e:
    print(f"⚠️ Note: Corrections skipped: {e}")

# =========================================================================
# --- 3. FETCH MATCH DATA ---
# =========================================================================
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
if not df.empty:
    df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

    # Apply date corrections securely
    if not game_id_mapping.empty:
        mask = df['GameID'].isin(game_id_mapping.index)
        if mask.any():
            original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
            new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
            df.loc[mask, 'Date_Closed'] = pd.to_datetime(new_dates + ' ' + original_times, utc=True)

    df = df[df['Date_Closed'].dt.date <= CUTOFF_DATE].copy()
    df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# =========================================================================
# --- 4. ELO CALCULATION & STATS ---
# =========================================================================
elo_ratings = {p: 1200.0 for p in df['Player'].unique()}
peak_elo = {p: 1200.0 for p in df['Player'].unique()}
player_stats = {p: {'games': 0, 'wins': 0.0} for p in df['Player'].unique()}
player_history = {p: [["Start", 1200]] for p in df['Player'].unique()}
last_diff = {p: 0 for p in df['Player'].unique()}
archive_matches_list = []

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    current_match_sum = sum([elo_ratings[p['Player']] for p in match_participants])
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
    
    # For Matches file (Lineup), logic unified with main.py
    winners = [p['Player'] for p in match_participants if p['Score'] >= 0.5]
    others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
    
    archive_matches_list.append({
        'MatchID': game_id,
        'Date': current_date,
        'Winner': ", ".join(winners),
        'Other Players': ", ".join(others),
        'ELO_Sum': round(current_match_sum)
    })

    # Calculate ELO
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

# =========================================================================
# --- 5. EXPORT FINAL RATINGS (LEADERBOARD) ---
# =========================================================================
results = []
for p, rating in elo_ratings.items():
    g = player_stats[p]['games']
    w = player_stats[p]['wins']
    diff = round(last_diff[p])
    results.append({
        'Rank': 0, 'Player': p, 'ELO': round(rating), 'Games': g,
        'Wins': w,
        'Win Rate': f"{(w/g):.1%}" if g > 0 else "0.0%", 'Peak': round(peak_elo[p]),
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': (g >= 10 and rating >= 1200)
    })

# Create final standings
final_df = pd.DataFrame(results).sort_values(by='ELO', ascending=False)
rank = 1
ranks = []
for _, row in final_df.iterrows():
    if row['Qualified']: 
        ranks.append(rank)
        rank += 1
    else: 
        ranks.append("-")
final_df['Rank'] = ranks

# =========================================================================
# --- 6. FINAL EXPORTS ---
# =========================================================================

# Ensure directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# A. Save Leaderboard
final_df.to_csv(OUTPUT_RATINGS, index=False)

# B. Save Matches 
df_archive_matches = pd.DataFrame(archive_matches_list)

# Sort by descending ELO_Sum and insert Rank column
if not df_archive_matches.empty:
    df_archive_matches = df_archive_matches.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
    df_archive_matches.insert(0, 'Rank', range(1, len(df_archive_matches) + 1))
    
df_archive_matches.to_csv(OUTPUT_MATCHES, index=False)

# C. Save History Graph
with open(OUTPUT_HISTORY, 'w', encoding='utf-8') as f:
    json.dump(player_history, f)

print(f"✨ ARCHIVES LH01 SUCCESSFULLY GENERATED.")
