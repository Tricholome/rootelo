import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone
import json
from jinja2 import Environment, FileSystemLoader

# =========================================================================
# --- 0. PATH CONFIGURATION (EXTERNAL FILES) ---
# =========================================================================
# Define base data directory and specific season folders
DATA_DIR = "data"

# Correction file path
CORRECTIONS_FILE = os.path.join(DATA_DIR, "lh01_corrections.csv")

# LH01 Archive files
ARCHIVE_LEADERBOARD_FILE = os.path.join(DATA_DIR, "lh01_final_ratings.csv")
ARCHIVE_MATCHES_FILE     = os.path.join(DATA_DIR, "lh01_matches_fixed.csv")
ARCHIVE_TRENDS_FILE      = os.path.join(DATA_DIR, "lh01_history_full.json")

# =========================================================================
# --- 1. JINJA2 & NAVIGATION SETUP ---
# =========================================================================
# Initialize Jinja2 environment for HTML template rendering
env = Environment(loader=FileSystemLoader('templates'))

# Define menu structure for the website header
NAV_ITEMS = [
    {'id': 'index', 'url': 'index.html', 'label': 'Leaderboard'},
    {'id': 'matches', 'url': 'matches.html', 'label': 'Top Tables'},
    {'id': 'trends', 'url': 'trends.html', 'label': "Player's Journey"},
    {'id': 'about', 'url': 'about.html', 'label': 'Codex'}
]

# =========================================================================
# --- 2. API & HELPER UTILITIES ---
# =========================================================================
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24

today = date.today()
CUTOFF_DATE = today - timedelta(days=1)
print(f"Update started. Filtering matches closed before: {today}")

def get_tier_icon(rating, games):
    if games < 10: return None, "unranked"  
    r = round(rating)
    if r >= 1500: return None, "bird"
    if r >= 1400: return None, "fox"
    if r >= 1300: return None, "rabbit"
    if r >= 1200: return None, "mouse"
    return None, "squirrel"

def prepare_leaderboard_data(df):
    players_list = []
    if df.empty: return []
    
    for _, row in df.iterrows():
        _, tier_name = get_tier_icon(row['ELO'], row['Games'])
        players_list.append({
            'Rank': row['Rank'],
            'tier': tier_name,
            'display_name': str(row['Player']).split('+')[0].split('#')[0],
            'ELO': row['ELO'],
            'Games': row['Games'],
            'Wins': row['Wins'],
            'Win_Rate': row['Win Rate'],
            'Peak': row['Peak'],
            'Last': row['Last']
        })
    return players_list

def prepare_matches_data(df):
    prepared = []
    if df.empty: return []

    def clean_names(name_str):
        if pd.isna(name_str) or not str(name_str).strip(): return ""
        parts = [str(n).strip().split('+')[0].split('#')[0] for n in str(name_str).split(',')]
        return ", ".join(parts)

    for _, row in df.iterrows():
        prepared.append({
            'rank': row['Rank'],
            'elo_sum': row['ELO_Sum'],
            'date': row['Date'],
            'winner': clean_names(row.get("Winner", "")),
            'others': clean_names(row.get("Other Players", "")),
            'match_id': row['MatchID'],
            'match_url': f"https://rootleague.pliskin.dev/match/{row['MatchID']}/"
        })
    return prepared

def prepare_trends_data(history_dict):
    if not history_dict:
        return {"history_json": "{}", "player_names": []}
    
    return {
        "history_json": json.dumps(history_dict),
        "player_names": sorted(list(history_dict.keys()))
    }

def render_page(template_name, output_name, **kwargs):
    template = env.get_template(template_name)
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
# --- 3. LOAD CORRECTIONS ---
# =========================================================================
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(CORRECTIONS_FILE):
        df_updates = pd.read_csv(CORRECTIONS_FILE, parse_dates=['New_Date'])
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"✅ Loaded corrections from {CORRECTIONS_FILE}")
except Exception as e:
    print(f"ℹ️ Note: No corrections loaded: {e}")

# =========================================================================
# --- 4. LOAD ARCHIVE DATA (LH01) ---
# =========================================================================
archive_final_df = pd.DataFrame()
archive_matches_df = pd.DataFrame()
archive_history = {}

try:
    if os.path.exists(ARCHIVE_LEADERBOARD_FILE):
        archive_final_df = pd.read_csv(ARCHIVE_LEADERBOARD_FILE)
        if 'Tier' not in archive_final_df.columns:
            archive_final_df['Tier'] = None 
    
    if os.path.exists(ARCHIVE_MATCHES_FILE):
        archive_matches_df = pd.read_csv(ARCHIVE_MATCHES_FILE)
    
    if os.path.exists(ARCHIVE_TRENDS_FILE):
        with open(ARCHIVE_TRENDS_FILE, "r", encoding="utf-8") as f:
            archive_history = json.load(f)
            archive_history = {k.split('+')[0].split('#')[0]: v for k, v in archive_history.items()}
    print("Archive LH01 loaded successfully.")
except Exception as e:
    print(f"Error loading archive files: {e}")

# =========================================================================
# --- 5. FETCH & PROCESS CURRENT SEASON ---
# =========================================================================
all_matches = []
T_ID = int(TOURNAMENT_ID)
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={T_ID}"

print(f"🌐 Requesting data for Tournament {T_ID}...")
while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        if res.status_code == 400:
            print(f"ℹ️ Tournament {T_ID} not yet active on API. Proceeding with empty data.")
            break
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except Exception as e:
        print(f"📡 API Note: {e}")
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

df = pd.DataFrame(raw_data)
if not df.empty:
    df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)
    if not game_id_mapping.empty:
        game_id_mapping.index = game_id_mapping.index.astype(int)
        mask = df['GameID'].isin(game_id_mapping.index)
        if mask.any():
            original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
            new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
            df.loc[mask, 'Date_Closed'] = pd.to_datetime(new_dates + ' ' + original_times, utc=True)
            print(f"🔧 Applied date corrections to {mask.sum()} entries.")

    df = df[df['Date_Closed'].dt.date <= CUTOFF_DATE].copy()
    df = df.sort_values(by='Date_Closed').reset_index(drop=True)
    
# =========================================================================
# --- 6. ELO CALCULATION & STANDINGS ---
# =========================================================================
current_final_df = pd.DataFrame()
current_matches_df = pd.DataFrame()
current_history = {}
match_history_data = []

elo_ratings = {}
# if not archive_final_df.empty:
#     for _, row in archive_final_df.iterrows():
#         p_name = str(row['Player'])
#         elo_ratings[p_name] = float(row.get('ELO', 1200))
#     print(f"📊 Initialized {len(elo_ratings)} players from LH01 archive.")

if not df.empty:
    for player in df['Player'].unique():
        if player not in elo_ratings:
            elo_ratings[player] = 1200.0

peak_elo = {p: r for p, r in elo_ratings.items()}
last_diff = {p: 0 for p in elo_ratings}
player_stats = {p: {'games': 0, 'wins': 0.0} for p in elo_ratings}
player_history = {p: [["LH01 Final", round(r)]] for p, r in elo_ratings.items()}

if not df.empty:
    for game_id, group in df.groupby('GameID', sort=False):
        match_participants = group.to_dict('records')
        current_match_sum = sum([elo_ratings[p['Player']] for p in match_participants])
        current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
        
        winners = [p['Player'] for p in match_participants if p['Score'] >= 0.5]
        others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
        
        match_history_data.append({
            'MatchID': game_id, 
            'Date': current_date, 
            'Winner': ", ".join(winners),
            'Other Players': ", ".join(others), 
            'ELO_Sum': round(current_match_sum)
        })

        total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
        for p in match_participants:
            name = p['Player']
            expected = (10**(elo_ratings[name]/400)) / total_q
            player_stats[name]['games'] += 1
            player_stats[name]['wins'] += p['Score']
            
            k = 80 if player_stats[name]['games'] <= 10 else (40 if player_stats[name]['games'] <= 50 else 20)
            change = k * (p['Score'] - expected)
            
            elo_ratings[name] += change
            last_diff[name] = change
            if elo_ratings[name] > peak_elo[name]: 
                peak_elo[name] = elo_ratings[name]
            player_history[name].append([current_date, round(elo_ratings[name])])

current_matches_df = pd.DataFrame(match_history_data)
if not current_matches_df.empty:
    current_matches_df = current_matches_df.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
    current_matches_df.insert(0, 'Rank', range(1, len(current_matches_df) + 1))

# =========================================================================
# --- 7. FINAL LEADERBOARD GENERATION ---
# =========================================================================
leaderboard_list = []
for p_name, rating in elo_ratings.items():
    s = player_stats.get(p_name, {'wins': 0, 'games': 0})
    diff = round(last_diff.get(p_name, 0))
    is_qual = (s['games'] >= 10 and rating >= 1200)
    
    leaderboard_list.append({
        'Rank': 0, 'Player': p_name, 'ELO': round(rating), 'Games': s['games'],
        'Wins': s['wins'], 'Win Rate': f"{(s['wins']/s['games']):.1%}" if s['games'] > 0 else "0.0%",
        'Peak': round(peak_elo.get(p_name, rating)), 
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': is_qual
    })

current_final_df = pd.DataFrame(leaderboard_list).sort_values(by='ELO', ascending=False)

rank_counter = 1
ranks = []
for _, row in current_final_df.iterrows():
    if row['Qualified']:
        ranks.append(rank_counter)
        rank_counter += 1
    else: 
        ranks.append("-")
current_final_df['Rank'] = ranks

current_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}

# =========================================================================
# --- 8. FILTERS & HTML GENERATION (JINJA2) ---
# =========================================================================
print("\n=== GÉNÉRATION DU SITE ===")

# Application du filtre "Minimum 1 victoire" (Identique à ton ancien code)
display_current_df = pd.DataFrame()
if not current_final_df.empty:
    display_current_df = current_final_df[current_final_df['Wins'].astype(float) >= 1].copy()

display_archive_df = pd.DataFrame()
if not archive_final_df.empty:
    display_archive_df = archive_final_df[archive_final_df['Wins'].astype(float) >= 1].copy()

# A. Génération des pages LH02 (Saison en cours)
render_page(
    "leaderboard.html", 
    "index.html",
    title="Leaderboard • Rootelo",
    page_id="index",
    is_archive=False,
    has_seasons=True,
    current_page_base="index",
    page_heading="Leaderboard",
    description=f"Minimum 1 win required for display. Data tracked until {CUTOFF_DATE}.",
    players=prepare_leaderboard_data(display_current_df)
)

render_page(
    "matches.html", 
    "matches.html",
    title="Top Tables • Rootelo",
    page_id="matches",
    is_archive=False,
    has_seasons=True,
    page_heading="Top Tables",
    description="Games ranked by total ELO. Click a Game ID to view full match details.",
    matches=prepare_matches_data(current_matches_df)
)

render_page(
    "trends.html", 
    "trends.html",
    title="Player's Journey • Rootelo",
    page_id="trends",
    is_archive=False,
    has_seasons=True,
    page_heading="Player's Journey",
    description="Search for a player to see their ELO evolution over the season.",
    history_json=json.dumps(current_history),
    player_names=sorted(list(current_history.keys()))
)

# B. Génération des pages Archives (LH01)
render_page(
    "leaderboard.html", 
    "index_lh01.html",
    title="Leaderboard • Rootelo",
    page_id="index",
    is_archive=True,
    has_seasons=True,
    current_page_base="index",
    page_heading="Leaderboard",
    description="Minimum 1 win required for display.",
    players=prepare_leaderboard_data(display_archive_df)
)

render_page(
    "matches.html",
    "matches_lh01.html", 
    title="Top Tables • Rootelo",
    page_id="matches",
    is_archive=True,
    has_seasons=True,
    page_heading="Top Tables",
    description="Games ranked by total ELO. Click a Game ID to view full match details.",
    matches=prepare_matches_data(archive_matches_df)
)

render_page(
    "trends.html", 
    "trends_lh01.html",
    title="Player's Journey • Rootelo",
    page_id="trends",
    is_archive=True,
    has_seasons=True,
    page_heading="Player's Journey",
    description="Search for a player to see their ELO evolution over the season.",
    history_json=json.dumps(archive_history),
    player_names=sorted(list(archive_history.keys()))
)

# C. Génération des pages uniques
render_page(
    "about.html", 
    "about.html",
    title="Codex • Rootelo",
    page_id="about",
    is_archive=False,
    has_seasons=False,
    page_heading="Codex",
    description="Understanding the mechanics of Rootelo.",
)

render_page(
    "cache.html", 
    "cache.html",
    title="Undergrowth • Rootelo",
    page_id="cache",
    is_archive=False,
    has_seasons=False,
    page_heading="Undergrowth",
    description="No rank? No stress. The Woodland has room for all kinds of critters.",
)

print("Génération terminée avec succès !")
