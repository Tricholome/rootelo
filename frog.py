"""
frog.py — Détection de tribus stables au fil d'une saison.

Principes de conception (à lire avant de toucher aux paramètres) :

1. FENETRE GLISSANTE, pas cumulatif.
   Chaque match est pondéré par une demi-vie. Le signal est lisse par
   construction, ce qui évite d'avoir des seuils qui montent au fil de la
   saison pour compenser l'inertie du cumulatif.

2. LES TRIBUS SONT DES OBJETS PERSISTANTS.
   Elles ne sont pas recréées chaque jour. Louvain propose un découpage, qui
   est apparié globalement aux tribus existantes (Jaccard + Hongrois), puis la
   composition de chaque tribu dérive lentement (EMA). Une communauté qui ne
   ressemble à rien d'existant crée une NOUVELLE tribu. Une tribu qui n'est
   plus détectée devient dormante, puis meurt. Le nombre de tribus est une
   sortie, pas une entrée.

3. UN SEUL SCORE, LISSE, QUI SOMME A 100.
   L'affinité est calculée sur le MEME graphe que celui utilisé par Louvain.
   Les parts sont normalisées sur les tribus uniquement. La proximité avec les
   joueurs non affiliés est reportée séparément, comme un indice de confiance
   (`coverage`), et n'écrase plus les pourcentages.

4. UNE SEULE REGLE DE DECISION, AVEC DEBOUNCE TEMPOREL.
   On calcule une cible, on exige un écart minimum pour changer de tribu, et
   on n'applique le changement que s'il se confirme N jours de suite. Pas de
   cascade de if/elif, pas de court-circuit "core".

5. TOUT EST TRACABLE.
   `step()` est une fonction pure state -> state. Chaque joueur-jour porte un
   champ `reason` qui dit exactement quelle règle a décidé de son sort, et
   chaque journée porte des métriques de churn pour régler les paramètres sur
   des chiffres plutôt qu'à l'oeil.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

import networkx as nx
from jinja2 import Environment, FileSystemLoader

try:
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    HAS_SCIPY = True
except ImportError:  # repli sans scipy : appariement glouton trié globalement
    HAS_SCIPY = False


# ==============================================================================
# PARAMETRES
# ==============================================================================


@dataclass(frozen=True)
class Params:
    # --- Fenêtre temporelle ---
    half_life_days: float = 30.0  # au-delà, un match compte moitié moins
    prune_below: float = 1e-3  # poids négligeable : on oublie

    # --- Graphe ---
    min_weight_active: float = 2.0  # volume pondéré pour entrer dans le graphe
    min_pair_weight: float = 1.0  # co-présence pondérée minimale pour une arête
    min_cosine: float = 0.15  # force minimale d'une arête

    # --- Détection de communautés ---
    louvain_resolution: float = 1.2
    louvain_seed: int = 42
    min_community_size: int = 5

    # --- Continuité des tribus ---
    membership_alpha: float = 0.25  # vitesse de dérive de la composition
    membership_floor: float = 0.50  # poids au-delà duquel on est "membre"
    membership_prune: float = 0.05
    min_jaccard_match: float = 0.30  # en dessous : c'est une autre tribu
    max_dormant_days: int = 21  # dormance tolérée avant la mort
    probation_days: int = 10  # une tribu neuve n'accueille personne avant ça
    max_tribes: int = 8

    # --- Scores ---
    tribe_size_exponent: float = 0.5  # 0 = brut, 1 = moyenne, 0.5 = compromis
    score_beta: float = 0.35  # lissage EMA des parts

    # --- Décision ---
    min_weight_assign: float = 3.0  # volume requis pour être affilié
    min_coverage: float = 0.35  # part du jeu passée avec des affiliés
    entry_floor: float = 40.0  # part minimale pour rejoindre une tribu
    switch_margin: float = 12.0  # écart requis pour quitter sa tribu
    switch_days: int = 3  # jours consécutifs de confirmation

    # --- Affichage (n'influence jamais l'appartenance) ---
    wavering_margin: float = 8.0
    core_pct: float = 65.0
    loyal_pct: float = 45.0


UNALIGNED = "-"


def seq_label(n: int) -> str:
    """Tribe A, B, ... Z, AA, AB... Jamais recyclé : un libellé = une tribu, pour toujours."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return f"Tribe {s}"


# ==============================================================================
# MODELE
# ==============================================================================


@dataclass
class Tribe:
    id: str
    label: str
    born_on: str
    membership: dict[str, float] = field(default_factory=dict)
    last_active: str = ""
    dormant_days: int = 0

    def members(self, floor: float) -> set[str]:
        return {p for p, w in self.membership.items() if w >= floor}


@dataclass
class State:
    player_weight: dict[str, float] = field(default_factory=dict)
    pair_weight: dict[tuple[str, str], float] = field(default_factory=dict)
    games_played: Counter = field(default_factory=Counter)

    tribes: dict[str, Tribe] = field(default_factory=dict)
    scores: dict[str, dict[str, float]] = field(default_factory=dict)  # joueur -> tid -> part
    assignment: dict[str, str] = field(default_factory=dict)  # joueur -> tid | UNALIGNED
    since: dict[str, str] = field(default_factory=dict)  # date d'entrée dans la tribu
    pending: dict[str, tuple[str, int]] = field(default_factory=dict)  # cible + jours confirmés

    last_date: str | None = None
    tribe_seq: int = 0


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


# ==============================================================================
# 1. FENETRE GLISSANTE
# ==============================================================================


def absorb(state: State, day: str, day_matches: list[list[str]], p: Params) -> int:
    """Décroît l'historique puis intègre les matchs du jour. Retourne les jours écoulés."""
    elapsed = 0
    if state.last_date is not None:
        elapsed = (_d(day) - _d(state.last_date)).days

    if elapsed > 0:
        f = 0.5 ** (elapsed / p.half_life_days)
        state.player_weight = {
            k: v * f for k, v in state.player_weight.items() if v * f >= p.prune_below
        }
        state.pair_weight = {
            k: v * f for k, v in state.pair_weight.items() if v * f >= p.prune_below
        }

    for players in day_matches:
        uniq = sorted(set(players))
        for a in uniq:
            state.player_weight[a] = state.player_weight.get(a, 0.0) + 1.0
            state.games_played[a] += 1
        for a, b in combinations(uniq, 2):
            state.pair_weight[(a, b)] = state.pair_weight.get((a, b), 0.0) + 1.0

    state.last_date = day
    return elapsed


# ==============================================================================
# 2. GRAPHE ET COMMUNAUTES
# ==============================================================================


def build_graph(state: State, p: Params) -> nx.Graph:
    """Le graphe unique de la journée : il sert à Louvain ET au calcul des scores."""
    active = {pl for pl, w in state.player_weight.items() if w >= p.min_weight_active}
    G = nx.Graph()
    G.add_nodes_from(active)
    for (a, b), w in state.pair_weight.items():
        if a not in active or b not in active or w < p.min_pair_weight:
            continue
        cos = w / math.sqrt(state.player_weight[a] * state.player_weight[b])
        if cos >= p.min_cosine:
            G.add_edge(a, b, weight=cos)
    return G


def detect_communities(G: nx.Graph, p: Params) -> list[set[str]]:
    if G.number_of_edges() == 0:
        return []
    comms = nx.community.louvain_communities(
        G, weight="weight", resolution=p.louvain_resolution, seed=p.louvain_seed
    )
    return [set(c) for c in comms if len(c) >= p.min_community_size]


# ==============================================================================
# 3. CONTINUITE DES TRIBUS
# ==============================================================================


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_communities(
    comms: list[set[str]], tribes: dict[str, Tribe], p: Params
) -> dict[int, str]:
    """Appariement GLOBAL communauté <-> tribu existante. Sous le seuil : pas d'appariement."""
    if not comms or not tribes:
        return {}

    tids = list(tribes)
    sims = [[jaccard(c, tribes[t].members(p.membership_floor)) for t in tids] for c in comms]

    if HAS_SCIPY:
        rows, cols = linear_sum_assignment(-np.array(sims))
        pairs = [(int(r), int(c)) for r, c in zip(rows, cols) if sims[r][c] >= p.min_jaccard_match]
    else:
        ranked = sorted(
            ((sims[i][j], i, j) for i in range(len(comms)) for j in range(len(tids))),
            key=lambda x: -x[0],
        )
        taken_c, taken_t, pairs = set(), set(), []
        for s, i, j in ranked:
            if s < p.min_jaccard_match:
                break
            if i in taken_c or j in taken_t:
                continue
            taken_c.add(i)
            taken_t.add(j)
            pairs.append((i, j))

    return {i: tids[j] for i, j in pairs}


def drift(tribe: Tribe, comm: set[str], p: Params) -> None:
    """La composition d'une tribu se déplace lentement vers la communauté détectée."""
    a = p.membership_alpha
    keys = set(tribe.membership) | comm
    tribe.membership = {
        k: w
        for k in keys
        if (w := (1 - a) * tribe.membership.get(k, 0.0) + a * (1.0 if k in comm else 0.0))
        >= p.membership_prune
    }


def update_tribes(
    state: State,
    comms: list[set[str]],
    matched: dict[int, str],
    day: str,
    elapsed: int,
    p: Params,
) -> tuple[list[str], list[str]]:
    births, deaths = [], []

    for i, comm in enumerate(comms):
        tid = matched.get(i)
        if tid is None:
            continue
        t = state.tribes[tid]
        drift(t, comm, p)
        t.last_active = day
        t.dormant_days = 0

    for i, comm in enumerate(comms):
        if i in matched or len(state.tribes) >= p.max_tribes:
            continue
        state.tribe_seq += 1
        tid = f"t{state.tribe_seq}"
        state.tribes[tid] = Tribe(
            id=tid,
            label=seq_label(state.tribe_seq),
            born_on=day,
            membership={pl: 1.0 for pl in comm},
            last_active=day,
        )
        births.append(tid)

    alive = set(matched.values()) | set(births)
    for tid, t in list(state.tribes.items()):
        if tid in alive:
            continue
        t.dormant_days += max(1, elapsed)
        if t.dormant_days > p.max_dormant_days:
            del state.tribes[tid]
            deaths.append(tid)

    return births, deaths


# ==============================================================================
# 4. SCORES
# ==============================================================================


def compute_shares(
    G: nx.Graph, state: State, p: Params
) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """Parts d'affinité par tribu (somme = 100) + couverture (confiance), par joueur."""
    members = {tid: t.members(p.membership_floor) for tid, t in state.tribes.items()}
    owner = {pl: tid for tid, ms in members.items() for pl in ms}
    sizes = {tid: max(1, len(ms)) for tid, ms in members.items()}

    shares, coverage = {}, {}
    for player in G.nodes:
        raw = Counter()
        unaligned = 0.0
        for nb in G[player]:
            w = G[player][nb]["weight"]
            tid = owner.get(nb)
            if tid is None:
                unaligned += w
            else:
                raw[tid] += w

        aligned = sum(raw.values())
        coverage[player] = aligned / (aligned + unaligned) if (aligned + unaligned) > 0 else 0.0

        norm = {tid: raw[tid] / (sizes[tid] ** p.tribe_size_exponent) for tid in members}
        total = sum(norm.values())
        shares[player] = (
            {tid: 100.0 * v / total for tid, v in norm.items()}
            if total > 0
            else {tid: 0.0 for tid in members}
        )

    return shares, coverage


def smooth(prev: dict[str, float], raw: dict[str, float], live: set[str], beta: float):
    out = {tid: (1 - beta) * prev.get(tid, 0.0) + beta * raw.get(tid, 0.0) for tid in live}
    s = sum(out.values())
    return {tid: 100.0 * v / s for tid, v in out.items()} if s > 0 else out


# ==============================================================================
# 5. DECISION (une seule règle)
# ==============================================================================


def decide(
    player: str,
    scores: dict[str, float],
    coverage: float,
    state: State,
    day: str,
    p: Params,
    eligible_tribes: set[str],
) -> tuple[str, dict]:
    current = state.assignment.get(player, UNALIGNED)
    if current != UNALIGNED and current not in state.tribes:
        current = UNALIGNED  # sa tribu est morte

    weight = state.player_weight.get(player, 0.0)
    ranked = sorted(
        ((t, v) for t, v in scores.items() if t in eligible_tribes or t == current),
        key=lambda kv: -kv[1],
    )
    best, best_pct = ranked[0] if ranked else (UNALIGNED, 0.0)
    second_pct = ranked[1][1] if len(ranked) > 1 else 0.0

    # a) éligibilité : propriété du joueur, jamais de la tribu vers laquelle il penche
    if weight < p.min_weight_assign:
        target, rule = UNALIGNED, "volume insuffisant"
    elif coverage < p.min_coverage:
        target, rule = UNALIGNED, "entourage trop peu affilié"
    elif best_pct < p.entry_floor:
        target, rule = UNALIGNED, "aucune tribu au-dessus du seuil"
    else:
        target, rule = best, "meilleure affinité"

    # b) inertie : quitter sa tribu demande un écart, pas seulement un classement
    if current != UNALIGNED and target != UNALIGNED and target != current:
        if best_pct - scores.get(current, 0.0) < p.switch_margin:
            target, rule = current, "écart insuffisant pour changer"

    # c) debounce : un changement doit se confirmer N jours de suite
    pending_days = 0
    if target == current:
        state.pending.pop(player, None)
    else:
        cible, n = state.pending.get(player, (target, 0))
        n = n + 1 if cible == target else 1
        pending_days = n
        if n >= p.switch_days:
            state.pending.pop(player, None)
            state.assignment[player] = target
            state.since[player] = day
            current = target
            rule += " (confirmé)"
        else:
            state.pending[player] = (target, n)
            rule = f"changement en attente ({n}/{p.switch_days}) : {rule}"
            target = current

    if player not in state.since and current != UNALIGNED:
        state.since[player] = day
    state.assignment[player] = current

    reason = {
        "rule": rule,
        "weight": round(weight, 2),
        "coverage": round(coverage, 3),
        "best": best if ranked else None,
        "best_pct": round(best_pct, 1),
        "margin": round(best_pct - second_pct, 1),
        "pending_days": pending_days,
        "since": state.since.get(player),
    }
    return current, reason


def status_of(pct: float, margin: float, p: Params) -> str:
    if margin <= p.wavering_margin:
        return "Wavering"
    if pct >= p.core_pct:
        return "Core"
    if pct >= p.loyal_pct:
        return "Loyalist"
    return "Affiliate"


# ==============================================================================
# 6. UNE JOURNEE
# ==============================================================================


def step(state: State, day: str, day_matches: list[list[str]], p: Params) -> dict:
    previous = dict(state.assignment)

    elapsed = absorb(state, day, day_matches, p)
    G = build_graph(state, p)
    comms = detect_communities(G, p)
    matched = match_communities(comms, state.tribes, p)
    births, deaths = update_tribes(state, comms, matched, day, elapsed, p)

    for tid in deaths:
        for sc in state.scores.values():
            sc.pop(tid, None)

    live = set(state.tribes)
    established = {
        tid for tid, t in state.tribes.items()
        if (_d(day) - _d(t.born_on)).days >= p.probation_days
    }
    raw_shares, coverage = compute_shares(G, state, p)

    hubs = set()
    for tid, t in state.tribes.items():
        sub = G.subgraph(t.members(p.membership_floor) & set(G))
        if sub.number_of_nodes() >= 3:
            cent = nx.degree_centrality(sub)
            hubs |= set(sorted(cent, key=cent.get, reverse=True)[:3])

    players_out = []
    for player in sorted(state.games_played, key=lambda x: (-state.games_played[x], x)):
        raw = raw_shares.get(player, {})
        state.scores[player] = smooth(
            state.scores.get(player, {}), raw, live, p.score_beta
        )
        sc = state.scores[player]
        tribe, reason = decide(
            player, sc, coverage.get(player, 0.0), state, day, p, established
        )

        ordered = sorted(sc.values(), reverse=True)
        margin = (ordered[0] - ordered[1]) if len(ordered) > 1 else 100.0
        scores_out = {}
        for tid in live:
            pct = round(sc.get(tid, 0.0))
            scores_out[state.tribes[tid].label] = {
                "pct": pct,
                "status": status_of(sc.get(tid, 0.0), margin, p) if tid == tribe else None,
                "hub": player in hubs and tid == tribe,
            }

        players_out.append(
            {
                "name": player,
                "games": state.games_played[player],
                "weight": round(state.player_weight.get(player, 0.0), 1),
                "main_tribe": state.tribes[tribe].label if tribe in state.tribes else UNALIGNED,
                "scores": scores_out,
                "reason": reason,
            }
        )

    labels = [state.tribes[t].label for t in sorted(live)]
    summary = Counter(pl["main_tribe"] for pl in players_out)

    assigned_before = {k for k, v in previous.items() if v != UNALIGNED}
    moved = sum(
        1
        for k in assigned_before
        if state.assignment.get(k, UNALIGNED) != previous.get(k, UNALIGNED)
    )
    tenures = [
        (_d(day) - _d(state.since[k])).days
        for k, v in state.assignment.items()
        if v != UNALIGNED and k in state.since
    ]

    return {
        "tribes": labels,
        "summary": {lab: summary.get(lab, 0) for lab in labels + [UNALIGNED]},
        "players": players_out,
        "metrics": {
            "n_tribes": len(live),
            "established": len(established),
            "births": [state.tribes[t].label for t in births],
            "deaths": len(deaths),
            "churn_pct": round(100 * moved / max(1, len(assigned_before)), 1),
            "assigned": len([v for v in state.assignment.values() if v != UNALIGNED]),
            "mean_tenure_days": round(sum(tenures) / len(tenures), 1) if tenures else 0.0,
        },
    }


# ==============================================================================
# 7. ENTREE / SORTIE
# ==============================================================================

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh03/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")


def load_matches(path: Path) -> dict[str, list[list[str]]]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    by_day: dict[str, list[list[str]]] = {}
    for match in raw:
        stamp = match.get("Date") or match.get("date") or match.get("date_closed") or ""
        day = str(stamp)[:10] if stamp else "1970-01-01"
        names = [pl.get("name") for pl in match.get("players", []) if pl.get("name")]
        if names:
            by_day.setdefault(day, []).append(names)
    return by_day


def run(by_day: dict[str, list[list[str]]], p: Params) -> tuple[dict, list[str]]:
    state = State()
    snapshots = {}
    for day in sorted(by_day):
        snapshots[day] = step(state, day, by_day[day], p)
    return snapshots, sorted(by_day)


def main() -> None:
    params = Params()

    config_path = CONFIG_PATH if CONFIG_PATH.exists() else Path("data/config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    json_path = DEFAULT_MATCHES_PATH
    if not json_path.exists():
        archives = list(Path("data/rdl/archives").rglob("matches.json"))
        if archives:
            json_path = archives[0]

    by_day = load_matches(json_path)
    snapshots, dates = run(by_day, params)

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    env.globals["config"] = config_data
    template = env.get_template(TEMPLATE_FILE)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(
            template.render(
                active_section="frog",
                snapshots_json=json.dumps(snapshots, ensure_ascii=False),
                dates_json=json.dumps(dates, ensure_ascii=False),
            )
        )

    churn = [s["metrics"]["churn_pct"] for s in snapshots.values()]
    last = snapshots[dates[-1]]["metrics"]
    print(f"{len(dates)} journées | tribus finales : {last['n_tribes']}")
    print(f"churn moyen : {sum(churn) / len(churn):.2f} %/jour | max : {max(churn):.1f} %")
    print(f"ancienneté moyenne : {last['mean_tenure_days']:.0f} j | affiliés : {last['assigned']}")


if __name__ == "__main__":
    main()
