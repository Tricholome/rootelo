import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone
import json
from jinja2 import Environment, FileSystemLoader

# =========================================================================
# --- 0. PATH CONFIGURATION & SEASON SETTINGS ---
# =========================================================================
DATA_DIR = "data"

# Add future seasons here when they are archived (e.g., ["lh01", "lh02"])
ARCHIVE_SEASONS = ["lh01"] 

CURRENT_SEASON_TAG = "lh02"
TOURNAMENT_ID = 25

CORRECTIONS_FILE = os.path.join(DATA_DIR, f"{CURRENT_SEASON_TAG}_corrections.csv")

# =========================================================================
# --- 1. JINJA2 & NAVIGATION SETUP ---
# =========================================================================
env = Environment(loader=FileSystemLoader('templates'))

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
TOURNAMENT_ID = 25

today = date.today()
CUTOFF_DATE = today - timedelta(days=1)
print(f"Update started. Filtering matches closed before: {today}")

def get_tier_icon(rating, games):
    if games < 10: return None, "unranked"  
    r = round(rating) # Ensure tier is based on visual score
    if r >= 1600: return None, "stag"
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
            'ELO': row['ELO'], # Will be strictly integer when reaching here
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
        "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
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
# --- 4. LOAD ARCHIVE DATA ---
# =========================================================================
archives_raw_data = {}
elo_ratings = {} # Engine baseline Elo

for tag in ARCHIVE_SEASONS:
    print(f"📂 Loading archive: {tag.upper()}")
    archives_raw_data[tag] = {
        'final_df': pd.DataFrame(),
        'matches_df': pd.DataFrame(),
        'history': {}
    }
    
    path_ratings = os.path.join(DATA_DIR, f"{tag}_final_ratings.csv")
    path_matches = os.path.join(DATA_DIR, f"{tag}_matches_fixed.csv")
    path_trends  = os.path.join(DATA_DIR, f"{tag}_history_full.json")
    path_meta = os.path.join(DATA_DIR, f"{tag}_metadata.json")
    archives_raw_data[tag]['metadata'] = {"cutoff_date": "N/A", "match_count": 0}
    if os.path.exists(path_meta):
        with open(path_meta, "r", encoding="utf-8") as f:
            archives_raw_data[tag]['metadata'] = json.load(f)
    
    try:
        if os.path.exists(path_ratings):
            df_ratings = pd.read_csv(path_ratings)
            
            # Load FLOAT Elo for calculation engine
            for _, row in df_ratings.iterrows():
                p_name = str(row['Player'])
                elo_ratings[p_name] = float(row.get('ELO', 1200.0))
                
            # Clean archive DF for web display: Round ELO to integers
            df_ratings['ELO'] = df_ratings['ELO'].round().astype(int)
            if 'Tier' not in df_ratings.columns:
                df_ratings['Tier'] = None 
            
            archives_raw_data[tag]['final_df'] = df_ratings
        
        if os.path.exists(path_matches):
            archives_raw_data[tag]['matches_df'] = pd.read_csv(path_matches)
        
        if os.path.exists(path_trends):
            with open(path_trends, "r", encoding="utf-8") as f:
                history = json.load(f)
                archives_raw_data[tag]['history'] = {k.split('+')[0].split('#')[0]: v for k, v in history.items()}
                
        print(f"  ✅ Archive {tag.upper()} loaded successfully.")
    except Exception as e:
        print(f"  ⚠️ Error loading archive {tag.upper()}: {e}")
        
archived_player_names = set(elo_ratings.keys())

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
match_history_data = []

if not df.empty:
    for player in df['Player'].unique():
        if player not in elo_ratings:
            elo_ratings[player] = 1200.0

peak_elo = {p: r for p, r in elo_ratings.items()}
last_diff = {p: 0.0 for p in elo_ratings}
player_stats = {p: {'games': 0, 'wins': 0.0} for p in elo_ratings}

player_history = {}
for p, r in elo_ratings.items():
    if ARCHIVE_SEASONS and p in archived_player_names:
        label = f"{ARCHIVE_SEASONS[-1].upper()} Final"
    else:
        label = "Start"
    player_history[p] = [[label, round(r)]]

if not df.empty:
    for game_id, group in df.groupby('GameID', sort=False):
        match_participants = group.to_dict('records')
        current_match_sum = round(sum([elo_ratings[p['Player']] for p in match_participants]))
        current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
        
        winners = [p['Player'] for p in match_participants if p['Score'] >= 0.5]
        others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
        
        match_history_data.append({
            'MatchID': game_id, 
            'Date': current_date, 
            'Winner': ", ".join(winners),
            'Other Players': ", ".join(others), 
            'ELO_Sum': current_match_sum
        })

        total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
        for p in match_participants:
            name = p['Player']
            actual = p['Score']
            expected = (10**(elo_ratings[name]/400)) / total_q
            player_stats[name]['games'] += 1
            player_stats[name]['wins'] += actual
            
            k = 80 if player_stats[name]['games'] <= 10 else (40 if player_stats[name]['games'] <= 50 else 20)
            change = k * (actual - expected)
            
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
    display_elo = round(rating)
    diff = round(last_diff.get(p_name, 0))
    is_qual = (s['games'] >= 10 and display_elo >= 1200)
    
    leaderboard_list.append({
        'Player': p_name, 
        'ELO': rating,  # Keeps float for sorting
        'Display_ELO': display_elo,
        'Games': s['games'],
        'Wins': s['wins'], 
        'Win Rate': f"{(s['wins']/s['games']):.1%}" if s['games'] > 0 else "0.0%",
        'Peak': round(peak_elo.get(p_name, rating)), 
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': is_qual
    })

if leaderboard_list:
    current_final_df = pd.DataFrame(leaderboard_list).sort_values(by='ELO', ascending=False)
    
    rank_counter = 1
    ranks = []
    for _, row in current_final_df.iterrows():
        if row['Qualified']:
            ranks.append(rank_counter)
            rank_counter += 1
        else: 
            ranks.append("-")
            
    current_final_df.insert(0, 'Rank', ranks)
    # Apply Visual ELO for web templates
    current_final_df['ELO'] = current_final_df['Display_ELO']
    current_final_df = current_final_df.drop(columns=['Display_ELO'])
else:
    current_final_df = pd.DataFrame(columns=['Rank', 'Player', 'ELO', 'Games', 'Wins', 'Win Rate', 'Peak', 'Last', 'Qualified'])

current_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}

# =========================================================================
# --- 8. DATA FILTERING & PREPARATION ---
# =========================================================================
print("\n=== GENERATING SITE ASSETS ===")

# --- A. Prepare Current Season ---
current_meta = {
    'match_count': df['GameID'].nunique() if not df.empty else 0,
    'cutoff_date': CUTOFF_DATE.strftime('%Y-%m-%d')
}
display_leaderboard_current = []
if not current_final_df.empty:
    filtered_df = current_final_df[current_final_df['Wins'].astype(float) >= 1].copy()
    display_leaderboard_current = prepare_leaderboard_data(filtered_df)

display_matches_current = []
if not current_matches_df.empty:
    display_matches_current = prepare_matches_data(current_matches_df)[:100]

display_trends_current = prepare_trends_data(current_history)

# --- B. Prepare Archives ---
display_archives = {}
for tag in ARCHIVE_SEASONS:
    raw = archives_raw_data[tag]
    
    lb_data = []
    if not raw['final_df'].empty:
        filtered_df = raw['final_df'][raw['final_df']['Wins'].astype(float) >= 1].copy()
        lb_data = prepare_leaderboard_data(filtered_df)
        
    match_data = []
    if not raw['matches_df'].empty:
        match_data = prepare_matches_data(raw['matches_df'])[:100]
        
    display_archives[tag] = {
        'leaderboard': lb_data,
        'matches': match_data,
        'trends': prepare_trends_data(raw['history'])
    }
    
# =========================================================================
# --- 9. HALL OF FAME : MEILLEUR STREAK PERSONNEL PAR TIER ---
# =========================================================================
print("  > Compiling Hall of Fame...")

def extract_all_streaks(history, player_full_name):
    streaks = []
    if len(history) < 11: return streaks
    short_name = player_full_name.split('+')[0].split('#')[0]
    current_s = None

    for i in range(10, len(history)):
        date_str, elo_val = history[i][0], history[i][1]
        if "-" not in str(date_str): continue
        _, tier_now = get_tier_icon(elo_val, 11)

        if tier_now not in ['bird', 'stag']:
            tier_now = None

        if tier_now != (current_s['tier'] if current_s else None):
            if current_s: streaks.append(current_s)
            if tier_now:
                current_s = {
                    'player': short_name, 
                    'tier': tier_now, 
                    'ascension': date_str, 
                    'peak': elo_val, 
                    'streak_count': 1
                }
            else:
                current_s = None
        elif current_s:
            current_s['streak_count'] += 1
            current_s['peak'] = max(current_s['peak'], elo_val)

    if current_s: streaks.append(current_s)
    return streaks

best_streaks_only = {}
sources = []

if not current_final_df.empty:
    for _, row in current_final_df.iterrows():
        sources.append((row['Player'], player_history.get(row['Player'], [])))

for tag in ARCHIVE_SEASONS:
    raw = archives_raw_data.get(tag, {})
    for p_name, h in raw.get('history', {}).items():
        sources.append((p_name, h))

for p_name, h in sources:
    player_streaks = extract_all_streaks(h, p_name)
    for s in player_streaks:
        key = (s['player'], s['tier'])
        if key not in best_streaks_only or s['streak_count'] > best_streaks_only[key]['streak_count']:
            best_streaks_only[key] = s

hall_of_fame_data = sorted(best_streaks_only.values(), key=lambda x: (x['tier'] != 'stag', -x['streak_count']))

# =========================================================================
# --- 10. SITE GENERATION (JINJA2 RENDERING) ---
# =========================================================================
print("\n=== GENERATING HTML PAGES ===")

def render_core_pages(file_suffix, is_archive, tag, lb_data, match_data, trends_data, meta):
    """Helper to generate the 3 main pages identically for live and archives."""
    
    render_page(
        "leaderboard.html", f"index{file_suffix}.html", page_id="index", current_page_base="index",
        title="Leaderboard • Rootelo", page_heading="Leaderboard",
        description=f"Minimum 1 win required for display. Only&nbsp;players&nbsp;with&nbsp;a&nbsp;Tier&nbsp;are&nbsp;ranked.<br><br><i><small>Includes {meta.get('match_count', 0)} matches up to {meta.get('cutoff_date', 'N/A')}.</i></small>",
        is_archive=is_archive, has_seasons=True, season_tag=tag,
        archive_seasons=ARCHIVE_SEASONS,
        current_season_tag=CURRENT_SEASON_TAG,
        num_matches=meta.get('match_count', 0),
        cutoff_date=meta.get('cutoff_date', "N/A"),
        players=lb_data
    )

    render_page(
        "matches.html", f"matches{file_suffix}.html", page_id="matches",
        title="Top Tables • Rootelo", page_heading="Top Tables",
        description="Top 100 games ranked by total Elo. Click&nbsp;a&nbsp;Game&nbsp;ID&nbsp;for&nbsp;match&nbsp;details.",
        is_archive=is_archive, has_seasons=True, season_tag=tag,
        archive_seasons=ARCHIVE_SEASONS,
        current_season_tag=CURRENT_SEASON_TAG,
        matches=match_data
    )

    render_page(
        "trends.html", f"trends{file_suffix}.html", page_id="trends",
        title="Player's Journey • Rootelo", page_heading="Player's Journey",
        description="Search for a player to see their Elo&nbsp;evolution&nbsp;over&nbsp;the&nbsp;season.",
        is_archive=is_archive, has_seasons=True, season_tag=tag,
        archive_seasons=ARCHIVE_SEASONS,
        current_season_tag=CURRENT_SEASON_TAG,
        history_json=trends_data['history_json'], player_names=trends_data['player_names']
    )

# --- A. Render Current Season Pages ---
# (file_suffix is empty so it generates 'index.html', 'matches.html'...)
render_core_pages(
    file_suffix="", 
    is_archive=False, 
    tag=CURRENT_SEASON_TAG, 
    lb_data=display_leaderboard_current, 
    match_data=display_matches_current, 
    trends_data=display_trends_current,
    meta=current_meta
)

# --- B. Render Archives Pages ---
# (file_suffix will be '_lh01' so it generates 'index_lh01.html', etc.)
for tag in ARCHIVE_SEASONS:
    data = display_archives[tag]
    render_core_pages(
        file_suffix=f"_{tag}", 
        is_archive=True, 
        tag=tag, 
        lb_data=data['leaderboard'], 
        match_data=data['matches'], 
        trends_data=data['trends'],
        meta=archives_raw_data[tag]['metadata']
    )

# --- C. Render Static Pages ---
render_page(
    "about.html", "about.html", title="Codex • Rootelo", page_id="about",
    is_archive=False, has_seasons=False, page_heading="Codex",
    description="Understanding the fundamental rules and&nbsp;mechanics&nbsp;of&nbsp;Rootelo."
)

render_page(
    "cache.html", "cache.html", title="Undergrowth • Rootelo", page_id="cache",
    is_archive=False, has_seasons=False, page_heading="Undergrowth",
    description="A sanctuary for the critters who&nbsp;never&nbsp;sought&nbsp;a&nbsp;crown.",
    hall_of_fame=hall_of_fame_data
)

print("✨ Website generated successfully!")
