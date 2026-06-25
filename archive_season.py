import os
import requests
import pandas as pd
import json
from datetime import datetime, date

# =========================================================================
# --- 0. SETTINGS & AUTHENTICATION ---
# =========================================================================
# --- DYNAMIC CONFIGURATION VIA ENVIRONMENT VARIABLES ---
SEASON_TAG = os.getenv('SEASON_TAG', 'lh01').strip().lower()
PREVIOUS_SEASON_TAG = os.getenv('PREVIOUS_SEASON_TAG', '').strip().lower()
if not PREVIOUS_SEASON_TAG:
    PREVIOUS_SEASON_TAG = None

TOURNAMENT_ID = int(os.getenv('TOURNAMENT_ID', 24))
CUTOFF_DATE_STR = os.getenv('CUTOFF_DATE_STR', '2026-03-31').strip()

# --- API TOKEN RECOVERY ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}

# =========================================================================
# --- 1. DYNAMIC PATH CONFIGURATION ---
# =========================================================================
DATA_DIR = "data"
CUTOFF_DATE = datetime.strptime(CUTOFF_DATE_STR, "%Y-%m-%d").date()

# Dynamic paths based on the SEASON_TAG
CORRECTIONS_PATH = os.path.join(DATA_DIR, f"{SEASON_TAG}_corrections.csv")
OUTPUT_RATINGS   = os.path.join(DATA_DIR, f"{SEASON_TAG}_final_ratings.csv")
OUTPUT_HISTORY   = os.path.join(DATA_DIR, f"{SEASON_TAG}_history_full.json")
OUTPUT_MATCHES   = os.path.join(DATA_DIR, f"{SEASON_TAG}_matches_fixed.json")
OUTPUT_METADATA  = os.path.join(DATA_DIR, f"{SEASON_TAG}_metadata.json")

# =========================================================================
# --- 2. LOAD PREVIOUS SEASON BASELINE ---
# =========================================================================
inherited_elo = {}
if PREVIOUS_SEASON_TAG:
    prev_path = os.path.join(DATA_DIR, f"{PREVIOUS_SEASON_TAG}_final_ratings.csv")
    if os.path.exists(prev_path):
        print(f"📜 Loading baseline from {PREVIOUS_SEASON_TAG}...")
        df_prev = pd.read_csv(prev_path)
        inherited_elo = {str(row['Player']): float(row.get('ELO', 1200.0)) for _, row in df_prev.iterrows()}
        print(f"   -> {len(inherited_elo)} players inherited.")
    else:
        print(f"⚠️ Warning: Previous ratings file not found at {prev_path}")
else:
    print("🆕 No previous season defined. Starting fresh (1200.0).")

# =========================================================================
# --- 3. LOAD CORRECTIONS ---
# =========================================================================
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(CORRECTIONS_PATH):
        df_updates = pd.read_csv(CORRECTIONS_PATH, parse_dates=['New_Date'])
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            game_id_mapping.index = game_id_mapping.index.astype(int)
            print(f"✅ Loaded {len(game_id_mapping)} corrections.")
except Exception as e:
    print(f"⚠️ Note: Corrections skipped: {e}")

# =========================================================================
# --- 4. FETCH MATCH DATA ---
# =========================================================================
all_matches = []
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

print(f"🌐 Fetching {SEASON_TAG.upper()} data...")
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

    if not game_id_mapping.empty:
        mask = df['GameID'].isin(game_id_mapping.index)
        if mask.any():
            original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
            new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
            df.loc[mask, 'Date_Closed'] = pd.to_datetime(new_dates + ' ' + original_times, utc=True)

    df = df[df['Date_Closed'].dt.date <= CUTOFF_DATE].copy()
    df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# =========================================================================
# --- 5. ELO CALCULATION & STATS ---
# =========================================================================
elo_ratings = {p: inherited_elo.get(p, 1200.0) for p in df['Player'].unique()}

for p, rating in inherited_elo.items():
    if p not in elo_ratings:
        elo_ratings[p] = rating

peak_elo = {p: r for p, r in elo_ratings.items()}
player_stats = {p: {'games': 0, 'wins': 0.0} for p in elo_ratings}
last_diff = {p: 0.0 for p in elo_ratings}
archive_matches_list = []
player_history = {}

for p, r in elo_ratings.items():
    start_label = f"{PREVIOUS_SEASON_TAG.upper()} Final" if PREVIOUS_SEASON_TAG and p in inherited_elo else "Start"
    player_history[p] = [[start_label, round(r), None, None]]

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    current_match_sum = round(sum([elo_ratings[p['Player']] for p in match_participants]))
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
    
    deltas_this_match = {}
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
        deltas_this_match[name] = round(change)
        
        if elo_ratings[name] > peak_elo[name]: peak_elo[name] = elo_ratings[name]
        
        match_url = f"https://rootleague.pliskin.dev/match/{game_id}"
        player_history[name].append([current_date, round(elo_ratings[name]), game_id, match_url])

    players_list = []
    for p in match_participants:
        clean_name = p['Player'].split('+')[0].split('#')[0].strip()
        players_list.append({
            'name': clean_name,
            'delta': int(deltas_this_match[p['Player']]),
            'is_winner': bool(p['Score'] >= 0.5)
        })
    
    archive_matches_list.append({
        'MatchID': int(game_id),
        'Date': current_date,
        'players': players_list,
        'ELO_Sum': int(current_match_sum)
    })

# =========================================================================
# --- 6. SEASON END REBALANCING ---
# =========================================================================
active_players = [p for p in elo_ratings if player_stats[p]['games'] >= 1]
inactive_players = [p for p in elo_ratings if player_stats[p]['games'] == 0]

num_players = len(elo_ratings)
num_active = len(active_players)

if num_active > 0 and num_players > 0:
    actual_sum = sum(elo_ratings.values())
    theoretical_sum = num_players * 1200.0
    total_deficit = theoretical_sum - actual_sum
    
    bonus_per_player = total_deficit / num_active
    
    print(f"📊 Rebalancing Season {SEASON_TAG.upper()}:")
    print(f"   - Total database players: {num_players}")
    print(f"   - Active Players (Tier unlocked, >= 10 games): {num_active}")
    print(f"   - Inactive/Unqualified Players (< 10 games): {len(inactive_players)}")
    print(f"   - Actual Total Elo: {actual_sum:.2f}")
    print(f"   - Theoretical Total: {theoretical_sum:.2f}")
    print(f"   - Global Deficit to inject: {total_deficit:.2f} points")
    print(f"   - Individual Loyalty Bonus: +{bonus_per_player:.4f} Elo per qualified player")
    
    for p in active_players:
        elo_ratings[p] += bonus_per_player
        if elo_ratings[p] > peak_elo[p]:
            peak_elo[p] = elo_ratings[p]
        player_history[p].append(["Final", round(elo_ratings[p]), None, None])           

for p in inactive_players:
    player_history[p].append(["Final", round(elo_ratings[p]), None, None])        

# =========================================================================
# --- 7. EXPORT FINAL RATINGS (LEADERBOARD) ---
# =========================================================================
results = []
for p, rating in elo_ratings.items():
    g = player_stats[p]['games']
    w = player_stats[p]['wins']
    display_elo = round(rating)
    diff = round(last_diff[p])
    
    results.append({
        'Player': p, 
        'ELO': rating, # Float preserved for LH02 logic
        'Display_ELO': display_elo, # Temporary column for qualification check
        'Games': g,
        'Wins': w,
        'Win Rate': f"{(w/g):.1%}" if g > 0 else "0.0%", 
        'Peak': round(peak_elo[p]),
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': (g >= 10 and display_elo >= 1200) # Qualified based on VISUAL elo
    })

# Sort by FLOAT (true mathematical ranking)
final_df = pd.DataFrame(results).sort_values(by='ELO', ascending=False)

rank = 1
ranks = []
for _, row in final_df.iterrows():
    if row['Qualified']: 
        ranks.append(rank)
        rank += 1
    else: 
        ranks.append("-")
        
final_df.insert(0, 'Rank', ranks)
# Drop Display_ELO, we only need true ELO in the CSV
final_df = final_df.drop(columns=['Display_ELO'])

# =========================================================================
# --- 8. FINAL EXPORTS ---
# =========================================================================
os.makedirs(DATA_DIR, exist_ok=True)

def safe_save(path, data, is_json=False):
    if os.path.exists(path):
        os.remove(path)
    
    if is_json:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    else:
        data.to_csv(path, index=False)
    print(f"DEBUG: Successfully overwritten {path}")

# A. Save Leaderboard
safe_save(OUTPUT_RATINGS, final_df)

# B. Save Matches 
if archive_matches_list:
    archive_matches_list = sorted(archive_matches_list, key=lambda x: x['ELO_Sum'], reverse=True)
    for idx, m in enumerate(archive_matches_list, start=1):
        m['Rank'] = idx

safe_save(OUTPUT_MATCHES, archive_matches_list, is_json=True)

# C. Save History Graph
safe_save(OUTPUT_HISTORY, player_history, is_json=True)

# D. Save Metadata
metadata = {
    "season_tag": SEASON_TAG.upper(),
    "cutoff_date": CUTOFF_DATE_STR,
    "match_count": len(archive_matches_list)
}
safe_save(os.path.join(DATA_DIR, f"{SEASON_TAG}_metadata.json"), metadata, is_json=True)

print(f"✨ ARCHIVES FOR {SEASON_TAG.upper()} SUCCESSFULLY GENERATED.")
