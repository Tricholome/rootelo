import argparse
import json
import os
import time
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from jinja2 import Environment, FileSystemLoader
import pandas as pd
import requests
import re

# =========================================================================
# --- 0. GLOBAL CONSTANTS & LOGGING ---
# =========================================================================

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

DISCORD_EPOCH = 1420070400000

class Logger:
    @staticmethod
    def header(title):
        print(f"\n==================================================")
        print(f"  {title}")
        print(f"==================================================")

    @staticmethod
    def section(title):
        print(f"\n--- [{title}] ---")

    @staticmethod
    def info(msg):
        print(f"  ℹ️  {msg}")

    @staticmethod
    def success(msg):
        print(f"  ✅ {msg}")

    @staticmethod
    def warn(msg):
        print(f"  ⚠️  {msg}")

    @staticmethod
    def step(step_name, duration=None):
        if duration is not None:
            print(f"  > {step_name} ({duration:.2f}s)")
        else:
            print(f"  > {step_name}")


# =========================================================================
# --- 1. CORE UTILITIES & HELPERS ---
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
            Logger.warn(f"Error reading {filepath}: {e}")
    return default


def save_json(filepath, data, indent=2):
    """Saves data to a JSON file, creating target directories if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_all_league_configs():
    """Dynamically discovers and loads all league configurations from data/<league_slug>/league.json."""
    configs = {}
    data_dir = "data"

    if not os.path.exists(data_dir):
        Logger.warn("Data directory does not exist.")
        return configs

    for entry in os.listdir(data_dir):
        entry_path = os.path.join(data_dir, entry)
        if os.path.isdir(entry_path) and entry != "config" and not entry.startswith("."):
            config_file = os.path.join(entry_path, "league.json")
            if os.path.exists(config_file):
                cfg = load_json(config_file)
                if cfg.get("enabled", True):
                    slug = cfg.get("slug", entry)
                    cfg["slug"] = slug
                    configs[slug] = cfg
            else:
                alt_config_file = os.path.join(entry_path, "config.json")
                if os.path.exists(alt_config_file):
                    cfg = load_json(alt_config_file)
                    if cfg.get("enabled", True):
                        slug = cfg.get("slug", entry)
                        cfg["slug"] = slug
                        configs[slug] = cfg

    return configs


class PlayerRegistry:
    """Handles cleaning and unique mapping for player names."""
    def __init__(self):
        self.player_map = {}

    def initialize(self, all_raw_names, name_overrides=None):
        if name_overrides is None:
            name_overrides = {}

        base_names = []
        for n in all_raw_names:
            if not n:
                continue
            name_str = str(n)
            base = name_overrides.get(name_str) or name_str.split('+')[0].split('#')[0].strip()
            base_names.append(base)

        counts = Counter(base_names)

        for name in all_raw_names:
            if not name:
                continue
            name_str = str(name)
            base = name_overrides.get(name_str) or name_str.split('+')[0].split('#')[0].strip()

            if counts[base] > 1 and name not in name_overrides:
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


def get_tier_name(rating, games):
    if games < 10:
        return "unassigned"
    r = round(rating)
    for threshold, tier in TIER_THRESHOLDS:
        if r >= threshold:
            return tier
    return "squirrel"


def calculate_k_factor(games_count, last_date, current_date, k_config, is_ranked=False):
    """Calculates K-factor dynamically using standardized parameters defined in league.json."""
    k_floor = float(k_config.get("k_floor", 20.0))
    k_start = float(k_config.get("k_start", 50.0))
    exp_decay = float(k_config.get("exp_decay", 10.0))
    k_cap = float(k_config.get("k_cap_ranked" if is_ranked else "k_cap_new", 50.0))   
    k_base = k_floor + (k_start - k_floor) * math.exp(-games_count / exp_decay)
    v_time = 1.0
    t_inactivity = k_config.get("t_inactivity")
    if t_inactivity and last_date and current_date:
        days_inactive = (current_date - last_date).days
        if days_inactive > 0:
            v_time = 1.0 + 1.0 * (1.0 - math.exp(-days_inactive / float(t_inactivity)))

    return min(k_cap, k_base * v_time)

def setup_jinja_env(config):
    env = Environment(loader=FileSystemLoader(['templates', '.']))
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

def get_discord_created_at(table_talk_url):
    """Extracts exact creation timestamp using the Snowflake ID from the Discord URL."""
    if not table_talk_url:
        return None

    url_str = str(table_talk_url).strip()
    
    match = re.search(r'/channels/\d+/(\d+)', url_str)
    
    if not match:
        match = re.search(r'/(\d+)/?$', url_str)

    if match:
        snowflake_id = int(match.group(1))
        timestamp_ms = (snowflake_id >> 22) + DISCORD_EPOCH
        return pd.to_datetime(timestamp_ms, unit='ms', utc=True)

    return None


def format_match_timing(turn_timing, created_at, closed_at):
    """Formats timing order, type ('Live'/'Async'), and optional duration."""
    if not turn_timing or str(turn_timing).lower() == 'live':
        return 0, "Live", None

    if not created_at or not closed_at or created_at == closed_at:
        return 99999999, "Async", None

    delta = pd.to_datetime(closed_at) - pd.to_datetime(created_at)
    seconds = max(1, int(delta.total_seconds()))
    days = delta.days

    if days == 0:
        hours = max(1, seconds // 3600)
        duration = f"{hours} hour" if hours == 1 else f"{hours} hours"
    else:
        duration = f"{days} day" if days == 1 else f"{days} days"

    return seconds, "Async", duration

# =========================================================================
# --- 2. API FETCHING & DATA INGESTION ---
# =========================================================================

def fetch_raw_matches(league_config, max_retries=3, retry_delay=5, timeout=15):
    """Fetches and normalizes raw match data using the specified league API configuration."""
    api_cfg = league_config.get('api', {})
    league_name = league_config.get('name', 'Unknown League')

    token_var = api_cfg.get('token_env_var')
    token = os.getenv(token_var) if token_var else None
    auth_prefix = api_cfg.get('auth_prefix', 'Token')
    headers = {'Authorization': f'{auth_prefix} {token}'} if token else {}

    base_url = api_cfg.get('base_url', '').rstrip('/')
    endpoint = api_cfg.get('endpoint') or f"{base_url}/api/match/"

    params = {'limit': 500}
    if 'tournament_id' in api_cfg:
        params['tournament'] = api_cfg['tournament_id']

    next_url, all_matches = endpoint, []
    while next_url:
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                res = requests.get(next_url, headers=headers, params=params, timeout=timeout)
                params = None

                if res.status_code == 400:
                    Logger.info(f"API returned 400 for {league_name} (league may not be active yet).")
                    next_url = None
                    success = True
                    break

                res.raise_for_status()
                data = res.json()
                all_matches.extend(data.get('results', []))
                next_url = data.get('next')
                success = True
                break
            except requests.RequestException as e:
                Logger.warn(f"API Error ({league_name}) - Attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)

        if not success and next_url:
            raise RuntimeError(
                f"API unavailable for league '{league_name}' after {max_retries} attempts. Aborting pipeline."
            )

    raw_data = []
    for m in all_matches:
        participants = m.get('participants', [])
        if len(participants) == 4:
            table_talk = m.get('table_talk_url')
            created_at = get_discord_created_at(table_talk) if table_talk else None

            for p in participants:
                match_row = {
                    'GameID': m['id'],
                    'Player': p.get('player'),
                    'Player_Name': p.get('player_name'),
                    'Score': float(p.get('tournament_score', 0.0)),
                    'Date_Closed': m.get('date_closed'),
                }
                if created_at:
                    match_row['Date_Created'] = created_at
                if 'turn_timing' in m:
                    match_row['Turn_Timing'] = m.get('turn_timing')

                raw_data.append(match_row)

    unique_matches_count = len({m['GameID'] for m in raw_data})
    Logger.step(f"{unique_matches_count} matches retrieved from API.")
    return raw_data


def get_match_url(match_id, league_config):
    """Builds the detail match URL for the specified league."""
    if not match_id:
        return None
    base_url = league_config['match_base_url'].rstrip('/')
    return f"{base_url}/{match_id}/"


# =========================================================================
# --- 3. ENGINE & DATA TRANSFORMATIONS ---
# =========================================================================

# --- ELO & Relations Engine ---

def get_elo_for_match(player_name, game_id, full_history, player_registry):
    clean_p = player_registry.get_clean_name(player_name)
    history = full_history.get(clean_p, [])

    for i, entry in enumerate(history):
        if entry[2] == game_id:
            return entry[1] if i == 0 else history[i-1][1]
    return None


def extract_relations(matches_list, full_history, player_registry):
    all_players = {player_registry.get_clean_name(p['name']) for m in matches_list for p in m['players']}

    relations = {p: {
        "trophy": {"name": None, "elo": -1, "tier": "unassigned"},
        "bane": {"name": None, "elo": 99999, "tier": "unassigned"},
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
                l_elo = get_elo_for_match(l_clean, match_id, full_history, player_registry)
                if l_elo is not None and l_elo > relations[w_clean]['trophy']['elo']:
                    relations[w_clean]['trophy'] = {
                        "name": l_clean, "elo": int(round(l_elo)), "tier": get_tier_name(l_elo, 10)
                    }

        for l in losers:
            l_clean = player_registry.get_clean_name(l['name'])
            for w in winners:
                w_clean = player_registry.get_clean_name(w['name'])
                w_elo = get_elo_for_match(w_clean, match_id, full_history, player_registry)
                if w_elo is not None and w_elo < relations[l_clean]['bane']['elo']:
                    relations[l_clean]['bane'] = {
                        "name": w_clean, "elo": int(round(w_elo)), "tier": get_tier_name(w_elo, 10)
                    }

    for p in all_players:
        relations[p]["unique_opponents"] = len(opponents_track[p])

    return relations


def prepare_archive_relations(raw_relations, player_registry):
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
                "tier": get_tier_name(t_elo, 10) if t_elo != -1 else "unassigned"
            },
            "bane": {
                "name": player_registry.get_clean_name(b_name) if b_name else None,
                "elo": b_elo,
                "tier": get_tier_name(b_elo, 10) if b_elo != 99999 else "unassigned"
            }
        }
    return prepared


# --- Hall of Fame Engine ---

def extract_all_streaks(history, player_full_name, player_registry):
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


def build_hall_of_fame(sources, player_registry):
    best_streaks_only = {}
    for p_name, h in sources:
        for s in extract_all_streaks(h, p_name, player_registry):
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


# --- Page Formatting Helpers ---

def prepare_leaderboard_data(df, player_registry, champion_name=None, is_archive=False):
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
            'ELO': int(round(row['ELO'])),
            'Games': row['Games'],
            'Wins': row['Wins'],
            'Win_Rate': row['Win Rate'],
            'Peak': row['Peak'],
            'Last': row['Last']
        })

    if clean_champ and is_archive:
        data.sort(key=lambda x: not x['is_champion'])

    return data


def prepare_matches_data(matches_list, player_registry, league_config):
    formatted = []
    for m in matches_list:
        order, timing_type, duration = format_match_timing(
            m.get('Turn_Timing'),
            m.get('Date_Created'),
            m.get('Date_Closed'),
        )
        formatted.append({
            'rank': m.get('Rank'),
            'elo_sum': m.get('ELO_Sum'),
            'date': m.get('Date'),
            'timing_order': order,
            'timing_type': timing_type,
            'timing_duration': duration,
            'players': sorted(
                [
                    {
                        **p,
                        'name': player_registry.get_clean_name(p['name']),
                    }
                    for p in m.get('players', [])
                ],
                key=lambda x: x['is_winner'],
                reverse=True,
            ),
            'match_id': m.get('MatchID'),
            'match_url': get_match_url(m.get('MatchID'), league_config),
        })
    return formatted


def prepare_trends_data(history_dict, player_registry, league_config):
    if not history_dict:
        return {"history_json": "{}", "player_names": []}

    enriched_history = {}
    for player_raw, rows in history_dict.items():
        clean_rows = []
        for row in rows:
            match_id = row[2] if len(row) > 2 else None
            url = get_match_url(match_id, league_config)
            clean_rows.append([row[0], row[1], match_id, url])

        enriched_history[player_registry.get_clean_name(player_raw)] = clean_rows

    player_names = sorted(list(enriched_history.keys()), key=lambda x: x.lower())
    return {
        "history_json": json.dumps(enriched_history),
        "player_names": player_names
    }


# =========================================================================
# --- 4. SINGLE LEAGUE PIPELINE ---
# =========================================================================

def run_league_pipeline(league_config, all_leagues_list):
    start_time = time.time()
    slug = league_config['slug']
    name = league_config['name']
    output_dir = league_config['output_dir']
    current_season_tag = league_config['current_season_tag']
    api_output_path = f"api/{slug}/elo.json"
    profile_base_url = league_config['profile_base_url']
    format_replace_chars = league_config.get('profile_format_replace_chars', False)

    Logger.header(f"ROOTELO PIPELINE: {name.upper()} ({slug})")

    Logger.section("1. CONFIGURATION & HISTORICAL DATA")
    data_dir = os.path.join("data", slug)
    archives_dir = os.path.join(data_dir, "archives")

    archive_seasons = sorted([
        d for d in os.listdir(archives_dir)
        if os.path.isdir(os.path.join(archives_dir, d)) and d != current_season_tag
    ]) if os.path.exists(archives_dir) else []
    Logger.info(f"Detected archived seasons ({len(archive_seasons)}): {', '.join(archive_seasons) if archive_seasons else 'None'}")

    player_registry = PlayerRegistry()

    # Load Global & League Configurations
    config = load_json(os.path.join("data", "config", "config.json"))
    pages_content = load_json(os.path.join("data", "config", "pages_content.json"))

    champions_data = load_json(os.path.join(data_dir, "champions.json"))
    corrections_file = os.path.join(data_dir, "corrections.csv")

    closed_date_mapping = pd.Series(dtype='object')
    created_date_mapping = pd.Series(dtype='object')

    if os.path.exists(corrections_file):
        try:
            df_updates = pd.read_csv(corrections_file)
            if not df_updates.empty and 'GameID' in df_updates.columns:
                if 'Date_Closed' in df_updates.columns:
                    df_closed = df_updates.dropna(subset=['Date_Closed'])
                    closed_date_mapping = df_closed.set_index('GameID')['Date_Closed']
                if 'Date_Created' in df_updates.columns:
                    df_created = df_updates.dropna(subset=['Date_Created'])
                    created_date_mapping = df_created.set_index('GameID')['Date_Created']
                
                Logger.success(f"Loaded manual date corrections from {corrections_file}")
        except Exception as e:
            Logger.warn(f"Error loading corrections: {e}")

    env = setup_jinja_env(config)

    # Load Historical Archives
    archives_raw_data = {}
    elo_ratings = {}

    for tag in archive_seasons:
        season_archive_dir = os.path.join(archives_dir, tag)
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

        m_count = len(archives_raw_data[tag]['matches_list'])
        p_count = len(archives_raw_data[tag]['final_df']) if not archives_raw_data[tag]['final_df'].empty else len(archives_raw_data[tag]['history'])
        Logger.step(f"Archive [{tag.upper()}]: {m_count} matches, {p_count} players loaded")

    archived_player_names = set(elo_ratings.keys())
    if archive_seasons:
        total_archived_matches = sum(len(a['matches_list']) for a in archives_raw_data.values())
        Logger.success(f"Total archives: {total_archived_matches} cumulative matches across {len(archive_seasons)} season(s), {len(archived_player_names)} players tracked")

    # Fetch Current Season API Data
    Logger.section("2. MATCH FETCHING & DATE FILTERING")
    today = date.today()
    cutoff_date = today - timedelta(days=1)

    Logger.info(f"Fetching API data for {name}... Filtering matches before: {today}")
    raw_data = fetch_raw_matches(league_config)

    df = pd.DataFrame(raw_data)
    if not df.empty:
        df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)
        if 'Date_Created' in df.columns:
            df['Date_Created'] = pd.to_datetime(df['Date_Created'], utc=True)

        if not closed_date_mapping.empty:
            closed_date_mapping.index = closed_date_mapping.index.astype(int)
            mask_closed = df['GameID'].isin(closed_date_mapping.index)
            if mask_closed.any():
                df.loc[mask_closed, 'Date_Closed'] = pd.to_datetime(
                    df.loc[mask_closed, 'GameID'].map(closed_date_mapping), utc=True
                )

        if not created_date_mapping.empty:
            created_date_mapping.index = created_date_mapping.index.astype(int)
            mask_created = df['GameID'].isin(created_date_mapping.index)
            if mask_created.any():
                df.loc[mask_created, 'Date_Created'] = pd.to_datetime(
                    df.loc[mask_created, 'GameID'].map(created_date_mapping), utc=True
                )

        df = df[df['Date_Closed'].dt.date <= cutoff_date].copy()
        df = df.sort_values(by='Date_Closed').reset_index(drop=True)

    # Player Registry Initialization
    name_overrides = {
        item['Player']: item['Player_Name']
        for item in raw_data
        if item.get('Player') and item.get('Player_Name')
    }

    all_raw_names = set()
    if not df.empty:
        all_raw_names.update(df['Player'].unique())
    for tag in archive_seasons:
        archive_df = archives_raw_data[tag]['final_df']
        if not archive_df.empty and 'Player' in archive_df.columns:
            all_raw_names.update(archive_df['Player'].unique())
        if archives_raw_data[tag]['history']:
            all_raw_names.update(archives_raw_data[tag]['history'].keys())

    player_registry.initialize(all_raw_names, name_overrides=name_overrides)
    global_players_list = sorted(list({player_registry.get_clean_name(name) for name in all_raw_names if name}))
    Logger.success(f"Player registry initialized ({len(global_players_list)} unique player names)")

    # Ranked Players Extraction                   
    last_season_ranked_players = set()
    if archive_seasons:
        last_tag = archive_seasons[-1]
        last_df = archives_raw_data[last_tag]['final_df']
        if not last_df.empty and 'Rank' in last_df.columns:
            for _, row in last_df.iterrows():
                rank_val = str(row.get('Rank', '')).strip()
                if rank_val and rank_val not in ('-', 'nan', 'None'):
                    clean_p = player_registry.get_clean_name(row['Player'])
                    last_season_ranked_players.add(clean_p)
    Logger.info(f"Ranked players from last archive season ({archive_seasons[-1] if archive_seasons else 'None'}): {len(last_season_ranked_players)}")                                 
    # Player Profile Mapping
    if format_replace_chars:
        player_profile_map = {
            player_registry.get_clean_name(n): str(n).strip().replace('+', '-').replace('#', '-')
            for n in all_raw_names if n
        }
    else:
        player_profile_map = {
            player_registry.get_clean_name(n): str(n).strip()
            for n in all_raw_names if n
        }

    for tag in archive_seasons:
        if archives_raw_data[tag]['history']:
            raw_hist = archives_raw_data[tag]['history']
            archives_raw_data[tag]['history'] = {player_registry.get_clean_name(k): v for k, v in raw_hist.items()}

    # Current Season ELO Calculation
    Logger.section("3. ELO COMPUTATION & RELATIONS EXTRACTION")
    current_final_df = pd.DataFrame()
    match_history_data = []

    if not df.empty:
        for player in df['Player'].unique():
            if player not in elo_ratings:
                elo_ratings[player] = 1200.0

    peak_elo = {p: r for p, r in elo_ratings.items()}
    last_diff = {p: 0.0 for p in elo_ratings}
    player_stats = {p: {'games': 0, 'wins': 0.0, 'last_date': None} for p in elo_ratings}
    player_history = {}

    for p, r in elo_ratings.items():
        label = f"{archive_seasons[-1].upper()} Final" if archive_seasons and p in archived_player_names else "Start"
        player_history[p] = [[label, round(r), None]]
        
    k_config = league_config.get('k_factor', {})

    if not df.empty:
        for game_id, group in df.groupby('GameID', sort=False):
            match_participants = group.to_dict('records')
            current_match_sum = round(sum([elo_ratings[p['Player']] for p in match_participants]))
            
            current_dt = pd.to_datetime(match_participants[0]['Date_Closed'])
            current_date = current_dt.strftime('%Y-%m-%d')

            q_scores = {p['Player']: 10 ** (elo_ratings[p['Player']] / 400) for p in match_participants}
            total_q = sum(q_scores.values())

            deltas_this_match = {}
            for p in match_participants:
                name = p['Player']
                clean_name = player_registry.get_clean_name(name)                                               
                actual = p['Score']
                expected = q_scores[name] / total_q

                g_count = player_stats[name]['games']
                last_dt = player_stats[name]['last_date']
                is_ranked = clean_name in last_season_ranked_players                                                   
                k = calculate_k_factor(g_count, last_dt, current_dt, k_config, is_ranked=is_ranked)
                change = k * (actual - expected)

                elo_ratings[name] += change
                last_diff[name] = change
                deltas_this_match[name] = round(change)

                if elo_ratings[name] > peak_elo[name]:
                    peak_elo[name] = elo_ratings[name]

                player_stats[name]['games'] += 1
                player_stats[name]['wins'] += actual
                player_stats[name]['last_date'] = current_dt

                player_history[name].append([current_date, round(elo_ratings[name]), int(game_id)])

            players_list = [{
                'name': player_registry.get_clean_name(p['Player']),
                'delta': int(deltas_this_match[p['Player']]),
                'is_winner': bool(p['Score'] >= 0.5)
            } for p in match_participants]

            match_history_data.append({
                'MatchID': game_id,
                'Date': current_date,
                'Date_Closed': match_participants[0].get('Date_Closed'),
                'Date_Created': match_participants[0].get('Date_Created'),
                'Turn_Timing': match_participants[0].get('Turn_Timing'),
                'players': players_list,
                'ELO_Sum': current_match_sum,
            })

    current_matches_df = pd.DataFrame(match_history_data)
    if not current_matches_df.empty:
        current_matches_df = current_matches_df.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
        current_matches_df.insert(0, 'Rank', range(1, len(current_matches_df) + 1))

    current_history = {player_registry.get_clean_name(k): v for k, v in player_history.items()}
    current_relations = extract_relations(match_history_data, current_history, player_registry)

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

    qual_count = len(current_final_df[current_final_df['Qualified'] == True]) if not current_final_df.empty else 0
    active_count = len(current_final_df[current_final_df['Games'] > 0]) if not current_final_df.empty else 0
    Logger.success(f"Elo computation complete: {len(current_final_df)} total players tracked ({active_count} active this season, {qual_count} qualified on leaderboard)")

    # Site Asset Preparation
    current_meta = {
        'match_count': df['GameID'].nunique() if not df.empty else 0,
        'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
    }

    reigning_champ = champions_data.get(archive_seasons[-1], {}).get('champion') if archive_seasons else None

    display_leaderboard_current = prepare_leaderboard_data(
        current_final_df[current_final_df['Games'] > 0],
        player_registry,
        champion_name=reigning_champ
    ) if not current_final_df.empty else []

    display_matches_current = prepare_matches_data(current_matches_df.to_dict('records'), player_registry, league_config) if not current_matches_df.empty else []
    display_trends_current = prepare_trends_data(current_history, player_registry, league_config)

    display_archives = {}
    for tag in archive_seasons:
        raw = archives_raw_data[tag]
        season_champ = champions_data.get(tag, {}).get('champion')
        lb_data = prepare_leaderboard_data(
            raw['final_df'][raw['final_df']['Games'] > 0],
            player_registry,
            champion_name=season_champ,
            is_archive=True
        ) if not raw['final_df'].empty else []

        display_archives[tag] = {
            'leaderboard': lb_data,
            'matches': prepare_matches_data(raw['matches_list'], player_registry, league_config),
            'trends': prepare_trends_data(raw['history'], player_registry, league_config)
        }

    # Hall of Fame Compilation
    sources = [(row['Player'], player_history.get(row['Player'], [])) for _, row in current_final_df.iterrows()] if not current_final_df.empty else []
    for tag in archive_seasons:
        for p_name, h in archives_raw_data.get(tag, {}).get('history', {}).items():
            sources.append((p_name, h))

    hall_of_fame_data = build_hall_of_fame(sources, player_registry)

    # HTML Page Rendering
    Logger.section("4. HTML RENDERING")
    
    player_data_map_json = json.dumps({
        player_registry.get_clean_name(p): {
            'elo': round(r),
            'games': player_stats.get(p, {}).get('games', 0),
            'is_ranked': player_registry.get_clean_name(p) in last_season_ranked_players
        }
        for p, r in elo_ratings.items()
    })

    def render_page(template_name, output_name, **kwargs):
        template = env.get_template(template_name)
        
        prefix = "../" if (output_dir and output_dir not in ('.', '')) else ""
        
        page_id = kwargs.get("page_id")
        section_id = kwargs.get("section_id", page_id)

        full_vars = {
            "nav_items": NAV_ITEMS,
            "section_id": section_id,
            "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            "global_players": global_players_list,
            "player_profile_map_json": json.dumps(player_profile_map),
            "player_data_map_json": player_data_map_json,
            "profile_base_url": profile_base_url,
            "current_league": slug,
            "league_config": league_config,
            "all_leagues": all_leagues_list,
            "path_prefix": prefix,
            "is_static": False,
            **kwargs
        }

        target_path = os.path.join(output_dir, output_name) if output_dir not in ('.', '') else output_name
        if output_dir not in ('.', '') and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(template.render(**full_vars))
        Logger.step(f"Page generated: {target_path}")

    def render_season_pages(tag, is_archive, lb_data, match_data, trends_data, meta, relations_data=None, champ_match=None, suffix=""):
        season_context = {
            "is_archive": is_archive,
            "has_seasons": bool(archive_seasons),
            "season_tag": tag,
            "archive_seasons": archive_seasons,
            "current_season_tag": current_season_tag,
            "cutoff_date": meta.get('cutoff_date', 'N/A'),
        }

        render_page(
            "index.html", f"index{suffix}.html",
            page_id="index",
            players=lb_data,
            champ_match=champ_match,
            match_count=meta.get('match_count', 0),
            **pages_content.get("index", {}),
            **season_context
        )

        render_page(
            "matches.html", f"matches{suffix}.html",
            page_id="matches",
            matches=match_data,
            match_count=meta.get('match_count', 0),
            **pages_content.get("matches", {}),
            **season_context
        )

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
        current_season_tag, False,
        display_leaderboard_current, display_matches_current, display_trends_current,
        current_meta, current_relations,
        champ_match=champions_data.get(archive_seasons[-1]) if archive_seasons else None
    )

    # Render Historical Archives
    for tag in archive_seasons:
        archive_relations_clean = prepare_archive_relations(archives_raw_data[tag].get('relations', {}), player_registry)
        render_season_pages(
            tag, True,
            display_archives[tag]['leaderboard'], display_archives[tag]['matches'], display_archives[tag]['trends'],
            archives_raw_data[tag]['metadata'], archive_relations_clean,
            champ_match=champions_data.get(tag), suffix=f"_{tag}"
        )

    # Render Static Pages (About, Simulator, Cache)
    static_pages = [
        ("about", "about.html", "codex"),
        ("league", "league.html", "codex"),
        ("simulator", "simulator.html", "codex"),
        ("cache", "cache.html", "cache")
    ]
    for page_id, tmpl, section_id in static_pages:
        p_info = pages_content.get(section_id, {})
        extra = {"hall_of_fame": hall_of_fame_data} if page_id == "cache" else {}

        render_page(
            tmpl, f"{page_id}.html",
            page_id=page_id,
            section_id=section_id,
            is_archive=False,
            has_seasons=False,
            is_static=True,
            title=p_info.get("title", ""), 
            page_heading=p_info.get("page_heading", ""), 
            description=p_info.get("description", ""), 
            **extra
        )

    # API JSON Generation
    Logger.section("5. REST JSON API EXPORT")
    site_base_url = config.get('site_base_url', '').rstrip('/')
    tier_colors = config.get('colors', {}).get('tiers', {})
    tier_icons = config.get('assets', {}).get('icons', {})

    api_data = {
        "updated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "players": {}
    }

    full_api_leaderboard = prepare_leaderboard_data(current_final_df, player_registry, champion_name=reigning_champ) if not current_final_df.empty else []

    for item in full_api_leaderboard:
        clean_name = item['display_name']
        raw_identifier = player_profile_map.get(clean_name, clean_name)
        player_key = str(raw_identifier).replace('#', '-').lower().strip()

        tier = item['tier']
        color = tier_colors.get(tier)
        icon_path = tier_icons.get(tier)

        api_data["players"][player_key] = {
            "elo": item['ELO'], "rank": item['Rank'], "tier": tier, "bg_color": color,
            "icon_url": f"{site_base_url}/{icon_path.lstrip('/')}" if icon_path else None,
            "games": item['Games'], "wins": item['Wins'], "win_rate": item['Win_Rate']
        }

    save_json(api_output_path, api_data)
    Logger.success(f"API endpoint exported: {api_output_path} ({len(api_data['players'])} player records)")

    elapsed = time.time() - start_time
    Logger.header(f"PIPELINE {slug.upper()} FINISHED IN {elapsed:.2f}s")


# =========================================================================
# --- 5. CLI ENTRYPOINT ---
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Rootelo Multi-League Engine")
    parser.add_argument('--league', help="Choose specific league (e.g. 'rdl', 'hoot')")
    parser.add_argument('--all', action='store_true', help="Process all registered and enabled leagues")
    args = parser.parse_args()

    all_league_configs = load_all_league_configs()
    all_leagues_list = list(all_league_configs.values())

    if not all_league_configs:
        Logger.warn("Error: No valid league configuration files found in data/*/")
        return

    if args.all or args.league == 'all':
        Logger.info(f"Executing full build for all leagues ({len(all_leagues_list)} total)...")
        for cfg in all_leagues_list:
            run_league_pipeline(cfg, all_leagues_list)
    else:
        target_slug = args.league if args.league else 'rdl'
        if target_slug not in all_league_configs:
            Logger.warn(f"Error: League '{target_slug}' not found in data/{target_slug}/league.json")
            return
        run_league_pipeline(all_league_configs[target_slug], all_leagues_list)


if __name__ == "__main__":
    main()
