import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone
import json
from jinja2 import Environment, FileSystemLoader

# =========================================================================
# --- 0. CONFIGURATION & CONSTANTS ---
# =========================================================================
DATA_DIR = "data"
ARCHIVE_SEASONS = ["lh01", "lh02"] 
CURRENT_SEASON_TAG = "lh03"
TOURNAMENT_ID = 26

CORRECTIONS_FILE = os.path.join(DATA_DIR, f"{CURRENT_SEASON_TAG}_corrections.csv")

CONTENT_FILE = os.path.join(DATA_DIR, "pages_content.json")
if os.path.exists(CONTENT_FILE):
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        PAGES = json.load(f)
else:
    PAGES = {}

NAV_ITEMS = [
    {'id': 'index', 'url': 'index.html', 'label': 'Leaderboard'},
    {'id': 'matches', 'url': 'matches.html', 'label': 'Top Tables'},
    {'id': 'trends', 'url': 'trends.html', 'label': "Player's Journey"},
    {'id': 'about', 'url': 'about.html', 'label': 'Codex'}
]

TIER_THRESHOLDS = [
    (1600, "stag"),
    (1500, "bird"),
    (1400, "fox"),
    (1300, "rabbit"),
    (1200, "mouse")
]
TIER_HIERARCHY = ['stag', 'bird', 'fox', 'rabbit', 'mouse']

# =========================================================================
# --- 1. JINJA2 FILTER SETUP ---
# =========================================================================
env = Environment(loader=FileSystemLoader('templates'))

def smart_date_filter(d1, d2=None):
    if not d1: 
        return ""
    try:
        dt1 = datetime.strptime(str(d1), '%Y-%m-%d')
        if not d2 or d1 == d2:
            return dt1.strftime('%b %d, %Y')
        
        dt2 = datetime.strptime(str(d2), '%Y-%m-%d')
        if dt1.year != dt2.year:
            return f"{dt1.strftime('%b %d, %Y')} — {dt2.strftime('%b %d, %Y')}"
        return f"{dt1.strftime('%b %d')} — {dt2.strftime('%b %d, %Y')}"
    except ValueError:
        return str(d1)

env.filters['smart_date'] = smart_date_filter

# =========================================================================
# --- 2. UTILITIES & HELPERS ---
# =========================================================================
def get_clean_name(name):
    if not name: 
        return ""
    return str(name).split('+')[0].split('#')[0].strip()

def get_tier_name(rating, games):
    if games < 10: 
        return "unranked"  
    r = round(rating)
    for threshold, tier in TIER_THRESHOLDS:
        if r >= threshold: 
            return tier
    return "squirrel"

def prepare_leaderboard_data(df):
    if df.empty: 
        return []
    return [{
        'Rank': row['Rank'],
        'tier': get_tier_name(row['ELO'], row['Games']),
        'display_name': get_clean_name(row['Player']),
        'ELO': int(row['ELO']),
        'Games': row['Games'],
        'Wins': row['Wins'],
        'Win_Rate': row['Win Rate'],
        'Peak': row['Peak'],
        'Last': row['Last']
    } for _, row in df.iterrows()]

def prepare_matches_data(matches_list):
    return [{
        'rank': m.get('Rank'),
        'elo_sum': m.get('ELO_Sum'),
        'date': m.get('Date'),
        'players': sorted([
            {**p, 'name': get_clean_name(p['name'])} for p in m.get('players', [])
        ], key=lambda x: x['is_winner'], reverse=True),
        'match_id': m.get('MatchID'),
        'match_url': f"https://rootleague.pliskin.dev/match/{m.get('MatchID')}/"
    } for m in matches_list]

def prepare_trends_data(history_dict):
    if not history_dict:
        return {"history_json": "{}", "player_names": []}
    return {
        "history_json": json.dumps(history_dict),
        "player_names": sorted(list(history_dict.keys()))
    }
    
def get_elo_for_match(player_name, game_id, full_history):
    clean_p = get_clean_name(player_name)
    history = full_history.get(clean_p, [])
    
    for i, entry in enumerate(history):
        if entry[2] == game_id:
            return entry[1] if i == 0 else history[i-1][1]
    return None

def extract_relations(matches_list, full_history):
    all_players = {get_clean_name(p['name']) for m in matches_list for p in m['players']}
    
    relations = {p: {
        "trophy": {"name": None, "elo": -1, "tier": "unranked"}, 
        "bane": {"name": None, "elo": 99999, "tier": "unranked"},
        "unique_opponents": 0
    } for p in all_players}
    
    opponents_track = {p: set() for p in all_players}
            
    for m in matches_list:
        match_id = m['MatchID']
        p_names = [get_clean_name(p['name']) for p in m['players']]
        
        for p_name in p_names:
            for opp_name in p_names:
                if p_name != opp_name:
                    opponents_track[p_name].add(opp_name)
                    
        winners = [p for p in m['players'] if p['is_winner']]
        losers = [p for p in m['players'] if not p['is_winner']]

        for w in winners:
            w_clean = get_clean_name(w['name'])
            for l in losers:
                l_clean = get_clean_name(l['name'])
                l_elo = get_elo_for_match(l_clean, match_id, full_history)
                if l_elo is not None and l_elo > relations[w_clean]['trophy']['elo']:
                    relations[w_clean]['trophy'] = {
                        "name": l_clean, "elo": int(round(l_elo)), "tier": get_tier_name(l_elo, 10)
                    }

        for l in losers:
            l_clean = get_clean_name(l['name'])
            for w in winners:
                w_clean = get_clean_name(w['name'])
                w_elo = get_elo_for_match(w_clean, match_id, full_history)
                if w_elo is not None and w_elo < relations[l_clean]['bane']['elo']:
                    relations[l_clean]['bane'] = {
                        "name": w_clean, "elo": int(round(w_elo)), "tier": get_tier_name(w_elo, 10)
                    }
    
    for p in all_players:
        relations[p]["unique_opponents"] = len(opponents_track[p])
        
    return relations

def prepare_archive_relations(raw_relations):
    prepared = {}
    for p_raw, data in raw_relations.items():
        p_clean = get_clean_name(p_raw)
        t_name = data["trophy"]["name"]
        t_elo = data["trophy"]["elo"]
        b_name = data["bane"]["name"]
        b_elo = data["bane"]["elo"]
        
        prepared[p_clean] = {
            "unique_opponents": data.get("unique_opponents", 0),
            "trophy": {
                "name": get_clean_name(t_name) if t_name else None,
                "elo": t_elo,
                "tier": get_tier_name(t_elo, 10) if t_elo != -1 else "unranked"
            },
            "bane": {
                "name": get_clean_name(b_name) if b_name else None,
                "elo": b_elo,
                "tier": get_tier_name(b_elo, 10) if b_elo != 99999 else "unranked"
            }
        }
    return prepared

def render_page(template_name, output_name, **kwargs):
    template = env.get_template(template_name)
    full_vars = {
        "nav_items": NAV_ITEMS,
        "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        **kwargs
    }
    with open(output_name, "w", encoding="utf-8") as f:
        f.write(template.render(**full_vars))
    print(f"  > {output_name} generated.")

# =========================================================================
# --- 3. DATA LOADERS ---
# =========================================================================
game_id_mapping = pd.Series(dtype='datetime64[ns]')
if os.path.exists(CORRECTIONS_FILE):
    try:
        df_updates = pd.read_csv(CORRECTIONS_FILE, parse_dates=['New_Date'])
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"✅ Loaded corrections from {CORRECTIONS_FILE}")
    except Exception as e:
        print(f"ℹ️ Note: Error loading corrections: {e}")

archives_raw_data = {}
elo_ratings = {} 

for tag in ARCHIVE_SEASONS:
    print(f"📂 Loading archive: {tag.upper()}")
    archives_raw_data[tag] = {
        'final_df': pd.DataFrame(), 'matches_list': [], 'history': {},
        'metadata': {"cutoff_date": "N/A", "match_count": 0}, 'relations': {}
    }
    
    for filename, key in [("_metadata.json", "metadata"), ("_relations.json", "relations")]:
        path = os.path.join(DATA_DIR, f"{tag}{filename}")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                archives_raw_data[tag][key] = json.load(f)
    try:
        path_ratings = os.path.join(DATA_DIR, f"{tag}_ratings.csv")
        if os.path.exists(path_ratings):
            df_ratings = pd.read_csv(path_ratings)
            for _, row in df_ratings.iterrows():
                elo_ratings[str(row['Player'])] = float(row.get('ELO', 1200.0))
            df_ratings['ELO'] = df_ratings['ELO'].round().astype(int)
            if 'Tier' not in df_ratings.columns: 
                df_ratings['Tier'] = None
            archives_raw_data[tag]['final_df'] = df_ratings
        
        path_matches = os.path.join(DATA_DIR, f"{tag}_matches.json")
        if os.path.exists(path_matches):
            with open(path_matches, "r", encoding="utf-8") as f:
                archives_raw_data[tag]['matches_list'] = json.load(f)
        
        path_trends = os.path.join(DATA_DIR, f"{tag}_history.json")
        if os.path.exists(path_trends):
            with open(path_trends, "r", encoding="utf-8") as f:
                history = json.load(f)
                archives_raw_data[tag]['history'] = {get_clean_name(k): v for k, v in history.items()}
                
        print(f"  ✅ Archive {tag.upper()} loaded successfully.")
    except Exception as e:
        print(f"  ⚠️ Error loading archive {tag.upper()}: {e}")
        
archived_player_names = set(elo_ratings.keys())

# =========================================================================
# --- 4. API FETCHING (CURRENT SEASON) ---
# =========================================================================
all_matches = []
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
today = date.today()
CUTOFF_DATE = today - timedelta(days=1)
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

print(f"🌐 Requesting data for Tournament {TOURNAMENT_ID}... Filtering before: {today}")
while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        if res.status_code == 400:
            print(f"ℹ️ Tournament {TOURNAMENT_ID} not yet active on API.")
            break
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except requests.RequestException as e:
        print(f"📡 API Note: {e}")
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
# --- 5. ELO ENGINE ---
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
    label = f"{ARCHIVE_SEASONS[-1].upper()} Final" if ARCHIVE_SEASONS and p in archived_player_names else "Start"
    player_history[p] = [[label, round(r), None]]

if not df.empty:
    for game_id, group in df.groupby('GameID', sort=False):
        match_participants = group.to_dict('records')
        current_match_sum = round(sum([elo_ratings[p['Player']] for p in match_participants]))
        current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
        
        q_scores = {p['Player']: 10 ** (elo_ratings[p['Player']] / 400) for p in match_participants}
        total_q = sum(q_scores.values())
        
        deltas_this_match = {}
        for p in match_participants:
            name = p['Player']
            actual = p['Score']
            expected = q_scores[name] / total_q
            
            player_stats[name]['games'] += 1
            player_stats[name]['wins'] += actual
            
            g_count = player_stats[name]['games']
            k = 80 if g_count <= 10 else (40 if g_count <= 50 else 20)
            change = k * (actual - expected)
            
            elo_ratings[name] += change
            last_diff[name] = change
            deltas_this_match[name] = round(change)
            
            if elo_ratings[name] > peak_elo[name]: 
                peak_elo[name] = elo_ratings[name]
                
            player_history[name].append([current_date, round(elo_ratings[name]), int(game_id)])

        players_list = [{
            'name': get_clean_name(p['Player']),
            'delta': int(deltas_this_match[p['Player']]),
            'is_winner': bool(p['Score'] >= 0.5)
        } for p in match_participants]

        match_history_data.append({
            'MatchID': game_id, 'Date': current_date, 'players': players_list, 'ELO_Sum': current_match_sum
        })

current_matches_df = pd.DataFrame(match_history_data)
if not current_matches_df.empty:
    current_matches_df = current_matches_df.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
    current_matches_df.insert(0, 'Rank', range(1, len(current_matches_df) + 1))
    
current_history = {get_clean_name(k): v for k, v in player_history.items()}
current_relations = extract_relations(match_history_data, current_history)
    
# =========================================================================
# --- 6. LEADERBOARD GENERATION ---
# =========================================================================
leaderboard_list = []
for p_name, rating in elo_ratings.items():
    s = player_stats.get(p_name, {'wins': 0, 'games': 0})
    display_elo = round(rating)
    diff = round(last_diff.get(p_name, 0))
    is_qual = (s['games'] >= 10 and display_elo >= 1200)
    
    leaderboard_list.append({
        'Player': p_name, 'ELO': rating, 'Display_ELO': display_elo, 'Games': s['games'], 'Wins': s['wins'], 
        'Win Rate': f"{(s['wins']/s['games']):.1%}" if s['games'] > 0 else "0.0%",
        'Peak': round(peak_elo.get(p_name, rating)), 'Last': f"+{diff}" if diff > 0 else str(diff), 'Qualified': is_qual
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
    current_final_df['ELO'] = current_final_df['Display_ELO']
    current_final_df = current_final_df.drop(columns=['Display_ELO'])
else:
    current_final_df = pd.DataFrame(columns=['Rank', 'Player', 'ELO', 'Games', 'Wins', 'Win Rate', 'Peak', 'Last', 'Qualified'])

# =========================================================================
# --- 7. ASSET PREPARATION ---
# =========================================================================
print("\n=== PREPARING SITE ASSETS ===")
print("  > Processing current season data...")

current_meta = {
    'match_count': df['GameID'].nunique() if not df.empty else 0, 'cutoff_date': CUTOFF_DATE.strftime('%Y-%m-%d')
}
display_leaderboard_current = []
if not current_final_df.empty:
    display_leaderboard_current = prepare_leaderboard_data(current_final_df[current_final_df['Games'] > 0])

display_matches_current = []
if not current_matches_df.empty:
    display_matches_current = prepare_matches_data(current_matches_df.to_dict('records'))

display_trends_current = prepare_trends_data(current_history)

print("  > Processing historical archive data...")
display_archives = {}
for tag in ARCHIVE_SEASONS:
    raw = archives_raw_data[tag]
    lb_data = prepare_leaderboard_data(raw['final_df'][raw['final_df']['Games'] > 0]) if not raw['final_df'].empty else []
    display_archives[tag] = {
        'leaderboard': lb_data, 'matches': prepare_matches_data(raw['matches_list']), 'trends': prepare_trends_data(raw['history'])
    }

# =========================================================================
# --- 8. HALL OF FAME (STREAKS CODES) ---
# =========================================================================
print("  > Compiling historical tier streaks...")

def extract_all_streaks(history, player_full_name):
    streaks = []
    if len(history) < 11: 
        return streaks
    short_name = get_clean_name(player_full_name)
    current_s = None

    for i in range(10, len(history)):
        date_str, elo_val = history[i][0], history[i][1]
        if "-" not in str(date_str): 
            continue
        tier_now = get_tier_name(elo_val, 11)
        if tier_now not in TIER_HIERARCHY: 
            tier_now = None

        if tier_now != (current_s['tier'] if current_s else None):
            if current_s: 
                streaks.append(current_s)
            if tier_now:
                current_s = {
                    'player': short_name, 'tier': tier_now, 'start_date': date_str,
                    'end_date': date_str, 'peak': elo_val, 'streak_count': 1
                }
            else:
                current_s = None
        elif current_s:
            current_s['streak_count'] += 1
            current_s['end_date'] = date_str
            current_s['peak'] = max(current_s['peak'], elo_val)

    if current_s: 
        streaks.append(current_s)
    return streaks

best_streaks_only = {}
sources = [(row['Player'], player_history.get(row['Player'], [])) for _, row in current_final_df.iterrows()] if not current_final_df.empty else []

for tag in ARCHIVE_SEASONS:
    for p_name, h in archives_raw_data.get(tag, {}).get('history', {}).items():
        sources.append((p_name, h))

for p_name, h in sources:
    for s in extract_all_streaks(h, p_name):
        key = (s['player'], s['tier'])
        if key not in best_streaks_only:
            best_streaks_only[key] = s
        else:
            curr = best_streaks_only[key]
            if (s['streak_count'] > curr['streak_count']) or (s['streak_count'] == curr['streak_count'] and s['peak'] > curr['peak']):
                best_streaks_only[key] = s

all_sorted_streaks = sorted(
    best_streaks_only.values(), 
    key=lambda x: (TIER_HIERARCHY.index(x['tier']) if x['tier'] in TIER_HIERARCHY else 99, -x['streak_count'], -x['peak'])
)

hall_of_fame_data = []
for t in TIER_HIERARCHY:
    tier_top_5 = [s for s in all_sorted_streaks if s['tier'] == t][:5]
    if tier_top_5:
        hall_of_fame_data.append({'is_section': True, 'tier': t})
        for rank, s in enumerate(tier_top_5, 1):
            s.update({'is_section': False, 'rank_display': ["", "I", "II", "III", "IV", "V"][rank]})
            hall_of_fame_data.append(s)
    
# =========================================================================
# --- 9. WEB RENDERING ---
# =========================================================================
print("\n=== GENERATING HTML PAGES ===")

def render_core_pages(file_suffix, is_archive, tag, lb_data, match_data, trends_data, meta, relations_data=None):
    
    # 1. Leaderboard
    render_page(
        "leaderboard.html", f"index{file_suffix}.html", page_id="index", current_page_base="index",
        title=PAGES["index"]["title"], 
        page_heading=PAGES["index"]["page_heading"],
        description=PAGES["index"]["description"].format(
            match_count=meta.get('match_count', 0), 
            cutoff_date=meta.get('cutoff_date', 'N/A')
        ),
        is_archive=is_archive, has_seasons=True, season_tag=tag,
        archive_seasons=ARCHIVE_SEASONS,
        current_season_tag=CURRENT_SEASON_TAG,
        num_matches=meta.get('match_count', 0),
        cutoff_date=meta.get('cutoff_date', 'N/A'),
        players=lb_data
    )

    # 2. Matches
    render_page(
        "matches.html", f"matches{file_suffix}.html", page_id="matches",
        title=PAGES["matches"]["title"], 
        page_heading=PAGES["matches"]["page_heading"],
        description=PAGES["matches"]["description"].format(
            match_count=meta.get('match_count', 0), 
            cutoff_date=meta.get('cutoff_date', 'N/A')
        ),
        is_archive=is_archive, has_seasons=True, season_tag=tag,
        archive_seasons=ARCHIVE_SEASONS,
        current_season_tag=CURRENT_SEASON_TAG,
        matches=match_data
    )

    # 3. Trends
    render_page(
        "trends.html", f"trends{file_suffix}.html", page_id="trends",
        title=PAGES["trends"]["title"], 
        page_heading=PAGES["trends"]["page_heading"],
        description=PAGES["trends"]["description"],
        is_archive=is_archive, has_seasons=True, season_tag=tag,
        archive_seasons=ARCHIVE_SEASONS,
        current_season_tag=CURRENT_SEASON_TAG,
        history_json=trends_data['history_json'], player_names=trends_data['player_names'],
        relations_json=json.dumps(relations_data) if relations_data else "{}"
    )

# --- Render Current Season & Archives ---
render_core_pages("", False, CURRENT_SEASON_TAG, display_leaderboard_current, display_matches_current, display_trends_current, current_meta, current_relations)

for tag in ARCHIVE_SEASONS:
    archive_relations_clean = prepare_archive_relations(archives_raw_data[tag].get('relations', {}))
    
    render_core_pages(f"_{tag}", True, tag, display_archives[tag]['leaderboard'], display_archives[tag]['matches'], display_archives[tag]['trends'], archives_raw_data[tag]['metadata'], archive_relations_clean)

# --- Render Static Pages ---
render_page(
    "about.html", "about.html", page_id="about", is_archive=False, has_seasons=False,
    title=PAGES["about"]["title"], 
    page_heading=PAGES["about"]["page_heading"], 
    description=PAGES["about"]["description"]
)

render_page(
    "cache.html", "cache.html", page_id="cache", is_archive=False, has_seasons=False,
    title=PAGES["cache"]["title"], 
    page_heading=PAGES["cache"]["page_heading"], 
    description=PAGES["cache"]["description"], 
    hall_of_fame=hall_of_fame_data
)

print("✨ Website generated successfully!")
