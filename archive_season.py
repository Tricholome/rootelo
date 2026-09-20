import argparse
import json
import math
import os
import re
import sys
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


def load_league_config(league_slug):
    data_dir = os.path.join("data", league_slug)
    config_file = os.path.join(data_dir, "league.json")
    if not os.path.exists(config_file):
        config_file = os.path.join(data_dir, "config.json")

    if os.path.exists(config_file):
        cfg = load_json(config_file)
        cfg["slug"] = cfg.get("slug", league_slug)
        return cfg
    else:
        raise FileNotFoundError(f"League config file not found for '{league_slug}' in {data_dir}")


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


def fetch_raw_matches(league_config, tournament_id=None):
    """Fetches raw match data dynamically using specified league API configuration."""
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
            print(f"  ⚠️ API Error ({league_config.get('name', 'League')}): {e}")
            break

    for m in all_matches:
        participants = m.get('participants', [])
        if len(participants) == 4:
            created_at = get_discord_created_at(m.get('table_talk_url'))
            turn_timing = m.get('turn_timing')

            for p in participants:
                raw_data.append({
                    'GameID': m['id'],
                    'Player': p.get('player'),
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
    parser.add_argument('--league', default=os.getenv('LEAGUE_SLUG', 'rdl'), help="League slug (e.g., 'rdl', 'hoot')")
    parser.add_argument('--season', default=os.getenv('SEASON_TAG', 'lh01'), help="Season tag (e.g., 'lh01')")
    parser.add_argument('--prev-season', default=os.getenv('PREVIOUS_SEASON_TAG', ''), help="Previous season tag")
    parser.add_argument('--cutoff', default=os.getenv('CUTOFF_DATE_STR', '2026-03-31'), help="Cutoff date (YYYY-MM-DD)")
    parser.add_argument('--tournament-id', type=int, default=int(os.getenv('TOURNAMENT_ID', 0)) or None, help="Override Tournament ID")
    args = parser.parse_args()

    league_slug = args.league.strip().lower()
    season_tag = args.season.strip().lower()
    previous_season_tag = args.prev_season.strip().lower() or None
    cutoff_date_str = args.cutoff.strip()
    cutoff_date = datetime.strptime(cutoff_date_str, "%Y-%m-%d").date()

    league_config = load_league_config(league_slug)
    k_config = league_config.get('k_factor', {})

    data_dir = os.path.join("data", league_slug)
    season_dir = os.path.join(data_dir, "archives", season_tag)
    corrections_path = os.path.join(data_dir, "corrections.csv")

    output_ratings   = os.path.join(season_dir, "ratings.csv")
    output_history   = os.path.join(season_dir, "history.json")
    output_matches   = os.path.join(season_dir, "matches.json")
    output_metadata  = os.path.join(season_dir, "metadata.json")
    output_relations = os.path.join(season_dir, "relations.json")

    print(f"\n=== INITIALIZING ARCHIVE: {season_tag.upper()} ({league_config.get('name', league_slug).upper()}) ===")
    
    inherited_elo = {}
    last_season_ranked_players = set()

    if previous_season_tag:
        prev_path = os.path.join(data_dir, "archives", previous_season_tag, "ratings.csv")
        if os.path.exists(prev_path):
            print(f"  > Loading baseline ratings from {previous_season_tag.upper()}...")
            df_prev = pd.read_csv(prev_path)
            inherited_elo = {str(row['Player']): float(row.get('ELO', 1200.0)) for _, row in df_prev.iterrows()}
            
            if 'Rank' in df_prev.columns:
                for _, row in df_prev.iterrows():
                    rank_val = str(row.get('Rank', '')).strip()
                    if rank_val and rank_val not in ('-', 'nan', 'None'):
                        last_season_ranked_players.add(str(row['Player']))

            print(f"  > {len(inherited_elo)} players inherited ({len(last_season_ranked_players)} ranked).")
        else:
            print(f"  > Warning: Previous ratings file not found at {prev_path}")
    else:
        print("  > No previous season defined. Starting fresh (1200.0 baseline).")

    # Fetch Data
    print("\n=== FETCHING API DATA ===")
    print(f"  > Requesting matches (Cutoff date: {cutoff_date_str})...")
    raw_data = fetch_raw_matches(league_config, tournament_id=args.tournament_id)

    df = pd.DataFrame(raw_data)
    if not df.empty:
        df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)
        if 'Date_Created' in df.columns:
            df['Date_Created'] = pd.to_datetime(df['Date_Created'], utc=True)

        # Apply Manual Corrections (Date_Closed / Date_Created)
        if os.path.exists(corrections_path):
            try:
                df_corr = pd.read_csv(corrections_path)
                if not df_corr.empty and 'GameID' in df_corr.columns:
                    df_corr['GameID'] = df_corr['GameID'].astype(int)

                    if 'Date_Closed' in df_corr.columns:
                        closed_map = df_corr.set_index('GameID')['Date_Closed'].dropna()
                        mask_closed = df['GameID'].isin(closed_map.index)
                        if mask_closed.any():
                            df.loc[mask_closed, 'Date_Closed'] = pd.to_datetime(
                                df.loc[mask_closed, 'GameID'].map(closed_map), utc=True
                            )

                    if 'Date_Created' in df_corr.columns:
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

    # Elo Computation
    print("\n=== CALCULATING ELO & STATS (DYNAMIC K-FACTOR) ===")
    elo_ratings = {**{p: 1200.0 for p in df['Player'].unique()}, **inherited_elo} if not df.empty else inherited_elo.copy()
    peak_elo = elo_ratings.copy()
    player_stats = {p: {'games': 0, 'wins': 0.0, 'last_date': None} for p in elo_ratings}
    last_diff = {p: 0.0 for p in elo_ratings}

    start_label = f"{previous_season_tag.upper()} Final" if previous_season_tag else "Start"
    player_history = {p: [[start_label if p in inherited_elo else "Start", round(r), None]] for p, r in elo_ratings.items()}
    
    archive_matches_list = []
    pre_match_elos = {}

    if not df.empty:
        for game_id, group in df.groupby('GameID', sort=False):
            match_participants = group.to_dict('records')
            current_match_sum = round(sum(elo_ratings[p['Player']] for p in match_participants))
            
            current_dt = pd.to_datetime(match_participants[0]['Date_Closed'])
            current_date = current_dt.strftime('%Y-%m-%d')

            date_closed_val = match_participants[0].get('Date_Closed')
            date_closed_str = date_closed_val.isoformat() if hasattr(date_closed_val, 'isoformat') else (str(date_closed_val) if date_closed_val else None)

            date_created_val = match_participants[0].get('Date_Created')
            date_created_str = date_created_val.isoformat() if hasattr(date_created_val, 'isoformat') else (str(date_created_val) if date_created_val else None)

            turn_timing_val = match_participants[0].get('Turn_Timing')
            
            q_scores = {p['Player']: 10 ** (elo_ratings[p['Player']] / 400) for p in match_participants}
            total_q = sum(q_scores.values())
            
            deltas_this_match = {}
            
            for p in match_participants:
                name = p['Player']
                actual = p['Score']
                expected = q_scores[name] / total_q
                
                pre_match_elos[(name, game_id)] = round(elo_ratings[name])
                
                g_count = player_stats[name]['games']
                last_dt = player_stats[name]['last_date']
                is_ranked = name in last_season_ranked_players
                
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

            archive_matches_list.append({
                'MatchID': int(game_id),
                'Date': current_date,
                'Date_Closed': date_closed_str,
                'Date_Created': date_created_str,
                'Turn_Timing': turn_timing_val,
                'players': [{
                    'name': p['Player'],
                    'delta': deltas_this_match[p['Player']],
                    'is_winner': bool(p['Score'] >= 0.5)
                } for p in match_participants],
                'ELO_Sum': current_match_sum
            })

    # Season End Rebalancing
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
            player_history[p].append(["Final", round(elo_ratings[p]), None])           

    for p in inactive_players:
        player_history[p].append(["Final", round(elo_ratings[p]), None])        

    # Leaderboard DataFrame
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

    # Extraction of Relationships
    print("\n=== EXTRACTING RELATIONSHIPS ===")
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

    # Exports
    print("\n=== EXPORTING ARCHIVES ===")
    os.makedirs(season_dir, exist_ok=True)

    def safe_save(path, data, is_json=False):
        if os.path.exists(path):
            os.remove(path)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4) if is_json else data.to_csv(path, index=False)
        print(f"  > {os.path.basename(path)} saved in {season_dir}.")

    safe_save(output_ratings, final_df)

    if archive_matches_list:
        archive_matches_list = sorted(archive_matches_list, key=lambda x: x['ELO_Sum'], reverse=True)
        for idx, m in enumerate(archive_matches_list, start=1):
            m['Rank'] = idx
    safe_save(output_matches, archive_matches_list, is_json=True)

    safe_save(output_history, player_history, is_json=True)
    safe_save(output_relations, relations_map, is_json=True)

    metadata = {"season_tag": season_tag.upper(), "cutoff_date": cutoff_date_str, "match_count": len(archive_matches_list)}
    safe_save(output_metadata, metadata, is_json=True)

    print(f"\n✨ Archives for {season_tag.upper()} successfully generated in {season_dir}!")


if __name__ == "__main__":
    main()
