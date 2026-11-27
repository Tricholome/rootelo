import json
import math
import os
import re
import time
import pandas as pd
import requests


# =========================================================================
# --- 1. CONSTANTS & LOGGING ---
# =========================================================================

TIER_THRESHOLDS = [
    (1600, "stag"),
    (1500, "bird"),
    (1400, "fox"),
    (1300, "rabbit"),
    (1200, "mouse")
]
TIER_HIERARCHY = ['stag', 'bird', 'fox', 'rabbit', 'mouse']

DISCORD_EPOCH = 1420070400000


class Logger:
    @staticmethod
    def header(title):
        print("\n==================================================")
        print(f"  {title}")
        print("==================================================")

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
# --- 2. JSON I/O & LEAGUE CONFIGURATION ---
# =========================================================================

def load_json(filepath, default=None):
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
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_league_config(league_slug):
    data_dir = os.path.join("data", league_slug)
    config_file = os.path.join(data_dir, "league.json")
    if not os.path.exists(config_file):
        config_file = os.path.join(data_dir, "config.json")

    if os.path.exists(config_file):
        cfg = load_json(config_file)
        cfg["slug"] = cfg.get("slug", league_slug)
        return cfg
    raise FileNotFoundError(f"League config file not found for '{league_slug}' in {data_dir}")


def load_all_league_configs():
    configs = {}
    data_dir = "data"

    if not os.path.exists(data_dir):
        Logger.warn("Data directory does not exist.")
        return configs

    for entry in os.listdir(data_dir):
        entry_path = os.path.join(data_dir, entry)
        if os.path.isdir(entry_path) and entry != "config" and not entry.startswith("."):
            config_file = os.path.join(entry_path, "league.json")
            if not os.path.exists(config_file):
                config_file = os.path.join(entry_path, "config.json")
            if os.path.exists(config_file):
                cfg = load_json(config_file)
                if cfg.get("enabled", True):
                    slug = cfg.get("slug", entry)
                    cfg["slug"] = slug
                    configs[slug] = cfg

    sorted_items = sorted(
        configs.items(),
        key=lambda item: (
            0 if item[1].get("is_default") else 1,
            item[1].get("order", 99),
            item[0],
        ),
    )
    return dict(sorted_items)


# =========================================================================
# --- 3. PLAYER REGISTRY & HELPERS ---
# =========================================================================

class PlayerRegistry:
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.raw_map = load_json(filepath, {}) if filepath else {}

    def register(self, player_id, raw_name, display_name=None):
        if player_id is None:
            return
        slug = str(raw_name).strip() if raw_name else ""
        name = str(display_name).strip() if display_name else slug
        if not slug and not name:
            return
        if name and slug and name != slug:
            self.raw_map[str(player_id)] = {"slug": slug, "name": name}
        else:
            self.raw_map[str(player_id)] = slug or name

    def save(self):
        if self.filepath:
            save_json(self.filepath, self.raw_map)

    def get_raw_name(self, player_id):
        if player_id is None:
            return ""
        pid = str(player_id)
        entry = self.raw_map.get(pid, pid)
        if isinstance(entry, dict):
            return entry.get("slug") or entry.get("name") or pid
        return entry

    def get_clean_name(self, player_id):
        if player_id is None:
            return ""
        pid = str(player_id)
        entry = self.raw_map.get(pid, pid)
        if isinstance(entry, dict):
            return entry.get("name") or entry.get("slug") or pid
        return str(entry).split('+')[0].split('#')[0].strip()

    def get_profile_slug(self, player_id, replace_chars=False):
        raw = self.get_raw_name(player_id)
        if replace_chars:
            return raw.replace('+', '-').replace('#', '-')
        return raw

def get_tier_name(rating):
    r = round(rating)
    for threshold, tier in TIER_THRESHOLDS:
        if r >= threshold:
            return tier
    return "squirrel"


def calculate_k_factor(games_count, last_date, current_date, k_config, is_ranked=False, is_legacy=False):
    if is_legacy:
        if games_count < 10:
            return 80.0
        if games_count < 50:
            return 40.0
        return 20.0

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


def get_discord_created_at(table_talk_url):
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


def get_match_url(match_id, league_config):
    if not match_id:
        return None
    base_url = league_config['match_base_url'].rstrip('/')
    return f"{base_url}/{match_id}/"


# =========================================================================
# --- 4. API FETCHING, CORRECTIONS & ARCHIVES ---
# =========================================================================

_RAW_MATCHES_CACHE = {}

def fetch_raw_matches(
    league_config,
    tournament_id=None,
    is_legacy=False,
    max_retries=3,
    retry_delay=5,
    timeout=15,
    abort_on_error=True,
):
    api_cfg = league_config.get('api', {})
    league_name = league_config.get('name', 'Unknown League')

    token_var = api_cfg.get('token_env_var')
    token = os.getenv(token_var) if token_var else None
    auth_prefix = api_cfg.get('auth_prefix', 'Token')
    headers = {'Authorization': f'{auth_prefix} {token}'} if token else {}

    base_url = api_cfg.get('base_url', '').rstrip('/')
    endpoint = api_cfg.get('endpoint') or (f"{base_url}/api/match/" if base_url else "")

    t_id = tournament_id or api_cfg.get('tournament_id')
    cache_key = (endpoint, t_id, is_legacy)
    if endpoint and cache_key in _RAW_MATCHES_CACHE:
        Logger.step(f"Reusing cached API matches for {league_name}.")
        return _RAW_MATCHES_CACHE[cache_key]
    params = {'limit': 500}
    if t_id:
        params['tournament'] = t_id

    next_url, all_matches = endpoint, []
    while next_url:
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                res = requests.get(next_url, headers=headers, params=params, timeout=timeout)
                params = None

                if res.status_code == 400:
                    Logger.info(f"API returned 400 for {league_name} (league/tournament may not be active yet).")
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
            if abort_on_error:
                raise RuntimeError(
                    f"API unavailable for league '{league_name}' after {max_retries} attempts. Aborting pipeline."
                )
            break

    raw_data = []
    for m in all_matches:
        participants = m.get('participants', [])
        if len(participants) == 4:
            table_talk = m.get('table_talk_url')
            created_at = None if is_legacy else (get_discord_created_at(table_talk) if table_talk else None)

            for p in participants:
                pid = str(p.get('player_id') or p.get('player'))
                raw_name = p.get('player') or pid
                display_name = p.get('player_name') or raw_name

                match_row = {
                    'GameID': m['id'],
                    'PlayerID': pid,
                    'Raw_Name': raw_name,
                    'Display_Name': display_name,
                    'Score': float(p.get('tournament_score', 0.0)),
                    'Date_Closed': m.get('date_closed'),
                }
                if created_at is not None:
                    match_row['Date_Created'] = created_at
                if 'turn_timing' in m:
                    match_row['Turn_Timing'] = m.get('turn_timing')
                raw_turn = p.get('turn_order')
                if raw_turn is not None:
                    try:
                        match_row['Turn_Order'] = int(raw_turn)
                    except (TypeError, ValueError):
                        pass

                raw_data.append(match_row)

    unique_matches_count = len({m['GameID'] for m in raw_data})
    Logger.step(f"{unique_matches_count} matches retrieved from API.")
    if endpoint:
        _RAW_MATCHES_CACHE[cache_key] = raw_data
    return raw_data


def prepare_matches_dataframe(raw_data, cutoff_date, corrections_path=None, is_legacy=False):
    df = pd.DataFrame(raw_data)
    if df.empty:
        return df

    df['PlayerID'] = df['PlayerID'].astype(str)
    df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)
    if 'Date_Created' in df.columns and not is_legacy:
        df['Date_Created'] = pd.to_datetime(df['Date_Created'], utc=True)

    if corrections_path and os.path.exists(corrections_path):
        try:
            df_corr = pd.read_csv(corrections_path)
            if not df_corr.empty and 'GameID' in df_corr.columns:
                df_corr['GameID'] = df_corr['GameID'].astype(int)

                if 'Date_Closed' in df_corr.columns:
                    closed_map = df_corr.dropna(subset=['Date_Closed']).set_index('GameID')['Date_Closed']
                    mask_closed = df['GameID'].isin(closed_map.index)
                    if mask_closed.any():
                        original_times = df.loc[mask_closed, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
                        new_dates = pd.to_datetime(df.loc[mask_closed, 'GameID'].map(closed_map)).dt.strftime('%Y-%m-%d')
                        df.loc[mask_closed, 'Date_Closed'] = pd.to_datetime(new_dates + ' ' + original_times, utc=True)

                if not is_legacy and 'Date_Created' in df_corr.columns:
                    created_map = df_corr.dropna(subset=['Date_Created']).set_index('GameID')['Date_Created']
                    mask_created = df['GameID'].isin(created_map.index)
                    if mask_created.any():
                        df.loc[mask_created, 'Date_Created'] = pd.to_datetime(
                            df.loc[mask_created, 'GameID'].map(created_map), utc=True
                        )

                Logger.success(f"Applied manual date corrections from {corrections_path}")
        except Exception as e:
            Logger.warn(f"Error loading corrections from {corrections_path}: {e}")

    df = df[df['Date_Closed'].dt.date <= cutoff_date].copy()
    df = df.sort_values(by=['Date_Closed', 'GameID', 'PlayerID'], kind='mergesort').reset_index(drop=True)
    return df


def load_archives(data_dir, current_season_tag, min_games):
    archives_dir = os.path.join(data_dir, "archives")
    archive_seasons = sorted([
        d for d in os.listdir(archives_dir)
        if os.path.isdir(os.path.join(archives_dir, d)) and d != current_season_tag
    ]) if os.path.exists(archives_dir) else []

    Logger.info(
        f"Detected archived seasons ({len(archive_seasons)}): "
        f"{', '.join(archive_seasons) if archive_seasons else 'None'}"
    )

    archives_raw_data = {}
    elo_ratings = {}

    for tag in archive_seasons:
        season_archive_dir = os.path.join(archives_dir, tag)
        path_ratings = os.path.join(season_archive_dir, "ratings.csv")
        df_ratings = pd.DataFrame()

        if os.path.exists(path_ratings):
            df_ratings = pd.read_csv(path_ratings, dtype={'Last': str})
            id_col = 'PlayerID' if 'PlayerID' in df_ratings.columns else 'Player'
            if id_col in df_ratings.columns and 'ELO' in df_ratings.columns:
                df_ratings[id_col] = df_ratings[id_col].astype(str)
                elo_ratings.update(
                    dict(zip(df_ratings[id_col], df_ratings['ELO'].fillna(1200.0).astype(float)))
                )
                df_ratings['ELO'] = df_ratings['ELO'].round().astype(int)
            if 'Tier' not in df_ratings.columns:
                df_ratings['Tier'] = df_ratings.apply(
                    lambda r: get_tier_name(r['ELO']) if r['Games'] >= min_games else "unassigned",
                    axis=1
                )

        matches_list = load_json(os.path.join(season_archive_dir, "matches.json"), [])
        history = {str(k): v for k, v in load_json(os.path.join(season_archive_dir, "history.json"), {}).items()}
        net_data = load_json(os.path.join(season_archive_dir, "network.json"), {})

        archives_raw_data[tag] = {
            'final_df': df_ratings,
            'matches_list': matches_list,
            'history': history,
            'metadata': load_json(
                os.path.join(season_archive_dir, "metadata.json"),
                {"cutoff_date": "N/A", "match_count": 0}
            ),
            'relations': load_json(os.path.join(season_archive_dir, "relations.json"), {}),
            'homelands_snapshots': net_data.get("snapshots", {}),
            'homelands_constellations': net_data.get("constellations", {})
        }

        m_count = len(matches_list)
        p_count = len(df_ratings) if not df_ratings.empty else len(history)
        Logger.step(f"Archive [{tag.upper()}]: {m_count} matches, {p_count} players loaded")

    if archive_seasons:
        total_archived_matches = sum(len(a['matches_list']) for a in archives_raw_data.values())
        Logger.success(
            f"Total archives: {total_archived_matches} cumulative matches across "
            f"{len(archive_seasons)} season(s), {len(elo_ratings)} players tracked"
        )

    last_season_ranked_players = set()
    if archive_seasons:
        last_tag = archive_seasons[-1]
        last_df = archives_raw_data[last_tag]['final_df']
        if not last_df.empty and 'Rank' in last_df.columns:
            id_col = 'PlayerID' if 'PlayerID' in last_df.columns else 'Player'
            for _, row in last_df.iterrows():
                rank_val = str(row.get('Rank', '')).strip()
                if rank_val and rank_val not in ('-', 'nan', 'None'):
                    last_season_ranked_players.add(str(row[id_col]))

    Logger.info(
        f"Ranked players from last archive season "
        f"({archive_seasons[-1] if archive_seasons else 'None'}): {len(last_season_ranked_players)}"
    )

    return archive_seasons, archives_raw_data, elo_ratings, last_season_ranked_players


# =========================================================================
# --- 5. ELO COMPUTATION, RELATIONS & HALL OF FAME ---
# =========================================================================

def _serialize_timestamp(val):
    if val is None or pd.isna(val):
        return None
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)

def _compute_match_updates(match_participants, elo_ratings, elo_model):
    """Computes per-player Elo update steps u_i and scores for a 4-player match."""
    n = len(match_participants)
    c = math.log(10.0) / 400.0

    raw_scores = [float(p['Score']) for p in match_participants]
    if elo_model.get('normalize_scores', False):
        total_score = sum(raw_scores)
        scores = [s / total_score for s in raw_scores] if total_score > 0 else raw_scores
    else:
        scores = raw_scores

    seat_effects = elo_model.get('seat_effects')
    x = []
    for p in match_participants:
        r = elo_ratings[p['PlayerID']]
        seat_bonus = 0.0
        if seat_effects and len(seat_effects) == 4:
            seat = p.get('Turn_Order')
            if seat is not None and not pd.isna(seat):
                seat_idx = int(seat) - 1
                if 0 <= seat_idx < 4:
                    seat_bonus = float(seat_effects[seat_idx])
        x.append(r + seat_bonus)

    field_T = elo_model.get('field_T')
    weights = None
    if field_T is not None and n > 1:
        T = float(field_T)
        z = []
        weights = [[0.0] * n for _ in range(n)]
        for i in range(n):
            opp_indices = [j for j in range(n) if j != i]
            scaled = [x[j] / T for j in opp_indices]
            max_s = max(scaled)
            exps = [math.exp(s - max_s) for s in scaled]
            sum_exps = sum(exps)
            field_i = T * (max_s + math.log(sum_exps / len(opp_indices)))
            z.append(0.75 * c * (x[i] - field_i))
            for idx, j in enumerate(opp_indices):
                weights[i][j] = exps[idx] / sum_exps
    else:
        z = [c * xi for xi in x]

    max_z = max(z)
    exp_z = [math.exp(zi - max_z) for zi in z]
    sum_exp_z = sum(exp_z)
    q = [ez / sum_exp_z for ez in exp_z]

    lam = float(elo_model.get('luck_lambda', 0.0))
    luck_mode = elo_model.get('luck_mode', 'prediction_only')
    p_pred = [lam / n + (1.0 - lam) * qi for qi in q] if lam > 0 else q

    if lam > 0 and luck_mode == 'expected':
        v = [scores[i] - p_pred[i] for i in range(n)]
    elif lam > 0 and luck_mode == 'gradient':
        w = [
            (scores[i] * (1.0 - lam) * q[i] / p_pred[i]) if p_pred[i] > 0 else 0.0
            for i in range(n)
        ]
        sum_w = sum(w)
        v = [w[i] - q[i] * sum_w for i in range(n)]
    else:
        v = [scores[i] - q[i] for i in range(n)]

    if weights is not None:
        u = [
            0.75 * (v[j] - sum(v[i] * weights[i][j] for i in range(n)))
            for j in range(n)
        ]
    else:
        u = v

    return u, scores

def compute_season_elo(
    df,
    inherited_elo,
    last_season_ranked_players,
    k_config,
    prev_season_tag=None,
    is_legacy=False,
    rebalance=False,
    serialize_dates=False,
    elo_model=None,
    qualification_config=None,
    cutoff_date=None,
):
    elo_ratings = dict(inherited_elo)
    inherited_ids = set(inherited_elo.keys())

    if not df.empty:
        for pid in df['PlayerID'].unique():
            if pid not in elo_ratings:
                elo_ratings[pid] = 1200.0

    peak_elo = dict(elo_ratings)
    last_diff = {pid: 0.0 for pid in elo_ratings}
    player_stats = {pid: {'games': 0, 'wins': 0.0, 'last_date': None} for pid in elo_ratings}

    start_label = f"{prev_season_tag.upper()} Final" if prev_season_tag else "Start"
    player_history = {
        pid: [[start_label if pid in inherited_ids else "Start", round(r), None]]
        for pid, r in elo_ratings.items()
    }

    match_history_data = []
    player_match_dates = {pid: [] for pid in elo_ratings}

    if not df.empty:
        for game_id, group in df.groupby('GameID', sort=False):
            match_participants = group.to_dict('records')
            current_match_sum = round(sum(elo_ratings[p['PlayerID']] for p in match_participants))

            current_dt = pd.to_datetime(match_participants[0]['Date_Closed'])
            current_date = current_dt.strftime('%Y-%m-%d')

            update_steps, effective_scores = _compute_match_updates(
                match_participants, elo_ratings, elo_model or {}
            )

            deltas_this_match = {}
            for idx, p in enumerate(match_participants):
                pid = p['PlayerID']
                actual = effective_scores[idx]

                g_count = player_stats[pid]['games']
                last_dt = player_stats[pid]['last_date']
                is_ranked = pid in last_season_ranked_players
                k = calculate_k_factor(
                    g_count, last_dt, current_dt, k_config,
                    is_ranked=is_ranked, is_legacy=is_legacy
                )
                change = k * update_steps[idx]

                elo_ratings[pid] += change
                last_diff[pid] = change
                deltas_this_match[pid] = round(change)

                if elo_ratings[pid] > peak_elo[pid]:
                    peak_elo[pid] = elo_ratings[pid]

                player_stats[pid]['games'] += 1
                player_stats[pid]['wins'] += actual
                player_stats[pid]['last_date'] = current_dt
                player_match_dates[pid].append(current_dt)

                player_history[pid].append([current_date, round(elo_ratings[pid]), int(game_id)])

            players_list = [{
                'id': p['PlayerID'],
                'delta': int(deltas_this_match[p['PlayerID']]),
                'is_winner': bool(p['Score'] >= 0.5)
            } for p in match_participants]

            date_closed_val = match_participants[0].get('Date_Closed')
            date_created_val = match_participants[0].get('Date_Created')
            if serialize_dates:
                date_closed_val = _serialize_timestamp(date_closed_val)
                date_created_val = _serialize_timestamp(date_created_val)

            match_history_data.append({
                'MatchID': int(game_id),
                'Date': current_date,
                'Date_Closed': date_closed_val,
                'Date_Created': date_created_val,
                'Turn_Timing': match_participants[0].get('Turn_Timing'),
                'players': players_list,
                'ELO_Sum': current_match_sum,
            })

    if rebalance:
        active_players = [pid for pid in elo_ratings if player_stats[pid]['games'] >= 1]
        inactive_players = [pid for pid in elo_ratings if player_stats[pid]['games'] == 0]
        num_players, num_active = len(elo_ratings), len(active_players)

        if num_active > 0 and num_players > 0:
            actual_sum = sum(elo_ratings.values())
            theoretical_sum = num_players * 1200.0
            total_deficit = theoretical_sum - actual_sum
            bonus_per_player = total_deficit / num_active

            Logger.section("SEASON END REBALANCING")
            Logger.info(f"Total database players: {num_players} | Active: {num_active} | Inactive: {len(inactive_players)}")
            Logger.info(f"Actual Total Elo: {actual_sum:.2f} | Theoretical: {theoretical_sum:.2f}")
            Logger.info(f"Global deficit injected: {total_deficit:.2f} points (+{bonus_per_player:.4f} per active)")

            for pid in active_players:
                elo_ratings[pid] += bonus_per_player
                if elo_ratings[pid] > peak_elo[pid]:
                    peak_elo[pid] = elo_ratings[pid]
                player_history[pid].append(["Final", round(elo_ratings[pid]), None])

        for pid in inactive_players:
            player_history[pid].append(["Final", round(elo_ratings[pid]), None])

    min_games = qualification_config['min_games']
    window_days = qualification_config['window_days']
    rank_squirrels = qualification_config['rank_squirrels']

    window_start = None
    if window_days is not None:
        window_start = pd.to_datetime(cutoff_date, utc=True) + pd.Timedelta(days=1 - window_days)

    leaderboard_list = []
    for pid, rating in elo_ratings.items():
        s = player_stats[pid]
        diff = round(last_diff[pid])

        qualifying_games = (
            sum(1 for d in player_match_dates[pid] if d >= window_start)
            if window_start is not None
            else s['games']
        )

        has_tier = qualifying_games >= min_games
        tier = get_tier_name(rating) if has_tier else "unassigned"
        is_ranked = has_tier and (rank_squirrels or tier != "squirrel")

        leaderboard_list.append({
            'PlayerID': pid,
            'ELO': rating,
            'Tier': tier,
            'Games': s['games'],
            'Wins': s['wins'],
            'Win Rate': f"{(s['wins'] / s['games']):.1%}" if s['games'] > 0 else "0.0%",
            'Peak': round(peak_elo[pid]),
            'Last': f"+{diff}" if diff > 0 else str(diff),
            'Qualified': is_ranked
        })

    final_df = pd.DataFrame()
    if leaderboard_list:
        final_df = pd.DataFrame(leaderboard_list).sort_values(by='ELO', ascending=False)
        rank_counter = 1
        ranks = []
        for _, row in final_df.iterrows():
            if row['Qualified']:
                ranks.append(rank_counter)
                rank_counter += 1
            else:
                ranks.append("-")
        final_df.insert(0, 'Rank', ranks)

    return {
        'elo_ratings': elo_ratings,
        'peak_elo': peak_elo,
        'last_diff': last_diff,
        'player_stats': player_stats,
        'player_history': player_history,
        'matches': match_history_data,
        'final_df': final_df,
    }


def get_elo_for_match(player_id, game_id, full_history):
    history = full_history.get(str(player_id), [])
    for i, entry in enumerate(history):
        if entry[2] == game_id:
            return entry[1] if i == 0 else history[i - 1][1]
    return None


def extract_relations(matches_list, full_history):
    all_players = {str(p.get('id') or p.get('name')) for m in matches_list for p in m['players']}

    relations = {pid: {
        "trophy": {"id": None, "elo": -1},
        "bane": {"id": None, "elo": 99999},
        "unique_opponents": 0
    } for pid in all_players}

    opponents_track = {pid: set() for pid in all_players}

    for m in matches_list:
        match_id = m['MatchID']
        p_ids = [str(p.get('id') or p.get('name')) for p in m['players']]

        for pid in p_ids:
            for opp_id in p_ids:
                if pid != opp_id:
                    opponents_track[pid].add(opp_id)

        winners = [p for p in m['players'] if p['is_winner']]
        losers = [p for p in m['players'] if not p['is_winner']]

        for w in winners:
            w_id = str(w.get('id') or w.get('name'))
            for l in losers:
                l_id = str(l.get('id') or l.get('name'))
                l_elo = get_elo_for_match(l_id, match_id, full_history)
                if l_elo is not None and l_elo > relations[w_id]['trophy']['elo']:
                    relations[w_id]['trophy'] = {"id": l_id, "elo": int(round(l_elo))}

        for l in losers:
            l_id = str(l.get('id') or l.get('name'))
            for w in winners:
                w_id = str(w.get('id') or w.get('name'))
                w_elo = get_elo_for_match(w_id, match_id, full_history)
                if w_elo is not None and w_elo < relations[l_id]['bane']['elo']:
                    relations[l_id]['bane'] = {"id": w_id, "elo": int(round(w_elo))}

    for pid in all_players:
        relations[pid]["unique_opponents"] = len(opponents_track[pid])

    return relations


def extract_all_streaks(history, player_id, player_registry):
    streaks = []
    if len(history) < 11:
        return streaks
    short_name = player_registry.get_clean_name(player_id)
    current_s = None

    for i in range(10, len(history)):
        date_str, elo_val = history[i][0], history[i][1]
        if "-" not in str(date_str):
            continue
        tier_now = get_tier_name(elo_val)
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
    for pid, h in sources:
        for s in extract_all_streaks(h, pid, player_registry):
            key = (s['player'], s['tier'])
            if key not in best_streaks_only:
                best_streaks_only[key] = s
            else:
                curr = best_streaks_only[key]
                if (s['streak_count'] > curr['streak_count']) or (
                    s['streak_count'] == curr['streak_count'] and s['peak'] > curr['peak']
                ):
                    best_streaks_only[key] = s

    all_sorted_streaks = sorted(
        best_streaks_only.values(),
        key=lambda x: (
            TIER_HIERARCHY.index(x['tier']) if x['tier'] in TIER_HIERARCHY else 99,
            -x['streak_count'],
            -x['peak']
        )
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
