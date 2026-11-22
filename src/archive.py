import argparse
import os
import sys
from datetime import datetime
import pandas as pd

from engine import (
    Logger,
    PlayerRegistry,
    compute_season_elo,
    extract_relations,
    fetch_raw_matches,
    load_json,
    load_league_config,
    prepare_matches_dataframe,
    save_json,
)

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)


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
    player_registry = PlayerRegistry(os.path.join(data_dir, "players.json"))

    Logger.header(f"ARCHIVE: {season_tag.upper()} ({league_config.get('name', league_slug).upper()})")
    if is_legacy:
        Logger.info("LEGACY mode active: Step K-factor (80/40/20), Date_Created ignored.")
    else:
        Logger.info("DYNAMIC mode active: Exponential decay K-factor, Discord creation timestamp extraction enabled.")

    # --- 1. LOAD PREVIOUS SEASON BASELINE ---
    inherited_elo = {}
    last_season_ranked_players = set()

    if previous_season_tag:
        prev_path = os.path.join(data_dir, "archives", previous_season_tag, "ratings.csv")
        if os.path.exists(prev_path):
            Logger.step(f"Loading baseline ratings from {previous_season_tag.upper()}...")
            df_prev = pd.read_csv(prev_path)
            id_col = 'PlayerID' if 'PlayerID' in df_prev.columns else 'Player'
            inherited_elo = {str(row[id_col]): float(row.get('ELO', 1200.0)) for _, row in df_prev.iterrows()}

            if 'Rank' in df_prev.columns:
                for _, row in df_prev.iterrows():
                    rank_val = str(row.get('Rank', '')).strip()
                    if rank_val and rank_val not in ('-', 'nan', 'None'):
                        last_season_ranked_players.add(str(row[id_col]))

            Logger.step(f"{len(inherited_elo)} players inherited ({len(last_season_ranked_players)} ranked).")
        else:
            Logger.warn(f"Previous ratings file not found at {prev_path}")
    else:
        Logger.step("No previous season defined. Starting fresh (1200.0 baseline).")

    # --- 2. FETCH API DATA & APPLY CORRECTIONS ---
    Logger.section("FETCHING API DATA")
    Logger.step(f"Requesting matches (Cutoff date: {cutoff_date_str})...")
    raw_data = fetch_raw_matches(
        league_config,
        tournament_id=args.tournament_id,
        is_legacy=is_legacy,
        abort_on_error=False,
    )

    for item in raw_data:
        player_registry.register(item.get('PlayerID'), item.get('Raw_Name'))
    player_registry.save()

    df = prepare_matches_dataframe(
        raw_data,
        cutoff_date,
        corrections_path=corrections_path,
        is_legacy=is_legacy,
    )

    # --- 3. ELO, REBALANCING & RELATIONS ---
    Logger.section("CALCULATING ELO & STATS")
    elo_result = compute_season_elo(
        df=df,
        inherited_elo=inherited_elo,
        last_season_ranked_players=last_season_ranked_players,
        k_config=k_config,
        prev_season_tag=previous_season_tag,
        is_legacy=is_legacy,
        rebalance=True,
        serialize_dates=True,
    )

    final_df = elo_result['final_df']
    if not final_df.empty and 'Qualified' in final_df.columns:
        final_df = final_df.drop(columns=['Qualified'])

    archive_matches_list = elo_result['matches']
    player_history = elo_result['player_history']

    Logger.section("EXTRACTING RELATIONSHIPS")
    relations_map = extract_relations(archive_matches_list, player_history)

    # --- 4. HOMELANDS NETWORK SIMULATION ---
    homelands_snapshots = {}
    homelands_constellations = {}
    try:
        from frog import run_homelands_simulation
        Logger.section("GENERATING HOMELANDS SNAPSHOTS (NETWORK)")
        global_config_path = os.path.join("data", "config", "config.json")
        homelands_cfg = league_config.get("network", {}).copy()
        homelands_cfg["enabled"] = True
        if os.path.exists(global_config_path):
            homelands_cfg["tribe_names"] = load_json(global_config_path).get("network", {}).get("tribe_names", [])

        homelands_snapshots, homelands_constellations = run_homelands_simulation(
            archive_matches_list,
            custom_config=homelands_cfg,
            season_id=season_tag
        )
        active = sorted(t for t, m in homelands_snapshots[max(homelands_snapshots)].items() if m) if homelands_snapshots else []
        active_str = f"{len(active)} active ({', '.join(active)})" if active else "0 active"
        Logger.success(f"Homelands simulation complete: {len(homelands_snapshots)} days — {active_str}")
    except ImportError:
        Logger.info("Skipping Homelands snapshots (frog.py not found).")
    except Exception as e:
        Logger.warn(f"Homelands simulation error: {e}")

    # --- 5. EXPORT ARCHIVES ---
    Logger.section("EXPORTING ARCHIVES")
    os.makedirs(season_dir, exist_ok=True)

    ratings_path = os.path.join(season_dir, "ratings.csv")
    final_df.to_csv(ratings_path, index=False)
    Logger.step(f"ratings.csv saved in {season_dir}.")

    if archive_matches_list:
        archive_matches_list = sorted(archive_matches_list, key=lambda x: x['ELO_Sum'], reverse=True)
        for idx, m in enumerate(archive_matches_list, start=1):
            m['Rank'] = idx
    save_json(os.path.join(season_dir, "matches.json"), archive_matches_list, indent=4)
    Logger.step(f"matches.json saved in {season_dir}.")

    save_json(os.path.join(season_dir, "history.json"), player_history, indent=4)
    Logger.step(f"history.json saved in {season_dir}.")

    save_json(os.path.join(season_dir, "relations.json"), relations_map, indent=4)
    Logger.step(f"relations.json saved in {season_dir}.")

    if homelands_snapshots or homelands_constellations:
        network_payload = {
            "snapshots": homelands_snapshots,
            "constellations": homelands_constellations
        }
        save_json(os.path.join(season_dir, "network.json"), network_payload, indent=4)
        Logger.step(f"network.json saved in {season_dir}.")

    metadata = {
        "season_tag": season_tag.upper(),
        "cutoff_date": cutoff_date_str,
        "match_count": len(archive_matches_list),
        "is_legacy": is_legacy
    }
    save_json(os.path.join(season_dir, "metadata.json"), metadata, indent=4)
    Logger.step(f"metadata.json saved in {season_dir}.")

    Logger.success(f"Archives for {season_tag.upper()} successfully generated in {season_dir}!")


if __name__ == "__main__":
    main()
