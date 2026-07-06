import os
import requests
import pandas as pd
import json
from datetime import datetime

# =========================================================================
# --- 1. SETTINGS & PATH CONFIGURATION ---
# =========================================================================
SEASON_TAG = os.getenv('SEASON_TAG', 'lh01').strip().lower()
PREVIOUS_SEASON_TAG = os.getenv('PREVIOUS_SEASON_TAG', '').strip().lower() or None
TOURNAMENT_ID = int(os.getenv('TOURNAMENT_ID', 24))
CUTOFF_DATE_STR = os.getenv('CUTOFF_DATE_STR', '2026-03-31').strip()
CUTOFF_DATE = datetime.strptime(CUTOFF_DATE_STR, "%Y-%m-%d").date()

API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}

# Centralisation et uniformisation des noms de fichiers
DATA_DIR = "data"
CORRECTIONS_PATH = os.path.join(DATA_DIR, f"{SEASON_TAG}_corrections.csv")
OUTPUT_RATINGS   = os.path.join(DATA_DIR, f"{SEASON_TAG}_ratings.csv")
OUTPUT_HISTORY   = os.path.join(DATA_DIR, f"{SEASON_TAG}_history.json")
OUTPUT_MATCHES   = os.path.join(DATA_DIR, f"{SEASON_TAG}_matches.json")
OUTPUT_METADATA  = os.path.join(DATA_DIR, f"{SEASON_TAG}_metadata.json")
OUTPUT_RELATIONS = os.path.join(DATA_DIR, f"{SEASON_TAG}_relations.json")

# =========================================================================
# --- 2. LOAD PREVIOUS SEASON BASELINE ---
# =========================================================================
print(f"\n=== INITIALIZING {SEASON_TAG.upper()} ===")
inherited_elo = {}

if PREVIOUS_SEASON_TAG:
    # Utilisation du nouveau nom standardisé pour l'historique
    prev_path = os.path.join(DATA_DIR, f"{PREVIOUS_SEASON_TAG}_ratings.csv")
    if os.path.exists(prev_path):
        print(f"  > Loading baseline from {PREVIOUS_SEASON_TAG.upper()}...")
        df_prev = pd.read_csv(prev_path)
        inherited_elo = {str(row['Player']): float(row.get('ELO', 1200.0)) for _, row in df_prev.iterrows()}
        print(f"  > {len(inherited_elo)} players inherited.")
    else:
        print(f"  > Warning: Previous ratings file not found at {prev_path}")
else:
    print("  > No previous season defined. Starting fresh (1200.0).")

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
            print(f"  > Loaded {len(game_id_mapping)} manual date corrections.")
except Exception as e:
    print(f"  > Note: Corrections skipped or failed ({e}).")

# =========================================================================
# --- 4. FETCH MATCH DATA ---
# =========================================================================
print("\n=== FETCHING API DATA ===")
print(f"  > Requesting matches for Tournament {TOURNAMENT_ID} (Cutoff: {CUTOFF_DATE_STR})...")

all_matches = []
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except: 
        break

raw_data = [] 
for m in all_matches:
    participants = m.get('participants', [])
    if len(participants) == 4:
        for p in participants:
            raw_data.append({
                'GameID': m['id'], 'Player': p.get('player'),
                'Score': float(p.get('tournament_score', 0.0)), 'Date_Closed': m.get('date_closed')
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
print("\n=== CALCULATING ELO & STATS ===")
print("  > Processing matches and generating history...")

elo_ratings = {**{p: 1200.0 for p in df['Player'].unique()}, **inherited_elo} if not df.empty else inherited_elo.copy()
peak_elo = elo_ratings.copy()
player_stats = {p: {'games': 0, 'wins': 0.0} for p in elo_ratings}
last_diff = {p: 0.0 for p in elo_ratings}

start_label = f"{PREVIOUS_SEASON_TAG.upper()} Final" if PREVIOUS_SEASON_TAG else "Start"

# Allégement de la structure initiale : [Label, Elo, MatchID]
player_history = {p: [[start_label if p in inherited_elo else "Start", round(r), None]] for p, r in elo_ratings.items()}
archive_matches_list = []
pre_match_elos = {}

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    current_match_sum = round(sum(elo_ratings[p['Player']] for p in match_participants))
    current_date = match_participants[0]['Date_Closed'].strftime('%Y-%m-%d')
    
    total_q = sum(10**(elo_ratings[p['Player']]/400) for p in match_participants)
    deltas_this_match = {}
    
    for p in match_participants:
        name = p['Player']
        actual = p['Score']
        expected = (10**(elo_ratings[name]/400)) / total_q
        
        pre_match_elos[(name, game_id)] = round(elo_ratings[name])
        
        stats = player_stats[name]
        stats['games'] += 1
        stats['wins'] += actual
        
        k = 80 if stats['games'] <= 10 else (40 if stats['games'] <= 50 else 20)
        change = k * (actual - expected)
        
        elo_ratings[name] += change
        last_diff[name] = change
        deltas_this_match[name] = round(change)
        
        if elo_ratings[name] > peak_elo[name]: 
            peak_elo[name] = elo_ratings[name]
        
        # Allégement de l'historique : suppression de la chaîne URL redondante
        player_history[name].append([current_date, round(elo_ratings[name]), int(game_id)])

    archive_matches_list.append({
        'MatchID': int(game_id),
        'Date': current_date,
        'players': [{
            'name': p['Player'],
            'delta': deltas_this_match[p['Player']],
            'is_winner': bool(p['Score'] >= 0.5)
        } for p in match_participants],
        'ELO_Sum': current_match_sum
    })

# =========================================================================
# --- 6. SEASON END REBALANCING ---
# =========================================================================
active_players = [p for p in elo_ratings if player_stats[p]['games'] >= 1]
inactive_players = [p for p in elo_ratings if player_stats[p]['games'] == 0]

num_players, num_active = len(elo_ratings), len(active_players)

if num_active > 0 and num_players > 0:
    actual_sum = sum(elo_ratings.values())
    theoretical_sum = num_players * 1200.0
    total_deficit = theoretical_sum - actual_sum
    bonus_per_player = total_deficit / num_active
    
    print("\n=== SEASON END REBALANCING ===")
    print(f"  > Total database players: {num_players} | Active: {num_active} | Inactive: {len(inactive_players)}")
    print(f"  > Actual Total Elo: {actual_sum:.2f} | Theoretical: {theoretical_sum:.2f}")
    print(f"  > Global deficit injected: {total_deficit:.2f} points (+{bonus_per_player:.4f} per active)")
    
    for p in active_players:
        elo_ratings[p] += bonus_per_player
        if elo_ratings[p] > peak_elo[p]: 
            peak_elo[p] = elo_ratings[p]
        # Alignement structure à 3 éléments
        player_history[p].append(["Final", round(elo_ratings[p]), None])           

for p in inactive_players:
    player_history[p].append(["Final", round(elo_ratings[p]), None])        

# =========================================================================
# --- 7. EXPORT FINAL RATINGS (LEADERBOARD) ---
# =========================================================================
results = [
    {
        'Player': p, 'ELO': rating, 'Games': player_stats[p]['games'], 'Wins': player_stats[p]['wins'],
        'Win Rate': f"{(player_stats[p]['wins']/player_stats[p]['games']):.1%}" if player_stats[p]['games'] > 0 else "0.0%", 
        'Peak': round(peak_elo[p]), 'Last': f"+{round(last_diff[p])}" if round(last_diff[p]) > 0 else str(round(last_diff[p])),
        'Qualified': (player_stats[p]['games'] >= 10 and round(rating) >= 1200)
    } for p, rating in elo_ratings.items()
]

final_df = pd.DataFrame(results).sort_values(by='ELO', ascending=False)

rank, ranks = 1, []
for _, row in final_df.iterrows():
    if row['Qualified']:
        ranks.append(rank)
        rank += 1
    else:
        ranks.append("-")
        
final_df.insert(0, 'Rank', ranks)
final_df = final_df.drop(columns=['Qualified'])

# =========================================================================
# --- 8. GENERATE NARRATIVE JOURNEY RELATIONS DATA ---
# =========================================================================
print("\n=== EXTRACTING RELATIONSHIPS ===")
print("  > Mapping trophies, banes, and unique opponents...")

def extract_relations(matches_list, pre_match_elos):
    all_players = {p['name'] for m in matches_list for p in m['players']}
    
    relations = {p: {
        "trophy": {"name": None, "elo": -1}, 
        "bane": {"name": None, "elo": 99999},
        "unique_opponents": 0
    } for p in all_players}
    
    opponents_track = {p: set() for p in all_players}
            
    for m in matches_list:
        match_id = m['MatchID']
        p_names = [p['name'] for p in m['players']]
        
        for p_name in p_names:
            opponents_track[p_name].update(opp for opp in p_names if opp != p_name)
                    
        winners = [p for p in m['players'] if p['is_winner']]
        losers = [p for p in m['players'] if not p['is_winner']]

        for w in winners:
            for l in losers:
                l_elo = pre_match_elos.get((l['name'], match_id))
                if l_elo is not None and l_elo > relations[w['name']]['trophy']['elo']:
                    relations[w['name']]['trophy'] = {"name": l['name'], "elo": l_elo}

        for l in losers:
            for w in winners:
                w_elo = pre_match_elos.get((w['name'], match_id))
                if w_elo is not None and w_elo < relations[l['name']]['bane']['elo']:
                    relations[l['name']]['bane'] = {"name": w['name'], "elo": w_elo}
    
    for p in all_players:
        relations[p]["unique_opponents"] = len(opponents_track[p])
        
    return relations

relations_map = extract_relations(archive_matches_list, pre_match_elos)

# =========================================================================
# --- 9. FINAL EXPORTS ---
# =========================================================================
print("\n=== EXPORTING ARCHIVES ===")
os.makedirs(DATA_DIR, exist_ok=True)

def safe_save(path, data, is_json=False):
    if os.path.exists(path):
        os.remove(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4) if is_json else data.to_csv(path, index=False)
    print(f"  > {os.path.basename(path)} saved.")

safe_save(OUTPUT_RATINGS, final_df)

if archive_matches_list:
    archive_matches_list = sorted(archive_matches_list, key=lambda x: x['ELO_Sum'], reverse=True)
    for idx, m in enumerate(archive_matches_list, start=1):
        m['Rank'] = idx
safe_save(OUTPUT_MATCHES, archive_matches_list, is_json=True)

safe_save(OUTPUT_HISTORY, player_history, is_json=True)
safe_save(OUTPUT_RELATIONS, relations_map, is_json=True)

metadata = {"season_tag": SEASON_TAG.upper(), "cutoff_date": CUTOFF_DATE_STR, "match_count": len(archive_matches_list)}
safe_save(OUTPUT_METADATA, metadata, is_json=True)

print(f"\n✨ Archives for {SEASON_TAG.upper()} successfully generated!")
