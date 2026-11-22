import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
import pandas as pd

from engine import (
    Logger,
    PlayerRegistry,
    build_hall_of_fame,
    compute_season_elo,
    extract_relations,
    fetch_raw_matches,
    load_all_league_configs,
    load_archives,
    load_json,
    prepare_matches_dataframe,
)
from frog import run_homelands_simulation
from renderer import (
    SiteRenderer,
    export_league_api,
    format_champ_match,
    format_constellations,
    format_homelands_snapshots,
    format_relations_data,
    prepare_leaderboard_data,
    prepare_matches_data,
    prepare_trends_data,
)

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)


def run_league_pipeline(league_config, all_leagues_list):
    start_time = time.time()
    slug = league_config['slug']
    name = league_config['name']
    current_season_tag = league_config['current_season_tag']
    format_replace_chars = league_config.get('profile_format_replace_chars', False)

    Logger.header(f"ROOTELO PIPELINE: {name.upper()} ({slug})")

    # --- 1. CONFIGURATION & HISTORICAL DATA ---
    Logger.section("1. CONFIGURATION & HISTORICAL DATA")
    data_dir = os.path.join("data", slug)
    player_registry = PlayerRegistry(os.path.join(data_dir, "players.json"))

    config = load_json(os.path.join("data", "config", "config.json"))
    pages_content = load_json(os.path.join("data", "config", "pages_content.json"))
    champions_data = load_json(os.path.join(data_dir, "champions.json"))
    corrections_file = os.path.join(data_dir, "corrections.csv")

    archive_seasons, archives_raw_data, inherited_elo, last_season_ranked_players = load_archives(
        data_dir, current_season_tag
    )
    archived_player_ids = set(inherited_elo.keys())

    # --- 2. MATCH FETCHING & DATE FILTERING ---
    Logger.section("2. MATCH FETCHING & DATE FILTERING")
    today = date.today()
    cutoff_date = today - timedelta(days=1)

    Logger.info(f"Fetching API data for {name}... Filtering matches before: {today}")
    raw_data = fetch_raw_matches(league_config)

    for item in raw_data:
        player_registry.register(item.get('PlayerID'), item.get('Raw_Name'))
    player_registry.save()

    df = prepare_matches_dataframe(raw_data, cutoff_date, corrections_path=corrections_file)

    all_player_ids = set(archived_player_ids)
    if not df.empty:
        all_player_ids.update(df['PlayerID'].unique())
    for tag in archive_seasons:
        if archives_raw_data[tag]['history']:
            all_player_ids.update(archives_raw_data[tag]['history'].keys())

    global_players_list = sorted(
        list({player_registry.get_clean_name(pid) for pid in all_player_ids if pid}),
        key=lambda x: x.lower()
    )
    Logger.success(f"Player registry initialized ({len(all_player_ids)} unique player IDs)")

    player_profile_map = {
        player_registry.get_clean_name(pid): player_registry.get_profile_slug(pid, format_replace_chars)
        for pid in all_player_ids if pid
    }

    # --- 3. ELO COMPUTATION & RELATIONS EXTRACTION ---
    Logger.section("3. ELO COMPUTATION & RELATIONS EXTRACTION")
    elo_result = compute_season_elo(
        df=df,
        inherited_elo=inherited_elo,
        last_season_ranked_players=last_season_ranked_players,
        k_config=league_config.get('k_factor', {}),
        prev_season_tag=archive_seasons[-1] if archive_seasons else None,
    )

    elo_ratings = elo_result['elo_ratings']
    player_stats = elo_result['player_stats']
    player_history = elo_result['player_history']
    match_history_data = elo_result['matches']
    current_final_df = elo_result['final_df']

    current_matches_df = pd.DataFrame(match_history_data)
    if not current_matches_df.empty:
        current_matches_df = current_matches_df.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
        current_matches_df.insert(0, 'Rank', range(1, len(current_matches_df) + 1))

    raw_current_relations = extract_relations(match_history_data, player_history)
    current_relations = format_relations_data(raw_current_relations, player_registry)

    qual_count = len(current_final_df[current_final_df['Qualified'] == True]) if not current_final_df.empty else 0
    active_count = len(current_final_df[current_final_df['Games'] > 0]) if not current_final_df.empty else 0
    Logger.success(
        f"Elo computation complete: {len(current_final_df)} total players tracked "
        f"({active_count} active this season, {qual_count} qualified on leaderboard)"
    )

    current_meta = {
        'match_count': df['GameID'].nunique() if not df.empty else 0,
        'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
    }
    reigning_champ = champions_data.get(archive_seasons[-1], {}).get('champion') if archive_seasons else None

    display_leaderboard_current = prepare_leaderboard_data(
        current_final_df[current_final_df['Games'] > 0],
        player_registry,
        champion_ref=reigning_champ
    ) if not current_final_df.empty else []

    display_matches_current = prepare_matches_data(
        current_matches_df.to_dict('records'), player_registry, league_config
    ) if not current_matches_df.empty else []
    display_trends_current = prepare_trends_data(player_history, player_registry, league_config)

    display_archives = {}
    for tag in archive_seasons:
        raw = archives_raw_data[tag]
        season_champ = champions_data.get(tag, {}).get('champion')
        lb_data = prepare_leaderboard_data(
            raw['final_df'][raw['final_df']['Games'] > 0],
            player_registry,
            champion_ref=season_champ,
            is_archive=True
        ) if not raw['final_df'].empty else []

        display_archives[tag] = {
            'leaderboard': lb_data,
            'matches': prepare_matches_data(raw['matches_list'], player_registry, league_config),
            'trends': prepare_trends_data(raw['history'], player_registry, league_config)
        }

    sources = [
        (row['PlayerID'], player_history.get(row['PlayerID'], []))
        for _, row in current_final_df.iterrows()
    ] if not current_final_df.empty else []
    for tag in archive_seasons:
        for pid, h in archives_raw_data.get(tag, {}).get('history', {}).items():
            sources.append((pid, h))

    hall_of_fame_data = build_hall_of_fame(sources, player_registry)

    # --- 4. HOMELANDS NETWORK SIMULATION ---
    Logger.section("4. HOMELANDS NETWORK SIMULATION")
    homelands_snapshots = {}
    homelands_constellations = {}

    homelands_cfg = league_config.get("network", {}).copy()
    homelands_enabled = bool(homelands_cfg.get("enabled", False))

    if not homelands_enabled:
        Logger.info(f"Homelands simulation disabled for league '{slug}'. Skipping.")
    else:
        homelands_cfg["tribe_names"] = config.get("network", {}).get("tribe_names", [])
        try:
            raw_snapshots, raw_constellations = run_homelands_simulation(
                match_history_data,
                custom_config=homelands_cfg,
                season_id=current_season_tag
            )
            homelands_snapshots = format_homelands_snapshots(raw_snapshots, player_registry)
            homelands_constellations = format_constellations(raw_constellations, player_registry)
            active = sorted(t for t, m in homelands_snapshots[max(homelands_snapshots)].items() if m) if homelands_snapshots else []
            active_str = f"{len(active)} active ({', '.join(active)})" if active else "0 active"
            Logger.success(f"Homelands simulation complete: {len(homelands_snapshots)} days — {active_str}")
        except Exception as e:
            Logger.warn(f"Failed to run homelands simulation: {e}")

    # --- 5. HTML RENDERING ---
    Logger.section("5. HTML RENDERING")
    player_data_map_json = json.dumps({
        player_registry.get_clean_name(pid): {
            'elo': round(r),
            'games': player_stats.get(pid, {}).get('games', 0),
            'is_ranked': pid in last_season_ranked_players
        }
        for pid, r in elo_ratings.items()
    })

    renderer = SiteRenderer(
        config=config,
        pages_content=pages_content,
        league_config=league_config,
        all_leagues_list=all_leagues_list,
        archive_seasons=archive_seasons,
        global_players_list=global_players_list,
        player_profile_map=player_profile_map,
        player_data_map_json=player_data_map_json,
        homelands_enabled=homelands_enabled,
    )

    renderer.render_season_pages(
        tag=current_season_tag,
        is_archive=False,
        lb_data=display_leaderboard_current,
        match_data=display_matches_current,
        trends_data=display_trends_current,
        meta=current_meta,
        snapshots_data=homelands_snapshots,
        constellations_data=homelands_constellations,
        relations_data=current_relations,
        champ_match=format_champ_match(champions_data.get(archive_seasons[-1]), player_registry) if archive_seasons else None,
    )

    for tag in archive_seasons:
        archive_relations_clean = format_relations_data(archives_raw_data[tag].get('relations', {}), player_registry)
        raw_homelands = archives_raw_data[tag].get('homelands_snapshots', {})
        archive_homelands_clean = format_homelands_snapshots(raw_homelands, player_registry) if raw_homelands else {}
        raw_constellations = archives_raw_data[tag].get('homelands_constellations', {})
        archive_constellations_clean = format_constellations(raw_constellations, player_registry) if raw_constellations else {}

        renderer.render_season_pages(
            tag=tag,
            is_archive=True,
            lb_data=display_archives[tag]['leaderboard'],
            match_data=display_archives[tag]['matches'],
            trends_data=display_archives[tag]['trends'],
            meta=archives_raw_data[tag]['metadata'],
            snapshots_data=archive_homelands_clean,
            constellations_data=archive_constellations_clean,
            relations_data=archive_relations_clean,
            champ_match=format_champ_match(champions_data.get(tag), player_registry),
            suffix=f"_{tag}",
        )

    renderer.render_static_pages(hall_of_fame_data)

    # --- 6. REST JSON API EXPORT ---
    Logger.section("6. REST JSON API EXPORT")
    export_league_api(current_final_df, player_registry, reigning_champ, config, league_config)

    elapsed = time.time() - start_time
    Logger.header(f"PIPELINE {slug.upper()} FINISHED IN {elapsed:.2f}s")


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
