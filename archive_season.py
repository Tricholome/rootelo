import argparse
import json
import math
import os
import re
from datetime import datetime
import pandas as pd
import requests

# =========================================================================
# --- 1. UTILS & LEAGUE CONFIGURATION ---
# =========================================================================

DISCORD_EPOCH = 1420070400000


def load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"  ⚠️ Error reading {filepath}: {e}")
    return default


def save_json(filepath, data, indent=2):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
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


def fetch_raw_matches(league_config, tournament_id=None, is_legacy=False):
    raw_data = []
    api_cfg = league_config.get('api', {})
    token_var = api_cfg.get('token_env_var')
    api_token = os.getenv(token_var) if token_var else os.getenv('API_TOKEN')

    auth_prefix = api_cfg.get('auth_prefix', 'Token')
    headers = {'Authorization': f'{auth_prefix} {api_token}'} if api_token else {}

    base_url = api_cfg.get('base_url', '').rstrip('/')
    endpoint = api_cfg.get('endpoint') or (f"{base_url}/api/match/" if base_url else "")

    t_id = tournament_id or api_cfg.get('tournament_id')
    params = {'limit': 500}
    if t_id:
        params['tournament'] = t_id

    next_url = endpoint
    all_matches = []
    while next_url:
        try:
            res = requests.get(next_url, headers=headers, params=params)
            params = None
            if res.status_code == 400:
                print(f"  ⚠️ Tournament {t_id} is not active on API.")
                break
            res.raise_for_status()
            data = res.json()
            all_matches.extend(data.get('results', []))
            next_url = data.get('next')
        except requests.RequestException as e:
            print(f"  ⚠ API Error ({league_config.get('name', 'League')}): {e}")
            break

    for m in all_matches:
        participants = m.get('participants', [])
        if len(participants) == 4:
            created_at = None if is_legacy else get_discord_created_at(m.get('table_talk_url'))
            turn_timing = m.get('turn_timing')

            for p in participants:
                pid = str(p.get('player_id') or p.get('player'))
                raw_name = p.get('player_name') or p.get('player') or pid

                raw_data.append({
                    'GameID': m['id'],
                    'PlayerID': pid,
                    'Raw_Name': raw_name,
                    'Score': float(p.get('tournament_score', 0.0)),
                    'Date_Closed': m.get('date_closed'),
                    'Date_Created': created_at,
                    'Turn_Timing': turn_timing
                })

    return raw_data


# =========================================================================
# --- 2. MAIN ARCHIVE PIPELINE ---
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Rootelo Season Archiver Engine")
    parser.add_argument('--league', required=True, help="League slug (e.g., 'rdl', 'hoot')")
    parser.add_argument('--season', required=True, help="Season tag (e.g., 'lh01')")
    parser.add_argument('--cutoff', required=True, help="Cutoff date (YYYY-MM-DD)")
    parser.add_argument('--tournament-id', type=int, required=True, help="Tournament ID")
    parser.add_argument('--prev-season', default=None, help="Previous season tag")
    parser.add_argument('--legacy', action='store_true', help="Enable legacy mode (step K-factor 80/40/20 and omit Date_Created)")
    args = parser.parse_args()

    league_slug = args.league.strip().lower()
    season_tag = args.season.strip().lower()
    cutoff_date_str = args.cutoff.strip()
    cutoff_date = datetime.strptime(cutoff_date_str, "%Y-%m-%d").date()
    previous_season_tag = args.prev_season.strip().lower() if args.prev_season else None
    is_legacy = args.legacy

    league_config = load_league_config(league_slug)
    k_config = league_config.get('k_factor', {})

    data_dir = os.path.join("data", league_slug)
    season_dir = os.path.join(data_dir, "archives", season_tag)
    corrections_path = os.path.join(data_dir, "corrections.csv")
    players_path = os.path.join(data_dir, "players.json")

    output_ratings = os.path.join(season_dir, "ratings.csv")
    output_history = os.path.join(season_dir, "history.json")
    output_matches = os.path.join(season_dir, "matches.json")
    output_metadata = os.path.join(season_dir, "metadata.json")
    output_relations = os.path.join(season_dir, "relations.json")
    output_network = os.path.join(season_dir, "network.json")

    print(f"\n=== INITIALIZING ARCHIVE: {season_tag.upper()} ({league_config.get('name', league_slug).upper()}) ===")
    if is_legacy:
        print("  ⚙️ LEGACY mode active: Step K-factor (80/40/20), Date_Created ignored.")
    else:
        print("  ⚙️ DYNAMIC mode active: Exponential decay K-factor, Discord creation timestamp extraction enabled.")

    inherited_elo = {}
    last_season_ranked_players = set()

    if previous_season_tag:
        prev_path = os.path.join(data_dir, "archives", previous_season_tag, "ratings.csv")
        if os.path.exists(prev_path):
            print(f"  > Loading baseline ratings from {previous_season_tag.upper()}...")
            df_prev = pd.read_csv(prev_path)
            id_col = 'PlayerID' if 'PlayerID' in df_prev.columns else 'Player'
            inherited_elo = {str(row[id_col]): float(row.get('ELO', 1200.0)) for _, row in df_prev.iterrows()}

            if 'Rank' in df_prev.columns:
                for _, row in df_prev.iterrows():
                    rank_val = str(row.get('Rank', '')).strip()
                    if rank_val and rank_val not in ('-', 'nan', 'None'):
                        last_season_ranked_players.add(str(row[id_col]))

            print(f"  > {len(inherited_elo)} players inherited ({len(last_season_ranked_players)} ranked).")
        else:
            print(f"  > Warning: Previous ratings file not found at {prev_path}")
    else:
        print("  > No previous season defined. Starting fresh (1200.0 baseline).")

    print("\n=== FETCHING API DATA ===")
    print(f"  > Requesting matches (Cutoff date: {cutoff_date_str})...")
    raw_data = fetch_raw_matches(league_config, tournament_id=args.tournament_id, is_legacy=is_legacy)

    players_map = load_json(players_path, {})
    for item in raw_data:
        if item.get('PlayerID') and item.get('Raw_Name'):
            players_map[str(item['PlayerID'])] = str(item['Raw_Name']).strip()
    save_json(players_path, players_map)

    df = pd.DataFrame(raw_data)
    if not df.empty:
        df['PlayerID'] = df['PlayerID'].astype(str)
        df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)
        if 'Date_Created' in df.columns and not is_legacy:
            df['Date_Created'] = pd.to_datetime(df['Date_Created'], utc=True)

        if os.path.exists(corrections_path):
            try:
                df_corr = pd.read_csv(corrections_path)
                if not df_corr.empty and 'GameID' in df_corr.columns:
                    df_corr['GameID'] = df_corr['GameID'].astype(int)

                    if 'Date_Closed' in df_corr.columns:
                        closed_map = df_corr.set_index('GameID')['Date_Closed'].dropna()
                        mask_closed = df['GameID'].isin(closed_map.index)
                        if mask_closed.any():
                            original_times = df.loc[mask_closed, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
                            new_dates = pd.to_datetime(df.loc[mask_closed, 'GameID'].map(closed_map)).dt.strftime('%Y-%m-%d')
                            df.loc[mask_closed, 'Date_Closed'] = pd.to_datetime(new_dates + ' ' + original_times, utc=True)

                    if not is_legacy and 'Date_Created' in df_corr.columns:
                        created_map = df_corr.set_index('GameID')['Date_Created'].dropna()
                        mask_created = df['GameID'].isin(created_map.index)
                        if mask_created.any():
                            df.loc[mask_created, 'Date_Created'] = pd.to_datetime(
                                df.loc[mask_created, 'GameID'].map(created_map), utc=True
                            )

                    print(f"  > Applied manual date corrections from {corrections_path}.")
            except Exception as e:
                print(f"  > Note: Corrections skipped or failed ({e}).")

        df = df[df['Date_Closed'].dt.date <= cutoff_date].copy()
        df = df.sort_values(by='Date_Closed').reset_index(drop=True)

    print("\n=== CALCULATING ELO & STATS ===")
    elo_ratings = {**{pid: 1200.0 for pid in df['PlayerID'].unique()}, **inherited_elo} if not df.empty else inherited_elo.copy()
    peak_elo = elo_ratings.copy()
    player_stats = {pid: {'games': 0, 'wins': 0.0, 'last_date': None} for pid in elo_ratings}
    last_diff = {pid: 0.0 for pid in elo_ratings}

    start_label = f"{previous_season_tag.upper()} Final" if previous_season_tag else "Start"
    player_history = {
        pid: [[start_label if pid in inherited_elo else "Start", round(r), None]]
        for pid, r in elo_ratings.items()
    }

    archive_matches_list = []
    pre_match_elos = {}

    if not df.empty:
        for game_id, group in df.groupby('GameID', sort=False):
            match_participants = group.to_dict('records')
            current_match_sum = round(sum(elo_ratings[p['PlayerID']] for p in match_participants))

            current_dt = pd.to_datetime(match_participants[0]['Date_Closed'])
            current_date = current_dt.strftime('%Y-%m-%d')

            date_closed_val = match_participants[0].get('Date_Closed')
            date_closed_str = date_closed_val.isoformat() if hasattr(date_closed_val, 'isoformat') else (str(date_closed_val) if date_closed_val else None)

            date_created_val = match_participants[0].get('Date_Created')
            date_created_str = date_created_val.isoformat() if hasattr(date_created_val, 'isoformat') else (str(date_created_val) if date_created_val else None)

            turn_timing_val = match_participants[0].get('Turn_Timing')

            q_scores = {p['PlayerID']: 10 ** (elo_ratings[p['PlayerID']] / 400) for p in match_participants}
            total_q = sum(q_scores.values())

            deltas_this_match = {}

            for p in match_participants:
                pid = p['PlayerID']
                actual = p['Score']
                expected = q_scores[pid] / total_q

                pre_match_elos[(pid, game_id)] = round(elo_ratings[pid])

                g_count = player_stats[pid]['games']
                last_dt = player_stats[pid]['last_date']
                is_ranked = pid in last_season_ranked_players

                k = calculate_k_factor(g_count, last_dt, current_dt, k_config, is_ranked=is_ranked, is_legacy=is_legacy)
                change = k * (actual - expected)

                elo_ratings[pid] += change
                last_diff[pid] = change
                deltas_this_match[pid] = round(change)

                if elo_ratings[pid] > peak_elo[pid]:
                    peak_elo[pid] = elo_ratings[pid]

                player_stats[pid]['games'] += 1
                player_stats[pid]['wins'] += actual
                player_stats[pid]['last_date'] = current_dt

                player_history[pid].append([current_date, round(elo_ratings[pid]), int(game_id)])

            archive_matches_list.append({
                'MatchID': int(game_id),
                'Date': current_date,
                'Date_Closed': date_closed_str,
                'Date_Created': date_created_str,
                'Turn_Timing': turn_timing_val,
                'players': [{
                    'id': p['PlayerID'],
                    'delta': deltas_this_match[p['PlayerID']],
                    'is_winner': bool(p['Score'] >= 0.5)
                } for p in match_participants],
                'ELO_Sum': current_match_sum
            })

    active_players = [pid for pid in elo_ratings if player_stats[pid]['games'] >= 1]
    inactive_players = [pid for pid in elo_ratings if player_stats[pid]['games'] == 0]

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

        for pid in active_players:
            elo_ratings[pid] += bonus_per_player
            if elo_ratings[pid] > peak_elo[pid]:
                peak_elo[pid] = elo_ratings[pid]
            player_history[pid].append(["Final", round(elo_ratings[pid]), None])

    for pid in inactive_players:
        player_history[pid].append(["Final", round(elo_ratings[pid]), None])

    results = [
        {
            'PlayerID': pid,
            'ELO': rating,
            'Games': player_stats[pid]['games'],
            'Wins': player_stats[pid]['wins'],
            'Win Rate': f"{(player_stats[pid]['wins'] / player_stats[pid]['games']):.1%}" if player_stats[pid]['games'] > 0 else "0.0%",
            'Peak': round(peak_elo[pid]),
            'Last': f"+{round(last_diff[pid])}" if round(last_diff[pid]) > 0 else str(round(last_diff[pid])),
            'Qualified': (player_stats[pid]['games'] >= 10 and round(rating) >= 1200)
        } for pid, rating in elo_ratings.items()
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

    print("\n=== EXTRACTING RELATIONSHIPS ===")

    def extract_relations(matches_list, pre_elos):
        all_players = {p['id'] for m in matches_list for p in m['players']}
        relations = {pid: {
            "trophy": {"id": None, "elo": -1},
            "bane": {"id": None, "elo": 99999},
            "unique_opponents": 0
        } for pid in all_players}

        opponents_track = {pid: set() for pid in all_players}

        for m in matches_list:
            match_id = m['MatchID']
            p_ids = [p['id'] for p in m['players']]

            for pid in p_ids:
                opponents_track[pid].update(opp for opp in p_ids if opp != pid)

            winners = [p for p in m['players'] if p['is_winner']]
            losers = [p for p in m['players'] if not p['is_winner']]

            for w in winners:
                for l in losers:
                    l_elo = pre_elos.get((l['id'], match_id))
                    if l_elo is not None and l_elo > relations[w['id']]['trophy']['elo']:
                        relations[w['id']]['trophy'] = {"id": l['id'], "elo": l_elo}

            for l in losers:
                for w in winners:
                    w_elo = pre_elos.get((w['id'], match_id))
                    if w_elo is not None and w_elo < relations[l['id']]['bane']['elo']:
                        relations[l['id']]['bane'] = {"id": w['id'], "elo": w_elo}

        for pid in all_players:
            relations[pid]["unique_opponents"] = len(opponents_track[pid])

        return relations

    relations_map = extract_relations(archive_matches_list, pre_match_elos)

    homelands_snapshots = {}
    homelands_constellations = {}
    try:
        from frog import run_homelands_simulation
        print("\n=== GENERATING HOMELANDS SNAPSHOTS (NETWORK) ===")
        global_config_path = os.path.join("data", "config", "config.json")
        tribe_names = []
        if os.path.exists(global_config_path):
            tribe_names = load_json(global_config_path).get("network", {}).get("tribe_names", [])

        homelands_snapshots, homelands_constellations = run_homelands_simulation(
            archive_matches_list,
            custom_config={"enabled": True, "tribe_names": tribe_names},
            season_id=season_tag
        )
        print(f"  > Homelands simulation finished successfully ({len(homelands_snapshots)} daily snapshots).")
    except ImportError:
        print("\n=== SKIPPING HOMELANDS SNAPSHOTS (frog.py not found) ===")
    except Exception as e:
        print(f"\n⚠️ Homelands simulation error: {e}")

    print("\n=== EXPORTING ARCHIVES ===")
    os.makedirs(season_dir, exist_ok=True)

    def safe_save(path, data, is_json=False):
        if os.path.exists(path):
            os.remove(path)
        if is_json:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        else:
            data.to_csv(path, index=False)
        print(f"  > {os.path.basename(path)} saved in {season_dir}.")

    safe_save(output_ratings, final_df)

    if archive_matches_list:
        archive_matches_list = sorted(archive_matches_list, key=lambda x: x['ELO_Sum'], reverse=True)
        for idx, m in enumerate(archive_matches_list, start=1):
            m['Rank'] = idx
    safe_save(output_matches, archive_matches_list, is_json=True)

    safe_save(output_history, player_history, is_json=True)
    safe_save(output_relations, relations_map, is_json=True)

    if homelands_snapshots or homelands_constellations:
        network_payload = {
            "snapshots": homelands_snapshots,
            "constellations": homelands_constellations
        }
        safe_save(output_network, network_payload, is_json=True)

    metadata = {
        "season_tag": season_tag.upper(),
        "cutoff_date": cutoff_date_str,
        "match_count": len(archive_matches_list),
        "is_legacy": is_legacy
    }
    safe_save(output_metadata, metadata, is_json=True)

    print(f"\n✨ Archives for {season_tag.upper()} successfully generated in {season_dir}!")


if __name__ == "__main__":
    main()
