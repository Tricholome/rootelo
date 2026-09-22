"""
frog.py — Dynamic player homelands simulation over a season.
"""

import json
import math
import os
import random
import statistics
import sys
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

import networkx as nx
from jinja2 import Environment, FileSystemLoader

# Ensure deterministic seed for Python execution
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ==============================================================================
# ⚙️ CONFIGURATION
# ==============================================================================

# --- Homelands ---
MAX_TRIBES = 5                 # Maximum concurrent active homelands
MIN_TRIBE_CREATION_SIZE = 6    # Minimum players required to found a new homeland
MIN_TRIBE_SURVIVAL = 4         # Minimum players required for a homeland to survive

# --- Eligibility ---
MIN_GAMES_FLOOR = 3            # Absolute floor for games required
DYNAMIC_RATIO = 2.0            # Threshold = max(floor, ratio * global median)

# --- Stability ---
STICKINESS = 1.5               # Affinity ratio required to switch homeland
MAX_DAILY_TRANSFERS = 3        # Maximum daily transfers allowed
INACTIVITY_LIMIT_DAYS = 21     # Days of inactivity before a player is unaligned

# --- Edge Weights ---
# All matches count equally, whenever they were played (no decay): a "tribe"
# reflects who a player has played with across the whole season, not just recently.
NEW_MATCH_WEIGHT = 1.0         # Weight added for each match played
MIN_EDGE_WEIGHT = 0.1          # Edge weight threshold below which edges are ignored

UNALIGNED_LABEL = "-"

# --- File Paths ---
CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh03/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")
PAGES_CONTENT_PATH = Path("data/config/pages_content.json")

# --- Root Items used as Homeland Names ---
ROOT_ITEMS_POOL = ["TEA", "BAG", "SWORD", "COINS", "HAMMER", "CROSSBOW", "BOOT"]

matches_file = DEFAULT_MATCHES_PATH
if not matches_file.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    matches_file = archives[0] if archives else Path("matches.json")

season_id = matches_file.parent.name if matches_file.exists() else "default"
rng = random.Random(season_id)

TRIBE_NAMES_POOL = ROOT_ITEMS_POOL.copy()
rng.shuffle(TRIBE_NAMES_POOL)


# ==============================================================================
# 🧩 ALGORITHM HELPER FUNCTIONS
# ==============================================================================

def min_games_required(player_games):
    """Calculate the minimum number of games required for eligibility."""
    median = statistics.median(player_games.values()) if player_games else 0
    return max(MIN_GAMES_FLOOR, math.ceil(median * DYNAMIC_RATIO))


def weight_by_tribe(G, roster, p):
    """Calculate player p's weight distribution towards each homeland."""
    weights = Counter()
    for n in G.neighbors(p):
        tribe = roster.get(n, UNALIGNED_LABEL)
        if tribe != UNALIGNED_LABEL:
            weights[tribe] += G[p][n]["weight"]
    return weights


def is_clearly_apart(G, roster, comm):
    """Check if a community has strong enough internal cohesion to form a homeland."""
    inside = outside = 0.0
    for p in comm:
        for n in G.neighbors(p):
            w = G[p][n]["weight"]
            if n in comm:
                inside += w
            elif roster[p] != UNALIGNED_LABEL and roster[n] == roster[p]:
                outside += w
    return inside > STICKINESS * outside


def compass(G, roster, eligible, ever_used_names):
    """Identify player communities and assign homeland names."""
    comms = nx.community.louvain_communities(G.subgraph(eligible), weight="weight", seed=42)
    comms.sort(key=lambda c: (-len(c), sorted(c)))

    members = {}
    for p, t in roster.items():
        if t != UNALIGNED_LABEL:
            members.setdefault(t, set()).add(p)

    overlaps = sorted(
        ((len(c & m), i, t) for i, c in enumerate(comms) for t, m in members.items()),
        key=lambda x: (-x[0], x[1], x[2])
    )
    name_of = {}
    for overlap, i, t in overlaps:
        if overlap > 0 and i not in name_of and t not in name_of.values():
            name_of[i] = t

    currently_free = [n for n in TRIBE_NAMES_POOL if n not in members]
    currently_free.sort(key=lambda n: (n in ever_used_names, TRIBE_NAMES_POOL.index(n)))

    available_slots = max(0, MAX_TRIBES - len(members))
    free = currently_free[:available_slots]
    founded = set()
    for i, c in enumerate(comms):
        if i not in name_of and len(c) >= MIN_TRIBE_CREATION_SIZE and free and is_clearly_apart(G, roster, c):
            chosen_name = free.pop(0)
            name_of[i] = chosen_name
            founded.add(chosen_name)
            ever_used_names.add(chosen_name)

    target = {p: name_of[i] for i, c in enumerate(comms) if i in name_of for p in c}
    return target, founded


def apply_compass(G, roster, target, founded):
    """Apply target assignments and player transfers to the roster."""
    moves, switches = [], []
    for p, t in target.items():
        current = roster[p]
        if current == t:
            continue

        if t in founded:
            moves.append((p, t))
        elif current == UNALIGNED_LABEL:
            w = weight_by_tribe(G, roster, p)
            if not w or w[t] == max(w.values()):
                moves.append((p, t))
        else:
            w = weight_by_tribe(G, roster, p)
            if w[t] > STICKINESS * w[current]:
                switches.append((w[t] - w[current], p, t))

    switches.sort(reverse=True)
    moves += [(p, t) for _, p, t in switches[:MAX_DAILY_TRANSFERS]]

    for p, t in moves:
        roster[p] = t


def prune_inactive(roster, last_active, current_date):
    """Remove players who have been inactive beyond the inactivity threshold."""
    if INACTIVITY_LIMIT_DAYS is None:
        return
    cur = date.fromisoformat(current_date)
    for p, t in roster.items():
        if t == UNALIGNED_LABEL:
            continue
        last = last_active.get(p)
        if last is None or (cur - date.fromisoformat(last)).days > INACTIVITY_LIMIT_DAYS:
            roster[p] = UNALIGNED_LABEL


def dissolve_small_tribes(roster):
    """Dissolve homelands that drop below the minimum survival threshold."""
    counts = Counter(t for t in roster.values() if t != UNALIGNED_LABEL)
    for tribe, n in counts.items():
        if n < MIN_TRIBE_SURVIVAL:
            for p, t in list(roster.items()):
                if t == tribe:
                    roster[p] = UNALIGNED_LABEL


def tribe_core_scores(G, members):
    """Weighted-degree centrality of each member within their own tribe's
    subgraph: how strongly, on average, a player is tied to their tribe-mates.
    This is purely descriptive (computed after assignment) and never feeds
    back into compass/apply_compass, so it never influences who belongs where."""
    n = len(members)
    if n < 2:
        return {}
    H = G.subgraph(members)
    return {
        p: sum(d["weight"] for _, _, d in H.edges(p, data=True)) / (n - 1)
        for p in members
    }


def player_scores(G, roster, p, active_tribes):
    """Calculate affiliation percentage and title status for a player across all homelands."""
    scores = {t: {"pct": 0, "status": None} for t in TRIBE_NAMES_POOL}
    if p not in G or G.degree(p) == 0:
        return scores

    by_tribe, total = Counter(), 0.0
    for n in G.neighbors(p):
        w = G[p][n]["weight"]
        total += w
        by_tribe[roster.get(n, UNALIGNED_LABEL)] += w

    pcts = {t: round(100 * by_tribe[t] / total) for t in TRIBE_NAMES_POOL}

    main = roster.get(p, UNALIGNED_LABEL)
    main_pct = pcts.get(main, 0)

    other_active_pcts = [pcts[t] for t in active_tribes if t != main]
    best_other = max(other_active_pcts, default=0)
    diff = abs(main_pct - best_other)

    for t in TRIBE_NAMES_POOL:
        status = None
        if t == main:
            if diff <= 3 and len(active_tribes) > 1 and best_other > 0:
                status = "Favoring"
            elif pcts[t] >= 65:
                status = "Partisan"
            elif pcts[t] >= 50:
                status = "Squire"
            else:
                status = "Friend"
        scores[t] = {"pct": pcts[t], "status": status}
    return scores


# ==============================================================================
# 🚀 DATA LOADING
# ==============================================================================

config_path = CONFIG_PATH
if not config_path.exists():
    configs = list(Path(".").rglob("config.json"))
    if configs:
        config_path = configs[0]

pages_content_path = PAGES_CONTENT_PATH
if not pages_content_path.exists():
    found = list(Path(".").rglob("pages_content.json"))
    if found:
        pages_content_path = found[0]

pages_content = {}
if pages_content_path.exists():
    with open(pages_content_path, "r", encoding="utf-8") as f:
        pages_content = json.load(f)

config_data = {}
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    json_path = archives[0] if archives else Path("matches.json")

if not json_path.exists():
    print(f"❌ Error: Matches file not found at {json_path}")
    sys.exit(1)

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

matches_by_date = {}
for m in matches:
    date_str = str(m.get("Date") or m.get("date") or m.get("date_closed") or "")[:10]
    players = list(dict.fromkeys(p.get("name") for p in m.get("players", []) if p.get("name")))
    if date_str and players:
        matches_by_date.setdefault(date_str, []).append(players)

sorted_dates = sorted(matches_by_date)


# ==============================================================================
# 🧠 SIMULATION LOOP
# ==============================================================================

edge_weights = Counter()
player_games = Counter()
last_active = {}
roster = {}
snapshots = {}
ever_used_names = set()

for d in sorted_dates:
    # 1. Parse the day's matches (all matches, past or present, count equally)
                             
                                        

    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
            last_active[p] = d
            roster.setdefault(p, UNALIGNED_LABEL)
        for p1, p2 in combinations(sorted(set(players)), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    G = nx.Graph()
    for (p1, p2), w in edge_weights.items():
        if w >= MIN_EDGE_WEIGHT:
            G.add_edge(p1, p2, weight=w)

    min_games = min_games_required(player_games)

    # 2. Run compass algorithm and apply transfers
    eligible = [p for p in G.nodes() if player_games[p] >= min_games]
    target, founded = compass(G, roster, eligible, ever_used_names)
    apply_compass(G, roster, target, founded)

    # 3. Handle dissolutions and inactivity pruning
    dissolve_small_tribes(roster)
    prune_inactive(roster, last_active, d)
    dissolve_small_tribes(roster)

    active_tribes = sorted({t for t in roster.values() if t != UNALIGNED_LABEL})
    tribe_labels = {t: t for t in TRIBE_NAMES_POOL}

    # 4. Core players ("piliers") — who each tribe currently gravitates around
    core_scores = {}
    for t in active_tribes:
        members = [p for p, tt in roster.items() if tt == t]
        core_scores.update(tribe_core_scores(G, members))

    # 5. Generate snapshot
    summary = {t: 0 for t in TRIBE_NAMES_POOL + [UNALIGNED_LABEL]}
    snapshot_players = []
    for p, games in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        main_tribe = roster[p]
        summary[main_tribe] += 1
        snapshot_players.append({
            "name": p,
            "games": games,
            "main_tribe": main_tribe,
            "core_score": round(core_scores.get(p, 0.0), 3),
            "scores": player_scores(G, roster, p, active_tribes),
        })

    snapshots[d] = {
        "active_tribes": active_tribes,
        "tribe_labels": tribe_labels,
        "summary": summary,
        "players": snapshot_players,
    }


# ==============================================================================
# 🎨 HTML GENERATION
# ==============================================================================

if (Path(TEMPLATE_DIR) / TEMPLATE_FILE).exists():
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
