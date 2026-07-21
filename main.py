import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from jinja2 import Environment, FileSystemLoader
import pandas as pd
import requests

# =========================================================================
# --- 0. CONFIGURATION & CONSTANTS ---
# =========================================================================
DATA_DIR = "data"
CONFIG_DIR = os.path.join(DATA_DIR, "config")
ARCHIVES_DIR = os.path.join(DATA_DIR, "archives")

ARCHIVE_SEASONS = ["lh01", "lh02"]
CURRENT_SEASON_TAG = "lh03"
TOURNAMENT_ID = 26
BASE_URL = "https://tricholome.github.io/rootelo"
PLISKIN_BASE_URL = "https://rootleague.pliskin.dev"

TIER_THRESHOLDS = [
    (1600, "stag"),
    (1500, "bird"),
    (1400, "fox"),
    (1300, "rabbit"),
    (1200, "mouse")
]
TIER_HIERARCHY = ['stag', 'bird', 'fox', 'rabbit', 'mouse']

NAV_ITEMS = [
    {'id': 'index', 'url': 'index.html', 'label': 'Leaderboard'},
    {'id': 'matches', 'url': 'matches.html', 'label': 'Top Tables'},
    {'id': 'trends', 'url': 'trends.html', 'label': "Player's Journey"},
    {'id': 'about', 'url': 'about.html', 'label': 'Codex'}
]

# =========================================================================
# --- 1. FILE & I/O HELPERS ---
# =========================================================================
def load_json(filepath, default=None):
    """Safely loads a JSON file with a fallback default value."""
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {filepath}: {e}")
    return default

def save_json(filepath, data, indent=2):
    """Saves data to a JSON file, creating target directories if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

# =========================================================================
# --- 2. PLAYER MAPPING & TIER UTILITIES ---
# =========================================================================
class PlayerRegistry:
    """Handles cleaning and unique mapping for player names."""
    def __init__(self):
        self.player_map = {}

    def initialize(self, all_raw_names):
        base_names = [str(n).split('+')[0].split('#')[0].strip() for n in all_raw_names if n]
        counts = Counter(base_names)
        
        for name in all_raw_names:
            if not name:
                continue
            name_str = str(name)
            base = name_str.split('+')[0].split('#')[0].strip()
            
            if counts[base] > 1:
                tag = ""
                if '#' in name_str:
                    tag = name_str.split('#')[-1].strip()
                elif '+' in name_str:
                    tag = name_str.split('+')[-1].strip()
                self.player_map[name] = f"{base} ({tag})" if tag else base
            else:
                self.player_map[name] = base

    def get_clean_name(self, name):
        if not name:
            return ""
        if name in self.player_map:
            return self.player_map[name]
        return str(name).split('+')[0].split('#')[0].strip()

# Global registry instance
player_registry = PlayerRegistry()

def get_tier_name(rating, games):
    if games < 10:
        return "unranked"
    r = round(rating)
    for threshold, tier in TIER_THRESHOLDS:
        if r >= threshold:
            return tier
    return "squirrel"

# =========================================================================
# --- 3. JINJA2 ENVIRONMENT SETUP ---
# =========================================================================
def setup_jinja_env(config):
    env = Environment(loader=FileSystemLoader('templates'))
    env.globals['config'] = config

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
    return env

# =========================================================================
# --- 4. DATA PREPARATION HELPERS ---
# =========================================================================
def prepare_leaderboard_data(df, champion_name=None, is_archive=False):
    if df.empty:
        return []
    
    data = []
    clean_champ = player_registry.get_clean_name(champion_name) if champion_name else None
    
    for _, row in df.iterrows():
        clean_name = player_registry.get_clean_name(row['Player'])
        is_champ = (clean_champ is not None and clean_name == clean_champ)
        rank_display = "♔" if (is_champ and is_archive) else row['Rank']
        tier = "bear" if is_champ else get_tier_name(row['ELO'], row['Games'])
        
        data.append({
            'Rank': rank_display,
            'tier': tier,
            'is_champion': is_champ,
            'display_name': clean_name,
            'ELO': int(row['ELO']),
            'Games': row['Games'],
            'Wins': row['Wins'],
            'Win_Rate': row['Win Rate'],
            'Peak': row['Peak'],
            'Last': row['Last']
        })
    
    if clean_champ and is_archive:
        data.sort(key=lambda x: not x['is_champion'])
            
    return data

def prepare_matches_data(matches_list):
    return [{
        'rank': m.get('Rank'),
        'elo_sum': m.get('ELO_Sum'),
        'date': m.get('Date'),
        'players': sorted([
            {**p, 'name': player_registry.get_clean_name(p['name'])} for p in m.get('players', [])
        ], key=lambda x: x['is_winner'], reverse=True),
        'match_id': m.get('MatchID'),
        'match_url': f"{PLISKIN_BASE_URL}/match/{m.get('MatchID')}/"
    } for m in matches_list]

def prepare_trends_data(history_dict):
    if not history_dict:
        return {"history_json": "{}", "player_names": []}
    
    enriched_history = {}
    for player_raw, rows in history_dict.items():
        clean_rows = []
        for row in rows:
            match_id = row[2] if len(row) > 2 else None
            url = f"{PLISKIN_BASE_URL}/match/{match_id}/" if match_id else None
            clean_rows.append([row[0], row[1], match_id, url])
            
        enriched_history[player_registry.get_clean_name(player_raw)] = clean_rows
    
    player_names = sorted(list(enriched_history.keys()), key=lambda x: x.lower())
    return {
        "history_json": json.dumps(enriched_history),
        "player_names": player_names
    }

# =========================================================================
# --- 5. ELO & RELATIONS ENGINE ---
# =========================================================================
def get_elo_for_match(player_name, game_id, full_history):
    clean_p = player_registry.get_clean_name(player_name)
    history = full_history.get(clean_p, [])
    
    for i, entry in enumerate(history):
        if entry[2] == game_id:
            return entry[1] if i == 0 else history[i-1][1]
    return None

def extract_relations(matches_list, full_history):
    all_players = {player_registry.get_clean_name(p['name']) for m in matches_list for p in m['players']}
    
    relations = {p: {
        "trophy": {"name": None, "elo": -1, "tier": "unranked"}, 
        "bane": {"name": None, "elo": 99999, "tier": "unranked"},
        "unique_opponents": 0
    } for p in all_players}
    
    opponents_track = {p: set() for p in all_players}
            
    for m in matches_list:
        match_id = m['MatchID']
        p_names = [player_registry.get_clean_name(p['name']) for p in m['players']]
        
        for p_name in p_names:
            for opp_name in p_names:
                if p_name != opp_name:
                    opponents_track[p_name].add(opp_name)
                    
        winners = [p for p in m['players'] if p['is_winner']]
        losers = [p for p in m['players'] if not p['is_winner']]

        for w in winners:
            w_clean = player_registry.get_clean_name(w['name'])
            for l in losers:
                l_clean = player_registry.get_clean_name(l['name'])
                l_elo = get_elo_for_match(l_clean, match_id, full_history)
                if l_elo is not None and l_elo > relations[w_clean]['trophy']['elo']:
                    relations[w_clean]['trophy'] = {
                        "name": l_clean, "elo": int(round(l_elo)), "tier": get_tier_name(l_elo, 10)
                    }

        for l in losers:
            l_clean = player_registry.get_clean_name(l['name'])
            for w in winners:
                w_clean = player_registry.get_clean_name(w['name'])
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
        p_clean = player_registry.get_clean_name(p_raw)
        t_name = data["trophy"]["name"]
        t_elo = data["trophy"]["elo"]
        b_name = data["bane"]["name"]
        b_elo = data["bane"]["elo"]
        
        prepared[p_clean] = {
            "unique_opponents": data.get("unique_opponents", 0),
            "trophy": {
                "name": player_registry.get_clean_name(t_name) if t_name else None,
                "elo": t_elo,
                "tier": get_tier_name(t_elo, 10) if t_elo != -1 else "unranked"
            },
            "bane": {
                "name": player_registry.get_clean_name(b_name) if b_name else None,
                "elo": b_elo,
                "tier": get_tier_name(b_elo, 10) if b_elo != 99999 else "unranked"
            }
        }
    return prepared

# =========================================================================
# --- 6. HALL OF FAME ENGINE ---
# =========================================================================
def extract_all_streaks(history, player_full_name):
    streaks = []
    if len(history) < 11:
        return streaks
    short_name = player_registry.get_clean_name(player_full_name)
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

def build_hall_of_fame(sources):
    best_streaks_only = {}
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
    return hall_of_fame_data

# =========================================================================
# --- 7. MAIN PIPELINE ---
# =========================================================================
def main():
    print("🚀 Initializing Rootelo generation pipeline...")
    
    # --- Load Configurations & Content (from data/config/) ---
    config = load_json(os.path.join(CONFIG_DIR, "config.json"))
    pages_content = load_json(os.path.join(CONFIG_DIR, "pages_content.json"))
    champions_data = load_json(os.path.join(CONFIG_DIR, "champions.json"))
    
    corrections_file = os.path.join(CONFIG_DIR, "corrections.csv")
    game_id_mapping = pd.Series(dtype='datetime64[ns]')
    if os.path.exists(corrections_file):
        try:
            df_updates = pd.read_csv(corrections_file, parse_dates=['New_Date'])
            if not df_updates.empty and 'GameID' in df_updates.columns:
                game_id_mapping = df_updates.set_index('GameID')['New_Date']
                print(f"✅ Loaded corrections from {corrections_file}")
        except Exception as e:
            print(f"ℹ️ Note: Error loading corrections: {e}")

    env = setup_jinja_env(config)

    # --- Load Historical Archives (from data/archives/{tag}/) ---
    archives_raw_data = {}
    elo_ratings = {}

    for tag in ARCHIVE_SEASONS:
        print(f"📂 Loading archive: {tag.upper()}")
        season_archive_dir = os.path.join(ARCHIVES_DIR, tag)
        archives_raw_data[tag] = {
            'final_df': pd.DataFrame(), 'matches_list': [], 'history': {},
            'metadata': {"cutoff_date": "N/A", "match_count": 0}, 'relations': {}
        }
        
        archives_raw_data[tag]['metadata'] = load_json(os.path.join(season_archive_dir, "metadata.json"), archives_raw_data[tag]['metadata'])
        archives_raw_data[tag]['relations'] = load_json(os.path.join(season_archive_dir, "relations.json"), archives_raw_data[tag]['relations'])
        archives_raw_data[tag]['matches_list'] = load_json(os.path.join(season_archive_dir, "matches.json"), [])
        archives_raw_data[tag]['history'] = load_json(os.path.join(season_archive_dir, "history.json"), {})

        path_ratings = os.path.join(season_archive_dir, "ratings.csv")
        if os.path.exists(path_ratings):
            df_ratings = pd.read_csv(path_ratings)
            for _, row in df_ratings.iterrows():
                elo_ratings[str(row['Player'])] = float(row.get('ELO', 1200.0))
            df_ratings['ELO'] = df_ratings['ELO'].round().astype(int)
            if 'Tier' not in df_ratings.columns:
                df_ratings['Tier'] = None
            archives_raw_data[tag]['final_df'] = df_ratings

    archived_player_names = set(elo_ratings.keys())

    # --- Fetch Current Season API Data ---
    all_matches = []
    api_token = os.getenv('API_TOKEN')
    headers = {'Authorization': f'Token {api_token}'} if api_token else {}
    today = date.today()
    cutoff_date = today - timedelta(days=1)
    
    endpoint = f"{PLISKIN_BASE_URL.rstrip('/')}/api/match/"
    params = {
        'tournament': TOURNAMENT_ID,
        'limit': 500
    }

    print(f"🌐 Requesting data for Tournament {TOURNAMENT_ID}... Filtering matches before: {today}")
    next_url = endpoint
    while next_url:
        try:
            res = requests.get(next_url, headers=headers, params=params)
            params = None  # Clear params for pagination pages as DRF includes them in 'next'
            if res.status_code == 400:
                print(f"ℹ️ Tournament {TOURNAMENT_ID} is not active on API yet.")
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

        df = df[df['Date_Closed'].dt.date <= cutoff_date].copy()
        df = df.sort_values(by='Date_Closed').reset_index(drop=True)

    # --- Player Registry Initialization ---
    all_raw_names = set()
    if not df.empty:
        all_raw_names.update(df['Player'].unique())
    for tag in ARCHIVE_SEASONS:
        archive_df = archives_raw_data[tag]['final_df']
        if not archive_df.empty and 'Player' in archive_df.columns:
            all_raw_names.update(archive_df['Player'].unique())
        if archives_raw_data[tag]['history']:
            all_raw_names.update(archives_raw_data[tag]['history'].keys())

    player_registry.initialize(all_raw_names)

    global_players_list = sorted(list({player_registry.get_clean_name(name) for name in all_raw_names if name}))
    player_dwd_map = {player_registry.get_clean_name(n): str(n).strip().replace('+', '-') for n in all_raw_names if n}

    for tag in ARCHIVE_SEASONS:
        if archives_raw_data[tag]['history']:
            raw_hist = archives_raw_data[tag]['history']
            archives_raw_data[tag]['history'] = {player_registry.get_clean_name(k): v for k, v in raw_hist.items()}

    # --- Current Season ELO Calculation ---
    current_final_df = pd.DataFrame()
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
                'name': player_registry.get_clean_name(p['Player']),
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
        
    current_history = {player_registry.get_clean_name(k): v for k, v in player_history.items()}
    current_relations = extract_relations(match_history_data, current_history)

    # Leaderboard Construction
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

    # --- Site Asset Preparation ---
    print("\n=== PREPARING SITE ASSETS ===")
    current_meta = {
        'match_count': df['GameID'].nunique() if not df.empty else 0,
        'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
    }
    
    reigning_champ = champions_data.get(ARCHIVE_SEASONS[-1], {}).get('champion') if ARCHIVE_SEASONS else None

    display_leaderboard_current = prepare_leaderboard_data(
        current_final_df[current_final_df['Games'] > 0], 
        champion_name=reigning_champ
    ) if not current_final_df.empty else []
    
    display_matches_current = prepare_matches_data(current_matches_df.to_dict('records')) if not current_matches_df.empty else []
    display_trends_current = prepare_trends_data(current_history)

    display_archives = {}
    for tag in ARCHIVE_SEASONS:
        raw = archives_raw_data[tag]
        season_champ = champions_data.get(tag, {}).get('champion')
        lb_data = prepare_leaderboard_data(
            raw['final_df'][raw['final_df']['Games'] > 0], 
            champion_name=season_champ, 
            is_archive=True
        ) if not raw['final_df'].empty else []
        
        display_archives[tag] = {
            'leaderboard': lb_data, 
            'matches': prepare_matches_data(raw['matches_list']), 
            'trends': prepare_trends_data(raw['history'])
        }

    # --- Hall of Fame Compilation ---
    sources = [(row['Player'], player_history.get(row['Player'], [])) for _, row in current_final_df.iterrows()] if not current_final_df.empty else []
    for tag in ARCHIVE_SEASONS:
        for p_name, h in archives_raw_data.get(tag, {}).get('history', {}).items():
            sources.append((p_name, h))
            
    hall_of_fame_data = build_hall_of_fame(sources)

    # --- HTML Page Rendering ---
    print("\n=== GENERATING HTML PAGES ===")

    def render_page(template_name, output_name, **kwargs):
        template = env.get_template(template_name)
        full_vars = {
            "nav_items": NAV_ITEMS,
            "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            "global_players": global_players_list,
            "player_dwd_map_json": json.dumps(player_dwd_map),
            **kwargs
        }
        with open(output_name, "w", encoding="utf-8") as f:
            f.write(template.render(**full_vars))
        print(f"  > {output_name} generated.")

    def render_season_pages(tag, is_archive, lb_data, match_data, trends_data, meta, relations_data=None, champ_match=None, suffix=""):
        season_context = {
            "is_archive": is_archive,
            "has_seasons": True,
            "season_tag": tag,
            "archive_seasons": ARCHIVE_SEASONS,
            "current_season_tag": CURRENT_SEASON_TAG,
            "cutoff_date": meta.get('cutoff_date', 'N/A'),
        }

        # 1. Leaderboard (Index)
        render_page(
            "index.html", f"index{suffix}.html",
            page_id="index",
            players=lb_data,
            champ_match=champ_match,
            match_count=meta.get('match_count', 0),
            **pages_content.get("index", {}),
            **season_context
        )

        # 2. Matches
        render_page(
            "matches.html", f"matches{suffix}.html",
            page_id="matches",
            matches=match_data,
            match_count=meta.get('match_count', 0),
            **pages_content.get("matches", {}),
            **season_context
        )

        # 3. Trends
        render_page(
            "trends.html", f"trends{suffix}.html",
            page_id="trends",
            history_json=trends_data['history_json'],
            player_names=trends_data['player_names'],
            relations_json=json.dumps(relations_data or {}),
            **pages_content.get("trends", {}),
            **season_context
        )

    # Render Current Season
    render_season_pages(
        CURRENT_SEASON_TAG, False, 
        display_leaderboard_current, display_matches_current, display_trends_current, 
        current_meta, current_relations,
        champ_match=champions_data.get(ARCHIVE_SEASONS[-1]) if ARCHIVE_SEASONS else None
    )

    # Render Historical Archives
    for tag in ARCHIVE_SEASONS:
        archive_relations_clean = prepare_archive_relations(archives_raw_data[tag].get('relations', {}))
        render_season_pages(
            tag, True, 
            display_archives[tag]['leaderboard'], display_archives[tag]['matches'], display_archives[tag]['trends'], 
            archives_raw_data[tag]['metadata'], archive_relations_clean, 
            champ_match=champions_data.get(tag), suffix=f"_{tag}"
        )

    # Render Static Pages (About, Undergrowth/Cache)
    for page_id, tmpl in [("about", "about.html"), ("cache", "cache.html")]:
        p_info = pages_content.get(page_id, {})
        extra = {"hall_of_fame": hall_of_fame_data} if page_id == "cache" else {}
        render_page(
            tmpl, f"{page_id}.html", page_id=page_id, is_archive=False, has_seasons=False,
            title=p_info.get("title", ""), page_heading=p_info.get("page_heading", ""), description=p_info.get("description", ""), **extra
        )

    # --- API JSON Generation ---
    print("\n=== GENERATING API JSON ===")
    tier_colors = config.get('colors', {}).get('tiers', {})
    tier_icons = config.get('assets', {}).get('icons', {})

    api_data = {
        "updated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "players": {}
    }

    reigning_champ = champions_data.get(ARCHIVE_SEASONS[-1], {}).get('champion') if ARCHIVE_SEASONS else None
    for item in prepare_leaderboard_data(current_final_df, champion_name=reigning_champ):
        clean_name = item['display_name']
        raw_dwd = player_dwd_map.get(clean_name, clean_name)
        dwd_key = str(raw_dwd).replace('#', '-').lower().strip()
        
        tier = item['tier']
        color = tier_colors.get(tier)
        icon_path = tier_icons.get(tier)

        api_data["players"][dwd_key] = {
            "elo": item['ELO'], "rank": item['Rank'], "tier": tier, "bg_color": color,
            "icon_url": f"{BASE_URL}/{icon_path}" if icon_path else None,
            "games": item['Games'], "wins": item['Wins'], "win_rate": item['Win_Rate']
        }

    save_json("api/live_elo.json", api_data)
    print("  > api/live_elo.json generated successfully!")
    print("\n✨ Website and API generated successfully!")

if __name__ == "__main__":
    main()
