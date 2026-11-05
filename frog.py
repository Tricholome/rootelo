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
    "REUSE_OVERLAP_RATIO": 0.5,
    "MAX_RECYCLES_PER_SEASON": 1,
    "MIN_RECYCLE_OVERLAP": 3,
    "SPLIT_BIG_SHARE": 0.35,
    "SPLIT_RESOLUTION": 2.0,
    "MIN_GAMES_FLOOR": 3,
    "DYNAMIC_RATIO": 2.0,
    "STICKINESS": 1.5,
    "SPLIT_RATIO": 0.75,
    "MAX_DAILY_TRANSFERS": 3,
    "INACTIVITY_LIMIT_DAYS": 21,
    "PARTNERS_SCALE_FACTOR": 2.5,
    "DECAY_RATE": 0.95,
    "NEW_MATCH_WEIGHT": 1.0,
    "MIN_EDGE_WEIGHT": 0.1,
    "RESOLUTION": 1.8,
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


def is_clearly_apart(G: nx.Graph, roster: dict, comm: set, split_ratio: float) -> bool:
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
    # Correct double-counting of internal edges while keeping the 0.75 effective ratio
    return (inside / 2.0) > split_ratio * outside


class NameBook:
    """Mémoire des noms de tribus : qui les a portés, quand, et combien de recyclages ont eu lieu."""

    def __init__(self, pool: list, cfg: dict):
        self.pool = pool
        self.cfg = cfg
        self.last_roster = {}          # nom -> derniers membres connus
        self.ever = defaultdict(set)   # nom -> tous les joueurs qui l'ont porté cette saison
        self.last_seen = {}            # nom -> dernier jour d'existence
        self.recycles = 0

    def _continuity(self, comm: set, name: str) -> int:
        old = self.last_roster.get(name, set())
        ov = len(comm & old)
        ok = ov >= self.cfg["MIN_REUSE_OVERLAP"] and ov >= self.cfg["REUSE_OVERLAP_RATIO"] * min(len(comm), len(old))
        return ov if ok else 0

    def pick(self, comm: set, taken: set, today: str):
        """Nom d'une nouvelle tribu, ou None si aucun nom n'est permis. Par ordre de priorité :
        1. résurrection : un nom dont le dernier effectif recouvre nettement la communauté
        2. un nom jamais utilisé
        3. recyclage, limité à MAX_RECYCLES_PER_SEASON, et seulement si au moins
           MIN_RECYCLE_OVERLAP joueurs de la communauté ont déjà porté ce nom
        """
        free = [n for n in self.pool if n not in taken]
        order = {n: i for i, n in enumerate(self.pool)}

        name = None
        revivable = [n for n in free if self._continuity(comm, n)]
        if revivable:
            name = max(revivable, key=lambda n: (self._continuity(comm, n), -order[n]))
        else:
            unused = [n for n in free if n not in self.last_seen]
            if unused:
                name = unused[0]
            elif self.recycles < self.cfg["MAX_RECYCLES_PER_SEASON"]:
                cands = [(len(comm & self.ever[n]), n) for n in free]
                cands = [(ov, n) for ov, n in cands if ov >= self.cfg["MIN_RECYCLE_OVERLAP"]]
                if cands:
                    name = min(cands, key=lambda x: (-x[0], self.last_seen[x[1]], order[x[1]]))[1]
                    self.recycles += 1

        if name is not None:
            self.last_seen[name] = today  # un nom fondé puis dissous le jour même n'est pas "jamais utilisé"
        return name

    def update(self, today: str, tribes: dict) -> None:
        for t, members in tribes.items():
            self.last_seen[t] = today
            self.last_roster[t] = set(members)
            self.ever[t] |= members


def louvain(G: nx.Graph, nodes, resolution: float) -> list:
    return nx.community.louvain_communities(
        G.subgraph(nodes), weight="weight", resolution=resolution, seed=42
    )


def split_big_communities(G: nx.Graph, comms: list, n_eligible: int, cfg: dict) -> list:
    """Repasse dans Louvain (résolution plus fine) toute communauté qui dépasse SPLIT_BIG_SHARE des joueurs éligibles."""
    share = cfg.get("SPLIT_BIG_SHARE")
    if not share:
        return comms
    out = []
    for c in comms:
        if len(c) > share * n_eligible and len(c) >= 2 * cfg["MIN_TRIBE_CREATION_SIZE"]:
            parts = louvain(G, sorted(c), cfg["SPLIT_RESOLUTION"])
            out.extend(parts if len(parts) > 1 else [c])
        else:
            out.append(c)
    return out


def compass(
    G: nx.Graph,
    roster: dict,
    eligible: list,
    names: NameBook,
    current_date: str,
    cfg: dict,
) -> tuple[dict, set]:
    if not eligible:
        return {}, set()

    comms = louvain(G, eligible, cfg["RESOLUTION"])
    comms = split_big_communities(G, comms, len(eligible), cfg)
    comms.sort(key=lambda c: (-len(c), sorted(c)))

    members = {}
    for p, t in roster.items():
        if t is not UNALIGNED:
            members.setdefault(t, set()).add(p)

    # Les communautés qui prolongent une tribu existante gardent son nom
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
        # Au moins 2 joueurs en commun pour qu'un seul membre ne s'approprie pas le nom
        if overlap >= min(2, len(members[t])) and i not in name_of and t not in name_of.values():
            name_of[i] = t

    available_slots = max(0, cfg["MAX_TRIBES"] - len(members))
    split_ratio = cfg.get("SPLIT_RATIO", cfg["STICKINESS"] / 2.0)

    # Les autres, assez grosses et nettement séparées, fondent une tribu
    founded = set()
    for i, c in enumerate(comms):
        if len(founded) >= available_slots:
            break
        if (
            i in name_of
            or len(c) < cfg["MIN_TRIBE_CREATION_SIZE"]
            or not is_clearly_apart(G, roster, c, split_ratio)
        ):
            continue
        name = names.pick(c, set(members) | set(name_of.values()), current_date)
        if name is None:
            continue
        name_of[i] = name
        founded.add(name)

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
            # Require an actual connection (w[t] > 0) to join an existing tribe
            if w[t] > 0 and w[t] == max(w.values()):
                moves.append((p, t))
        else:
            w = weight_by_tribe(G, roster, p)
            if w[t] > cfg["STICKINESS"] * w[current]:
                switches.append((w[t] - w[current], p, t))

    switches.sort(reverse=True)
    moves += [(p, t) for _, p, t in switches[: cfg["MAX_DAILY_TRANSFERS"]]]

    for p, t in moves:
        roster[p] = t


def prune_inactive_or_detached(
    G: nx.Graph, roster: dict, last_active: dict, current_date: str, cfg: dict
) -> None:
    limit_days = cfg["INACTIVITY_LIMIT_DAYS"]

    for p, t in list(roster.items()):
        if t is UNALIGNED:
            continue
        if limit_days is not None and not is_player_active(p, last_active, current_date, limit_days):
            roster[p] = UNALIGNED
            continue
        # Release fossilized members whose active edges with their own tribe have completely decayed
        w = weight_by_tribe(G, roster, p)
        if w[t] <= 0:
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
    names = NameBook(tribe_names_pool, cfg)
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

        G = nx.Graph()
        for (p1, p2), w in sorted(edge_weights.items()):
            if w >= cfg["MIN_EDGE_WEIGHT"]:
                G.add_edge(p1, p2, weight=w)

        prune_inactive_or_detached(G, roster, last_active, d, cfg)
        dissolve_small_tribes(roster, cfg)

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
            names,
            d,
            cfg,
        )
        apply_compass(G, roster, target, founded, cfg)
        prune_inactive_or_detached(G, roster, last_active, d, cfg)
        dissolve_small_tribes(roster, cfg)

        today = defaultdict(set)
        for p, t in roster.items():
            if t is not UNALIGNED:
                today[t].add(p)
        names.update(d, today)
        active_today = set(today)

        snapshots[d] = {
            t: member_metrics(G, roster, t)
            for t in sorted(active_today)
        }

    constellations = build_constellations(roster, player_games, shared, sorted_dates[-1], cfg)
    return snapshots, constellations
