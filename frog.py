from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
import math
import random
import statistics

import networkx as nx

UNALIGNED = None

DEFAULT_CONFIG = {
    "MAX_TRIBES": 5,
    "MIN_TRIBE_CREATION_SIZE": 6,
    "MAX_INITIAL_FOUNDERS": 8,
    "MIN_TRIBE_SURVIVAL": 4,
    "MIN_REUSE_OVERLAP": 3,
    "MIN_GAMES_FLOOR": 3,
    "DYNAMIC_RATIO": 1.5,
    "STICKINESS": 1.5,
    "MIN_JOIN_AFFINITY": 0.40,
    "DISSOLUTION_GRACE_DAYS": 2,
    "MAX_DAILY_TRANSFERS": 3,
    "INACTIVITY_LIMIT_DAYS": 21,
    "PARTNERS_SCALE_FACTOR": 2.5,
    "DECAY_RATE": 0.95,
    "NEW_MATCH_WEIGHT": 1.0,
    "MIN_EDGE_WEIGHT": 0.1,
    "RESOLUTION": 1.25,
}


def min_games_required(player_games: Counter, floor: int, ratio: float) -> int:
    median = statistics.median(player_games.values()) if player_games else 0
    return max(floor, math.ceil(median * ratio))


def is_player_active(p: str, last_active: dict, current_date: str, limit_days: int) -> bool:
    if limit_days is None:
        return True
    last = last_active.get(p)
    if last is None:
        return False
    return (date.fromisoformat(current_date) - date.fromisoformat(last)).days <= limit_days


def weight_by_tribe(G: nx.Graph, roster: dict, p: str) -> Counter:
    weights = Counter()
    if p not in G:
        return weights
    for n in G.neighbors(p):
        tribe = roster.get(n, UNALIGNED)
        if tribe is not UNALIGNED:
            weights[tribe] += G[p][n]["weight"]
    return weights


def is_clearly_apart(G: nx.Graph, roster: dict, comm: set, stickiness: float) -> bool:
    inside = outside = 0.0
    for p in sorted(comm):
        if p not in G:
            continue
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
    last_tribe: dict,
    ever_used_names: set,
    cfg: dict,
    tribe_names_pool: list,
) -> tuple[dict, set]:
    if not eligible:
        return {}, set()

    comms = nx.community.louvain_communities(
        G.subgraph(eligible),
        weight="weight",
        resolution=cfg["RESOLUTION"],
        seed=42,
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
        if overlap >= 2 and i not in name_of and t not in name_of.values():
            name_of[i] = t

    available_slots = max(0, cfg["MAX_TRIBES"] - len(members))
    min_reuse = cfg["MIN_REUSE_OVERLAP"]

    unused_names = [n for n in tribe_names_pool if n not in ever_used_names and n not in members]
    dissolved_names = [n for n in tribe_names_pool if n in ever_used_names and n not in members]

    founded = set()
    for i, c in enumerate(comms):
        if len(founded) >= available_slots:
            break
        if (
            i in name_of
            or len(c) < cfg["MIN_TRIBE_CREATION_SIZE"]
            or not is_clearly_apart(G, roster, c, cfg["STICKINESS"])
        ):
            continue

        ex_counts = Counter(
            last_tribe.get(p) for p in c if last_tribe.get(p) in dissolved_names
        )
        revive_candidates = sorted(
            [
                (count, t)
                for t, count in ex_counts.items()
                if t not in name_of.values() and count >= min_reuse
            ],
            key=lambda x: (-x[0], tribe_names_pool.index(x[1]) if x[1] in tribe_names_pool else 999),
        )

        chosen_name = None
        if revive_candidates:
            chosen_name = revive_candidates[0][1]
        elif unused_names:
            chosen_name = unused_names.pop(0)

        if chosen_name:
            name_of[i] = chosen_name
            founded.add(chosen_name)
            ever_used_names.add(chosen_name)

    target = {p: name_of[i] for i, c in enumerate(comms) if i in name_of for p in sorted(c)}
    return target, founded


def apply_compass(G: nx.Graph, roster: dict, target: dict, founded: set, cfg: dict) -> None:
    moves, switches = [], []
    min_affinity = cfg.get("MIN_JOIN_AFFINITY", 0.40)
    max_founders = cfg.get("MAX_INITIAL_FOUNDERS", 8)

    # 1. Fondations (limitées aux membres les plus centraux pour lisser les scissions)
    for t in sorted(founded):
        candidates = [p for p, target_t in target.items() if target_t == t]
        candidates_set = set(candidates)
        scored = []
        for p in candidates:
            internal_w = sum(
                G[p][n]["weight"] for n in G.neighbors(p) if n in candidates_set
            ) if p in G else 0.0
            scored.append((-internal_w, p))
        scored.sort()
        for _, p in scored[:max_founders]:
            moves.append((p, t))

    moved_players = {p for p, _ in moves}

    # 2. Recrutements et transferts vers les homelands existantes
    for p, t in target.items():
        if p in moved_players or t in founded:
            continue
        current = roster.get(p, UNALIGNED)
        if current == t:
            continue

        w = weight_by_tribe(G, roster, p)
        total_w = sum(w.values())

        if current is UNALIGNED:
            if total_w > 0 and w[t] == max(w.values()) and (w[t] / total_w) >= min_affinity:
                moves.append((p, t))
        else:
            if w[t] > cfg["STICKINESS"] * w[current]:
                switches.append((w[t] - w[current], p, t))

    switches.sort(reverse=True)
    moves += [(p, t) for _, p, t in switches[: cfg["MAX_DAILY_TRANSFERS"]]]

    for p, t in moves:
        roster[p] = t


def prune_inactive(roster: dict, last_active: dict, current_date: str, cfg: dict) -> None:
    limit_days = cfg["INACTIVITY_LIMIT_DAYS"]
    if limit_days is None:
        return

    for p, t in list(roster.items()):
        if t is not UNALIGNED and not is_player_active(p, last_active, current_date, limit_days):
            roster[p] = UNALIGNED


def dissolve_small_tribes(
    roster: dict, under_survival_days: Counter, cfg: dict, immediate: bool = False
) -> None:
    counts = Counter(t for t in roster.values() if t is not UNALIGNED)
    grace_days = 1 if immediate else max(1, cfg.get("DISSOLUTION_GRACE_DAYS", 2))

    for t in list(under_survival_days):
        if t not in counts:
            del under_survival_days[t]

    for tribe, n in counts.items():
        if n < cfg["MIN_TRIBE_SURVIVAL"]:
            under_survival_days[tribe] += 1
            if under_survival_days[tribe] >= grace_days:
                for p, t in list(roster.items()):
                    if t == tribe:
                        roster[p] = UNALIGNED
                del under_survival_days[tribe]
        else:
            under_survival_days.pop(tribe, None)


def member_metrics(G: nx.Graph, roster: dict, tribe: str) -> list:
    rows = []
    for p, t in roster.items():
        if t != tribe:
            continue
        own = other = 0.0
        if p in G:
            for n in G.neighbors(p):
                t_n = roster.get(n, UNALIGNED)
                if t_n is UNALIGNED:
                    continue
                if t_n == tribe:
                    own += G[p][n]["weight"]
                else:
                    other += G[p][n]["weight"]
        fidelity = round(100 * own / (own + other)) if own + other else 0
        rows.append([p, fidelity, round(own, 1)])
    rows.sort(key=lambda r: (-r[2], str(r[0])))
    return rows


def build_constellations(
    roster: dict, player_games: Counter, shared: dict, latest_date: str, cfg: dict
) -> dict:
    alpha = cfg.get("PARTNERS_SCALE_FACTOR", 2.5)
    players = {}

    for p in sorted(player_games):
        all_partners = sorted(shared[p].items(), key=lambda x: (-x[1], str(x[0])))
        total_partners = len(all_partners)

        if total_partners == 0:
            players[p] = {
                "tribe": roster.get(p, UNALIGNED),
                "games": player_games[p],
                "partners": [],
            }
            continue

        min_target = max(10, math.floor(alpha * math.sqrt(total_partners)))
        min_target = min(total_partners, min_target)

        selected_min_games = 1
        for mg in range(1, 10):
            filtered = [partner for partner, games in all_partners if games >= mg]
            if len(filtered) >= min_target:
                selected_min_games = mg
            else:
                break

        filtered_partners = [
            [partner, games] for partner, games in all_partners if games >= selected_min_games
        ]

        players[p] = {
            "tribe": roster.get(p, UNALIGNED),
            "games": player_games[p],
            "partners": filtered_partners,
        }
    return {"date": latest_date, "players": players}


def run_homelands_simulation(
    matches: list, custom_config: dict = None, season_id: str = "default"
) -> tuple[dict, dict]:
    if matches is None:
        return {}, {}
    if hasattr(matches, "empty") and matches.empty:
        return {}, {}
    if not hasattr(matches, "empty") and not matches:
        return {}, {}

    cfg = DEFAULT_CONFIG.copy()
    if custom_config:
        cfg.update(custom_config)

    tribe_names_pool = list(cfg.get("tribe_names", []))

    matches_by_date = {}
    for m in matches:
        date_str = str(
            m.get("Date_Closed") or m.get("date_closed") or m.get("Date") or m.get("date") or ""
        )[:10]
        players = list(
            dict.fromkeys(
                str(p.get("id") or p.get("name"))
                for p in m.get("players", [])
                if p.get("id") is not None or p.get("name") is not None
            )
        )
        if date_str and players:
            matches_by_date.setdefault(date_str, []).append(players)

    if not matches_by_date or not tribe_names_pool:
        return {}, {}

    sorted_dates = sorted(matches_by_date)

    rng = random.Random(season_id)
    rng.shuffle(tribe_names_pool)

    edge_weights = Counter()
    shared = defaultdict(Counter)
    player_games = Counter()
    last_active = {}
    roster = {}
    last_tribe = {}
    ever_used_names = set()
    under_survival_days = Counter()
    snapshots = {}
    limit_days = cfg["INACTIVITY_LIMIT_DAYS"]

    for d in sorted_dates:
        for pair in edge_weights:
            edge_weights[pair] *= cfg["DECAY_RATE"]

        for players in matches_by_date[d]:
            for p in players:
                player_games[p] += 1
                last_active[p] = d
                roster.setdefault(p, UNALIGNED)
            for p1, p2 in combinations(sorted(set(players)), 2):
                edge_weights[(p1, p2)] += cfg["NEW_MATCH_WEIGHT"]
                shared[p1][p2] += 1
                shared[p2][p1] += 1

        prune_inactive(roster, last_active, d, cfg)
        dissolve_small_tribes(roster, under_survival_days, cfg)

        G = nx.Graph()
        for (p1, p2), w in sorted(edge_weights.items()):
            if w >= cfg["MIN_EDGE_WEIGHT"]:
                G.add_edge(p1, p2, weight=w)

        min_games = min_games_required(
            player_games, cfg["MIN_GAMES_FLOOR"], cfg["DYNAMIC_RATIO"]
        )

        eligible = sorted(
            p for p in G.nodes()
            if player_games[p] >= min_games and is_player_active(p, last_active, d, limit_days)
        )

        target, founded = compass(
            G, roster, eligible, last_tribe, ever_used_names, cfg, tribe_names_pool
        )
        apply_compass(G, roster, target, founded, cfg)
        dissolve_small_tribes(roster, under_survival_days, cfg, immediate=True)

        for p, t in roster.items():
            if t is not UNALIGNED:
                last_tribe[p] = t

        snapshots[d] = {
            t: member_metrics(G, roster, t)
            for t in sorted({t for t in roster.values() if t is not UNALIGNED})
        }

    constellations = build_constellations(roster, player_games, shared, sorted_dates[-1], cfg)
    return snapshots, constellations
