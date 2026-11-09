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
    "MIN_TRIBE_SURVIVAL": 4,
    "MIN_REUSE_OVERLAP": 3,
    "MIN_COOLDOWN_DAYS": 7,
    "MIN_GAMES_FLOOR": 3,
    "DYNAMIC_RATIO": 2.0,
    "STICKINESS": 1.5,
    "MAX_DAILY_TRANSFERS": 3,
    "INACTIVITY_LIMIT_DAYS": 21,
    "PARTNERS_SCALE_FACTOR": 2.5,
    "DECAY_RATE": 0.95,
    "NEW_MATCH_WEIGHT": 1.0,
    "MIN_EDGE_WEIGHT": 0.1,
    "RESOLUTION": 1.2,
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
            elif roster.get(n, UNALIGNED) is not UNALIGNED:
                outside += w
    return inside > stickiness * outside


def pick_tribe_name(
    comm: set,
    available_names: list,
    historical_members: dict,
    last_seen: dict,
    times_used: Counter,
    current_date: str,
    cfg: dict,
) -> str | None:
    """
    Each tribe name can be founded once (times_used == 0) and revived/reclaimed at most once (times_used == 1).
    Priority: 1. Revive -> 2. Reclaim -> 3. Fresh name.
    """
    cur_dt = date.fromisoformat(current_date)
    cooldown = cfg["MIN_COOLDOWN_DAYS"]
    min_reuse = cfg["MIN_REUSE_OVERLAP"]

    recyclable = [
        t for t in available_names
        if times_used[t] == 1
        and t in last_seen
        and (cur_dt - date.fromisoformat(last_seen[t])).days > cooldown
    ]

    # 1. Revive: former members reforming their dissolved homeland
    revivable = [
        t for t in recyclable
        if len(comm & historical_members.get(t, set())) >= min_reuse
    ]
    if revivable:
        return max(revivable, key=lambda t: len(comm & historical_members[t]))

    # 2. Reclaim: recycle the longest-abandoned dissolved name (only if used once so far)
    if recyclable:
        return min(recyclable, key=lambda t: last_seen[t])

    # 3. Fresh: first name never used in the season
    for t in available_names:
        if times_used[t] == 0:
            return t

    return None


def compass(
    G: nx.Graph,
    roster: dict,
    eligible: list,
    historical_members: dict,
    last_seen: dict,
    times_used: Counter,
    current_date: str,
    cfg: dict,
    tribe_names_pool: list,
) -> tuple[dict, set]:
    if not eligible:
        return {}, set()

    eligible_set = set(eligible)
    H = nx.Graph()
    H.add_nodes_from(eligible)
    for u, v, data in sorted(G.edges(data=True), key=lambda e: tuple(sorted(e[:2]))):
        if u in eligible_set and v in eligible_set:
            H.add_edge(*sorted((u, v)), weight=data["weight"])

    comms = nx.community.louvain_communities(
        H,
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
        if overlap > 0 and i not in name_of and t not in name_of.values():
            name_of[i] = t

    available_slots = max(0, cfg["MAX_TRIBES"] - len(members))

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

        taken = set(members.keys()) | set(name_of.values())
        available_names = [t for t in tribe_names_pool if t not in taken]

        chosen_name = pick_tribe_name(
            c, available_names, historical_members, last_seen, times_used, current_date, cfg
        )
        if chosen_name:
            name_of[i] = chosen_name
            founded.add(chosen_name)
            times_used[chosen_name] += 1

    target = {p: name_of[i] for i, c in enumerate(comms) if i in name_of for p in sorted(c)}
    return target, founded


def apply_compass(G: nx.Graph, roster: dict, target: dict, founded: set, cfg: dict) -> None:
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
    limit_days = cfg["INACTIVITY_LIMIT_DAYS"]
    if limit_days is None:
        return

    for p, t in list(roster.items()):
        if t is not UNALIGNED and not is_player_active(p, last_active, current_date, limit_days):
            roster[p] = UNALIGNED


def dissolve_small_tribes(roster: dict, cfg: dict) -> None:
    counts = Counter(t for t in roster.values() if t is not UNALIGNED)
    for tribe, n in counts.items():
        if n < cfg["MIN_TRIBE_SURVIVAL"]:
            for p, t in list(roster.items()):
                if t == tribe:
                    roster[p] = UNALIGNED


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
    historical_members = defaultdict(set)
    last_seen = {}
    times_used = Counter()
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
        dissolve_small_tribes(roster, cfg)

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
            G,
            roster,
            eligible,
            historical_members,
            last_seen,
            times_used,
            d,
            cfg,
            tribe_names_pool,
        )
        apply_compass(G, roster, target, founded, cfg)
        dissolve_small_tribes(roster, cfg)

        active_today = set()
        for p, t in roster.items():
            if t is not UNALIGNED:
                historical_members[t].add(p)
                active_today.add(t)

        for t in active_today:
            last_seen[t] = d

        snapshots[d] = {
            t: member_metrics(G, roster, t)
            for t in sorted(active_today)
        }

    constellations = build_constellations(roster, player_games, shared, sorted_dates[-1], cfg)
    return snapshots, constellations
