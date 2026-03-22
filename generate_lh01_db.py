import os
import requests
import pandas as pd
import json
from datetime import datetime, date

# --- 1. Configuration ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24  # Season LH01 Tournament ID

# MANUAL CUTOFF DATE FOR LH01
CUTOFF_DATE = datetime.strptime("2026-03-31", "%Y-%m-%d").date()

# Output directories and files
os.makedirs('data', exist_ok=True)
OUTPUT_RATINGS = "data/lh01_final_ratings.csv"
OUTPUT_HISTORY = "data/lh01_history_full.json"
OUTPUT_MATCHES = "data/lh01_matches_fixed.csv"

# --- 2. Load Correction File (Excel) ---
CORRECTIONS_PATH = 'Root_Elo_LH01_Corrected_Dates.xlsx'
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(CORRECTIONS_PATH):
        df_updates = pd.read_excel(CORRECTIONS_PATH, engine='openpyxl')
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"✅ Loaded {len(game_id_mapping)} manual date corrections.")
except Exception as e:
    print(f"⚠️ Note: Excel skipped or error: {e}")

# --- 3. Fetch Match Data ---
all_matches = []
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

print(f"🌐 Fetching LH01 data (Tournament {TOURNAMENT_ID})...")
while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except Exception as e:
        print(f"❌ API Error: {e}")
        break

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

# --- 4. Processing and Cutoff ---
df = pd.DataFrame(raw_data)
df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

# Apply manual date corrections from Excel
try:
    if not game_id_mapping.empty:
        mask = df['GameID'].isin(game_id_mapping.index)
        if mask.any():
            # Preserve original time (HH:MM:SS) while changing the date
            original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
            new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
            combined_datetimes = new_dates + ' ' + original_times
            df.loc[mask, 'Date_Closed'] = pd.to_datetime(combined_datetimes, utc=True)
            print(f"🔧 Corrected dates for {mask.sum() // 4} matches.")
except Exception as e:
    print(f"Mapping error: {e}")

# FILTER: Keep matches strictly on or before the cutoff date
df = df[df['Date_Closed'].dt.date <= CUTOFF_DATE].copy()
# Sort chronologically to ensure Elo chain reaction is correct
df = df.sort_values(by='Date_Closed').reset_index(drop=True)

print(f"📊 {len(df)//4} matches retained after cutoff on {CUTOFF_DATE}.")

# --- 5. ELO Calculation & History Tracking ---
elo_ratings = {player: 1200 for player in df['Player'].unique()}
player_stats = {player: {'games': 0} for player in df['Player'].unique()}
player_history = {player: [["Start LH01", 1200]] for player in df['Player'].unique()}

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    # Calculate the denominator for the Elo formula
    total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
    
    for p in match_participants:
        name = p['Player']
        actual = p['Score']
        expected = (10**(elo_ratings[name]/400)) / total_q
        
        # Dynamic K-Factor based on games played
        player_stats[name]['games'] += 1
        g = player_stats[name]['games']
        k = 80 if g <= 10 else (40 if g <= 50 else 20)
            
        # Update rating and save history point
        elo_ratings[name] += k * (actual - expected)
        player_history[name].append([current_date, round(elo_ratings[name])])

# --- 6. Final Exports ---

# A. Final Ratings (to initialize LH02 starting ELO)
final_ratings_df = pd.DataFrame(list(elo_ratings.items()), columns=['Player', 'ELO'])
final_ratings_df['ELO'] = final_ratings_df['ELO'].round().astype(int)
final_ratings_df.to_csv(OUTPUT_RATINGS, index=False)

# B. Full History (for Trends / Player Journey charts)
with open(OUTPUT_HISTORY, 'w', encoding='utf-8') as f:
    json.dump(player_history, f, indent=4)

# C. Corrected Matches List (Clean data archive)
df.to_csv(OUTPUT_MATCHES, index=False)

print(f"✨ Completed. LH01 data frozen at {CUTOFF_DATE} in the /data folder.")
