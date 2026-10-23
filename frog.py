"""
frog.py — Dynamic player homelands simulation module.

This module processes season match history to compute temporal homeland 
snapshots, player affiliations, tier classifications, and direct player 
connections. Designed to be imported and executed directly within main.py 
or run autonomously for testing.
"""

from collections import Counter
from datetime import date
from itertools import combinations
import json
import math
import os
import random
from pathlib import Path
import statistics
import sys

from jinja2 import Environment, FileSystemLoader
import networkx as nx

# Ensure deterministic seed for Python execution
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ==============================================================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==============================================================================

UNALIGNED = None

DEFAULT_CONFIG = {
    "MAX_TRIBES": 5,
    "MIN_TRIBE_CREATION_SIZE": 6,
    "MIN_TRIBE_SURVIVAL": 4,
    "MIN_GAMES_FLOOR": 3,
    "DYNAMIC_RATIO": 2.0,
    "STICKINESS": 1.5,
    "MAX_DAILY_TRANSFERS": 3,
    "INACTIVITY_LIMIT_DAYS": 21,
    "PILLAR_PERCENTILE": 90,
    "SATELLITE_PERCENTILE": 60,
    "PILLAR_MIN": 1,
    "PILLAR_MAX": 6,
    "SATELLITE_MAX": 10,
    "DECAY_RATE": 0.95,
    "NEW_MATCH_WEIGHT": 1.0,
    "MIN_EDGE_WEIGHT": 0.1,
    "RESOLUTION": 1.2,
    "tribe_names": ["TEA", "BAG", "SWORD", "COINS", "HAMMER", "CROSSBOW", "BOOT"]
}


# ==============================================================================
# 🧩 ALGORITHM HELPER FUNCTIONS
# ==============================================================================

def min_games_required(player_games: Counter, floor: int, ratio: float) -> int:
    """Calculate the minimum number of games required for eligibility."""
    median = statistics.median(player_games.values()) if player_games else 0
    return max(floor, math.ceil(median * ratio))


def weight_by_tribe(G: nx.Graph, roster: dict, p: str) -> Counter:
    """Calculate player p's weight distribution towards each homeland."""
    weights = Counter()
    for n in G.neighbors(p):
        tribe = roster.get(n, UNALIGNED)
        if tribe is not UNALIGNED:
            weights[tribe] += G[p][n]["weight"]
    return weights


def is_clearly_apart(G: nx.Graph, roster: dict, comm: set, stickiness: float) -> bool:
    """Check if a community has strong enough internal cohesion to form a homeland."""
    inside = outside = 0.0
    for p in comm:
        for n in G.neighbors(p):
            w = G[p][n]["weight"]
            if n in comm:
                inside += w
            elif roster.get(p) is not UNALIGNED and roster.get(n) == roster.get(p):
                outside += w
    return inside > stickiness * outside


def compass(
    G: nx.Graph,
    roster: dict,
    eligible: list,
    ever_used_names: set,
    cfg: dict,
    tribe_names_pool: list,
) -> tuple[dict, set]:
    """Identify player communities and assign homeland names."""
    if not eligible:
        return {}, set()

    comms = nx.community.louvain_communities(
        G.subgraph(eligible),
        weight="weight",
        resolution=cfg["RESOLUTION"],
        seed=42
    )
    comms.sort(key=lambda c: (-len(c), sorted(c)))

    members = {}
    for p, t in roster.items():
        if t is not UNALIGNED:
            members.setdefault(t, set()).add(p)

    overlaps = sorted(
        [
            (len(c & m), i, t)
            for i, c in enumerate(comms)
            for t, m in members.items()
        ],
        key=lambda x: (-x[0], x[1], x[2]),
    )
    name_of = {}
    for overlap, i, t in overlaps:
        if overlap > 0 and i not in name_of and t not in name_of.values():
            name_of[i] = t

    currently_free = [n for n in tribe_names_pool if n not in members]
    currently_free.sort(
        key=lambda n: (n in ever_used_names, tribe_names_pool.index(n) if n in tribe_names_pool else 999)
    )

    available_slots = max(0, cfg["MAX_TRIBES"] - len(members))
    free = currently_free[:available_slots]
    founded = set()
    for i, c in enumerate(comms):
        if (
            i not in name_of
            and len(c) >= cfg["MIN_TRIBE_CREATION_SIZE"]
            and free
            and is_clearly_apart(G, roster, c, cfg["STICKINESS"])
        ):
            chosen_name = free.pop(0)
            name_of[i] = chosen_name
            founded.add(chosen_name)
            ever_used_names.add(chosen_name)

    target = {p: name_of[i] for i, c in enumerate(comms) if i in name_of for p in c}
    return target, founded


def apply_compass(G: nx.Graph, roster: dict, target: dict, founded: set, cfg: dict) -> None:
    """Apply target assignments and player transfers to the roster."""
    moves, switches = [], []

    for p, t in target.items():
        current = roster.get(p, UNALIGNED)
        if current == t:
            continue

        if t in founded:
            moves.append((p, t))
        elif current is UNALIGNED:
            w = weight_by_tribe(G, roster, p)
            if not w or w[t] == max(w.values()):
                moves.append((p, t))
        else:
            w = weight_by_tribe(G, roster, p)
            if w[t] > cfg["STICKINESS"] * w[current]:
                switches.append((w[t] - w[current], p, t))

    switches.sort(reverse=True)
    moves += [(p, t) for _, p, t in switches[: cfg["MAX_DAILY_TRANSFERS"]]]

    for p, t in moves:
        roster[p] = t


def prune_inactive(roster: dict, last_active: dict, current_date: str, cfg: dict) -> None:
    """Remove players who have been inactive beyond the inactivity threshold."""
    inactivity_limit = cfg["INACTIVITY_LIMIT_DAYS"]
    if inactivity_limit is None:
        return
    cur = date.fromisoformat(current_date)

    for p, t in roster.items():
        if t is UNALIGNED:
            continue
        last = last_active.get(p)
        if last is None or (cur - date.fromisoformat(last)).days > inactivity_limit:
            roster[p] = UNALIGNED


def dissolve_small_tribes(roster: dict, cfg: dict) -> None:
    """Dissolve homelands that drop below the minimum survival threshold."""
    counts = Counter(t for t in roster.values() if t is not UNALIGNED)
    for tribe, n in counts.items():
        if n < cfg["MIN_TRIBE_SURVIVAL"]:
            for p, t in list(roster.items()):
                if t == tribe:
                    roster[p] = UNALIGNED


def tribe_core_scores(G: nx.Graph, members: list) -> dict:
    """Calculate weighted-degree centrality within own tribe subgraph."""
    n = len(members)
    if n < 2:
        return {}
    H = G.subgraph(members)
    return {
        p: sum(d["weight"] for _, _, d in H.edges(p, data=True)) / (n - 1)
        for p in members
    }


def classify_tribe_tiers(scores: dict, cfg: dict) -> tuple[set, set]:
    """Classify players into pillars (core) and satellites based on relative scores."""
    items = sorted(scores.items(), key=lambda x: -x[1])
    values = [v for _, v in items]

    if not values:
        return set(), set()

    if len(values) >= 2:
        q = statistics.quantiles(values, n=100)
        pillar_cut = q[cfg["PILLAR_PERCENTILE"] - 1]
        satellite_cut = q[cfg["SATELLITE_PERCENTILE"] - 1]
    else:
        pillar_cut = satellite_cut = values[0]

    pillars = [p for p, v in items if v >= pillar_cut]
    if len(pillars) < cfg["PILLAR_MIN"]:
        pillars = [p for p, _ in items[: cfg["PILLAR_MIN"]]]
    elif len(pillars) > cfg["PILLAR_MAX"]:
        pillars = [p for p, _ in items[: cfg["PILLAR_MAX"]]]

    pillar_set = set(pillars)

    satellites = [
        p for p, v in items if v >= satellite_cut and p not in pillar_set
    ]
    satellites = satellites[: cfg["SATELLITE_MAX"]]

    return pillar_set, set(satellites)


# ==============================================================================
# 🚀 CORE SIMULATION FUNCTION
# ==============================================================================

def run_homelands_simulation(matches: list, custom_config: dict = None, season_id: str = "default") -> dict:
    """
    Executes the homelands simulation over the provided matches data.

    Args:
        matches (list): List of match dicts containing date and player list.
        custom_config (dict, optional): Overrides for simulation parameters and tribe_names.
        season_id (str, optional): Seed string for deterministic RNG pooling.

    Returns:
        dict: Snapshots dictionary mapping dates to active homelands, layouts, 
              members grouped by tribe, unaligned players, and player connections.
              Returns empty dict if parameters/matches are missing or empty.
    """
    if matches is None:
        return {}
    if hasattr(matches, "empty") and matches.empty:
        return {}
    if not hasattr(matches, "empty") and not matches:
        return {}

    # Merge configuration
    cfg = DEFAULT_CONFIG.copy()
    if custom_config:
        cfg.update(custom_config)

    tribe_names_pool = cfg.get("tribe_names", []).copy()

    # Group matches strictly by date
    matches_by_date = {}
    for m in matches:
        date_str = str(
            m.get("Date_Closed") or m.get("date_closed") or m.get("Date") or m.get("date") or ""
        )[:10]
        players = list(
            dict.fromkeys(p.get("name") for p in m.get("players", []) if p.get("name"))
        )
        if date_str and players:
            matches_by_date.setdefault(date_str, []).append(players)

    if not matches_by_date or not tribe_names_pool:
        return {}

    sorted_dates = sorted(matches_by_date)

    # Deterministic RNG for tribe name order
    rng = random.Random(season_id)
    rng.shuffle(tribe_names_pool)

    edge_weights = Counter()
    player_games = Counter()
    last_active = {}
    roster = {}
    snapshots = {}
    ever_used_names = set()

    for d in sorted_dates:
        # 1. Decay edge weights & accumulate daily matches
        for pair in edge_weights:
            edge_weights[pair] *= cfg["DECAY_RATE"]

        for players in matches_by_date[d]:
            for p in players:
                player_games[p] += 1
                last_active[p] = d
                roster.setdefault(p, UNALIGNED)
            for p1, p2 in combinations(sorted(set(players)), 2):
                edge_weights[(p1, p2)] += cfg["NEW_MATCH_WEIGHT"]

        G = nx.Graph()
        for (p1, p2), w in edge_weights.items():
            if w >= cfg["MIN_EDGE_WEIGHT"]:
                G.add_edge(p1, p2, weight=w)

        min_games = min_games_required(
            player_games, cfg["MIN_GAMES_FLOOR"], cfg["DYNAMIC_RATIO"]
        )

        # 2. Compass clustering & player transfers
        eligible = [p for p in G.nodes() if player_games[p] >= min_games]
        target, founded = compass(G, roster, eligible, ever_used_names, cfg, tribe_names_pool)
        apply_compass(G, roster, target, founded, cfg)

        # 3. Dissolutions & inactivity pruning
        dissolve_small_tribes(roster, cfg)
        prune_inactive(roster, last_active, d, cfg)
        dissolve_small_tribes(roster, cfg)

        active_tribes = sorted({t for t in roster.values() if t is not UNALIGNED})
        tribe_labels = {t: t for t in tribe_names_pool}

        # 4. Core scores & tier classification (Pillars / Satellites)
        tribe_layout = {}
        for t in active_tribes:
            members = [p for p, tribe in roster.items() if tribe == t]
            t_scores = tribe_core_scores(G, members)
            pillars, satellites = classify_tribe_tiers(t_scores, cfg)
            tribe_layout[t] = {
                "pillars": list(pillars),
                "satellites": list(satellites),
            }

        # 5. Build lightweight daily snapshot (Macro & Micro connections)
        summary = {t: 0 for t in tribe_names_pool}
        summary[UNALIGNED] = 0

        members_by_tribe = {t: [] for t in active_tribes}
        unaligned_players = []

        for p, games in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
            main_tribe = roster[p]
            if main_tribe in active_tribes:
                summary[main_tribe] += 1
                role = "member"
                if p in tribe_layout.get(main_tribe, {}).get("pillars", []):
                    role = "pillar"
                elif p in tribe_layout.get(main_tribe, {}).get("satellites", []):
                    role = "satellite"

                members_by_tribe[main_tribe].append({
                    "name": p,
                    "games": games,
                    "role": role
                })
            else:
                summary[UNALIGNED] += 1
                unaligned_players.append({
                    "name": p,
                    "games": games
                })

        # Extract direct player connections for ego-networks / mini-constellations
        player_connections = {}
        for p in player_games:
            neighbors = []
            if p in G:
                for n in G.neighbors(p):
                    w = G[p][n]["weight"]
                    neighbors.append({
                        "name": n,
                        "weight": round(w, 2),
                        "tribe": roster.get(n, UNALIGNED)
                    })
            neighbors.sort(key=lambda x: -x["weight"])
            player_connections[p] = neighbors

        snapshots[d] = {
            "active_tribes": active_tribes,
            "tribe_labels": tribe_labels,
            "summary": summary,
            "tribe_layout": tribe_layout,
            "members_by_tribe": members_by_tribe,
            "unaligned": unaligned_players,
            "player_connections": player_connections,
        }

    return snapshots


# ==============================================================================
# 🖥️ STANDALONE CLI EXECUTION & HTML RENDERING
# ==============================================================================

if __name__ == "__main__":
    CONFIG_PATH = Path("data/config/config.json")
    DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh01/matches.json")
    TEMPLATE_DIR = "templates"
    TEMPLATE_FILE = "frog.html"
    OUTPUT_FILE = Path("frog.html")
    PAGES_CONTENT_PATH = Path("data/config/pages_content.json")

    # Load configuration
    config_data = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config_data = json.load(f)

    pages_content = {}
    if PAGES_CONTENT_PATH.exists():
        with open(PAGES_CONTENT_PATH, "r", encoding="utf-8") as f:
            pages_content = json.load(f)

    # Locate matches file
    matches_file = DEFAULT_MATCHES_PATH
    if not matches_file.exists():
        archives = list(Path("data/rdl/archives").rglob("matches.json"))
        matches_file = archives[0] if archives else Path("matches.json")

    if not matches_file.exists():
        print(f"❌ Error: Matches file not found at {matches_file}")
        sys.exit(1)

    with open(matches_file, "r", encoding="utf-8") as f:
        matches_data = json.load(f)

    current_season_id = matches_file.parent.name if matches_file.exists() else "default"
    league_network_cfg = config_data.get("network", {})

    # Run simulation
    snapshots = run_homelands_simulation(matches_data, custom_config=league_network_cfg, season_id=current_season_id)
    sorted_dates = sorted(snapshots.keys())

    # Render HTML template if available
    if (Path(TEMPLATE_DIR) / TEMPLATE_FILE).exists() and sorted_dates:
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template(TEMPLATE_FILE)

        html_content = template.render(
            config=config_data,
            page_id="homelands",
            section_id="homelands",
            active_section="homelands",
            path_prefix="",
            dates_json=json.dumps(sorted_dates),
            snapshots_json=json.dumps(snapshots),
            **pages_content.get("homelands", {}),
        )

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ File {OUTPUT_FILE} successfully generated ({len(snapshots)} dates).")
    else:
        print(f"⚠️ Simulation complete, but template or dates missing. Generated {len(snapshots)} snapshots.")
