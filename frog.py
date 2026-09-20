import json
import math
from collections import Counter
from itertools import combinations, permutations
from pathlib import Path

import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# CONFIGURATION
# ==============================================================================

TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"

MIN_PLAYER_GAMES = 3
MIN_JOINT_GAMES = 2
MIN_COSINE_WEIGHT = 0.18
MIN_COMMUNITY_SIZE = 5
MAX_TRIBES = 3

LOUVAIN_SEED = 42
LOUVAIN_RESOLUTION = 1.5

# Affiliation officielle
MIN_GAMES_TO_JOIN = 3
MIN_EVIDENCE = 0.20
JOIN_MARGIN = 10
SWITCH_MARGIN = 15

# Badges
LOYAL_PCT = 45
WAVERING_MARGIN = 5

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh03/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")


# ==============================================================================
# HELPERS
# ==============================================================================

def build_graph(player_counts, pair_counts):
    """Construit le graphe cumulatif de la saison."""
    graph = nx.Graph()
    active = {
        player for player, games in player_counts.items()
        if games >= MIN_PLAYER_GAMES
    }
    graph.add_nodes_from(active)

    for (player_1, player_2), joint_games in pair_counts.items():
        if player_1 not in active or player_2 not in active:
            continue
        if joint_games < MIN_JOINT_GAMES:
            continue

        weight = joint_games / math.sqrt(
            player_counts[player_1] * player_counts[player_2]
        )
        if weight >= MIN_COSINE_WEIGHT:
            graph.add_edge(player_1, player_2, weight=weight)

    return graph


def community_strength(community, graph):
    """Poids interne total d'une communauté."""
    return sum(
        data["weight"]
        for _, _, data in graph.subgraph(community).edges(data=True)
    )


def detect_communities(graph):
    """Détecte et conserve au maximum les trois communautés principales."""
    if graph.number_of_edges() == 0:
        return []

    communities = nx.community.louvain_communities(
        graph,
        weight="weight",
        resolution=LOUVAIN_RESOLUTION,
        seed=LOUVAIN_SEED,
    )
    communities = [
        set(community)
        for community in communities
        if len(community) >= MIN_COMMUNITY_SIZE
    ]
    communities.sort(
        key=lambda community: community_strength(community, graph),
        reverse=True,
    )
    return communities[:MAX_TRIBES]


def overlap_score(old_members, new_members):
    """Part de l'ancienne tribu retrouvée dans la nouvelle communauté."""
    if not old_members:
        return 0.0
    return len(set(old_members) & set(new_members)) / len(set(old_members))


def name_communities(communities, previous_cores):
    """
    Donne aux nouvelles communautés les noms A/B/C en maximisant globalement
    leur continuité avec la veille.
    """
    if not communities:
        return {}

    best_mapping = None
    best_score = -1.0

    for labels in permutations(TARGET_TRIBES, len(communities)):
        mapping = dict(zip(labels, communities))
        score = sum(
            overlap_score(previous_cores.get(label, set()), community)
            for label, community in mapping.items()
        )
        if score > best_score:
            best_score = score
            best_mapping = mapping

    return best_mapping


def player_affinities(player, tribe_cores, graph):
    """Calcule les pourcentages d'affinité envers les noyaux des tribus."""
    raw_scores = {}

    for tribe in TARGET_TRIBES:
        core = tribe_cores.get(tribe, set())
        total = sum(
            graph[player][member]["weight"]
            for member in core
            if member != player and graph.has_edge(player, member)
        )
        raw_scores[tribe] = total / math.sqrt(len(core)) if core else 0.0

    evidence = sum(raw_scores.values())
    percentages = {
        tribe: (100 * raw_scores[tribe] / evidence if evidence else 0.0)
        for tribe in TARGET_TRIBES
    }
    return percentages, evidence


def choose_tribe(previous_tribe, games, percentages, evidence, tribe_cores):
    """Applique une hystérésis simple à l'unique affiliation officielle."""
    active_tribes = [tribe for tribe in TARGET_TRIBES if tribe in tribe_cores]
    if not active_tribes or games < MIN_GAMES_TO_JOIN or evidence < MIN_EVIDENCE:
        return UNALIGNED_LABEL

    ranked = sorted(active_tribes, key=lambda tribe: percentages[tribe], reverse=True)
    best = ranked[0]
    second_pct = percentages[ranked[1]] if len(ranked) > 1 else 0.0

    if previous_tribe not in tribe_cores:
        previous_tribe = UNALIGNED_LABEL

    if previous_tribe == UNALIGNED_LABEL:
        return best if percentages[best] - second_pct >= JOIN_MARGIN else UNALIGNED_LABEL

    if best == previous_tribe:
        return previous_tribe

    if percentages[best] - percentages[previous_tribe] >= SWITCH_MARGIN:
        return best

    return previous_tribe


def player_status(player, tribe, percentages, tribe_cores):
    """Le badge décrit l'affiliation sans la modifier."""
    if tribe == UNALIGNED_LABEL:
        return None
    if player in tribe_cores.get(tribe, set()):
        return "Core"

    other_scores = [
        percentages[other]
        for other in tribe_cores
        if other != tribe
    ]
    margin = percentages[tribe] - max(other_scores, default=0.0)

    if margin <= WAVERING_MARGIN:
        return "Wavering"
    if percentages[tribe] >= LOYAL_PCT:
        return "Loyalist"
    return "Affiliate"


# ==============================================================================
# LOAD DATA
# ==============================================================================

config_path = CONFIG_PATH if CONFIG_PATH.exists() else Path("data/config.json")
with open(config_path, "r", encoding="utf-8") as file:
    config_data = json.load(file)

json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as file:
    matches = json.load(file)

matches_data = []
for match in matches:
    raw_date = (
        match.get("Date")
        or match.get("date")
        or match.get("date_closed")
        or ""
    )
    date = str(raw_date)[:10] if raw_date else "1970-01-01"
    players = [
        player.get("name")
        for player in match.get("players", [])
        if player.get("name")
    ]
    if players:
        matches_data.append({"date": date, "players": players})

sorted_dates = sorted({match["date"] for match in matches_data})
matches_by_date = {date: [] for date in sorted_dates}
for match in matches_data:
    matches_by_date[match["date"]].append(match)


# ==============================================================================
# DAILY ANALYSIS
# ==============================================================================

snapshots = {}
player_counts = Counter()
pair_counts = Counter()
previous_cores = {}
previous_assignments = {}

for date in sorted_dates:
    # Mise à jour cumulative : tous les matchs gardent le même poids.
    for match in matches_by_date[date]:
        players = sorted(set(match["players"]))
        player_counts.update(players)
        pair_counts.update(combinations(players, 2))

    graph = build_graph(player_counts, pair_counts)
    communities = detect_communities(graph)
    tribe_cores = name_communities(communities, previous_cores)

    snapshot_players = []
    current_assignments = {}
    tribe_summary = Counter()

    for player, games in sorted(
        player_counts.items(),
        key=lambda item: (-item[1], item[0].lower()),
    ):
        percentages, evidence = player_affinities(player, tribe_cores, graph)
        tribe = choose_tribe(
            previous_assignments.get(player, UNALIGNED_LABEL),
            games,
            percentages,
            evidence,
            tribe_cores,
        )
        status = player_status(player, tribe, percentages, tribe_cores)

        current_assignments[player] = tribe
        tribe_summary[tribe] += 1

        snapshot_players.append({
            "name": player,
            "games": games,
            "main_tribe": tribe,
            "scores": {
                target: {
                    "pct": round(percentages[target]),
                    "status": status if target == tribe else None,
                }
                for target in TARGET_TRIBES
            },
        })

    snapshots[date] = {
        "summary": {
            tribe: tribe_summary.get(tribe, 0)
            for tribe in TARGET_TRIBES + [UNALIGNED_LABEL]
        },
        "players": snapshot_players,
    }

    previous_cores = {
        tribe: set(core)
        for tribe, core in tribe_cores.items()
    }
    previous_assignments = current_assignments


# ==============================================================================
# RENDER EXISTING FRONT-END
# ==============================================================================

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.globals["config"] = config_data
template = env.get_template(TEMPLATE_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
    file.write(template.render(
        active_section="frog",
        snapshots_json=json.dumps(snapshots, ensure_ascii=False),
        dates_json=json.dumps(sorted_dates, ensure_ascii=False),
    ))

print(f"Analysis successful: {len(sorted_dates)} dates calculated.")
