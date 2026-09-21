"""
frog.py — tribus dynamiques de joueurs au fil d'une saison.

Modifications apportées :
1. Suppression de la numérotation des régénérations (#2, #3, etc.)[cite: 4].
2. Remplacement du pool de noms par les 7 objets de Root[cite: 6].
3. Conservation de la limite stricte à 5 tribus simultanées max[cite: 4].
"""

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import json
import math
import random
import statistics
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION
# ==============================================================================

# --- Tribus ---
MAX_TRIBES = 5                 # Nombre max de tribus simultanées[cite: 4]
MIN_TRIBE_CREATION_SIZE = 8    # Fonder plus large que le seuil de survie[cite: 4]
MIN_TRIBE_SURVIVAL = 6         # Joueurs minimum pour qu'une tribu SURVIVE[cite: 4]

# --- Éligibilité ---
MIN_GAMES_FLOOR = 3            # Plancher absolu de matchs[cite: 4]
DYNAMIC_RATIO = 2.0            # Seuil = max(plancher, ratio × médiane globale)[cite: 4]

# --- Stabilité ---
STICKINESS = 1.5               # Pour quitter sa tribu : affinité ailleurs > STICKINESS × affinité actuelle[cite: 4]
MAX_DAILY_TRANSFERS = 3        # Max de changements de tribu (A→B) par jour[cite: 4]
INACTIVITY_LIMIT_DAYS = 30     # Au-delà, un joueur sort individuellement[cite: 4]

# --- Graphe ---
DECAY_RATE = 0.95              # Érosion quotidienne des arêtes[cite: 4]
NEW_MATCH_WEIGHT = 1.0         # Poids d'un match[cite: 4]
MIN_EDGE_WEIGHT = 0.1          # Sous ce poids, l'arête est ignorée[cite: 4]

UNALIGNED_LABEL = "-"

# --- Objets de Root comme nom de tribus (mélangés de manière déterministe) ---
ROOT_ITEMS_POOL = ["TEA", "BAG", "SWORD", "COINS", "HAMMER", "CROSSBOW", "BOOT"] #[cite: 6]
rng = random.Random(42)
TRIBE_NAMES_POOL = ROOT_ITEMS_POOL.copy()
rng.shuffle(TRIBE_NAMES_POOL)

REASON_LABELS = {
    "fondation":    "Nouvelle tribu fondée",
    "confirmation": "Lien le plus fort confirmé",
    "attraction":   "Attiré par une tribu plus forte",
    "dissolution":  "Tribu dissoute (sous le seuil)",
    "inactivite":   f"Inactif depuis plus de {INACTIVITY_LIMIT_DAYS}j" if INACTIVITY_LIMIT_DAYS else "Inactif",
} #[cite: 4]

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh03/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")
PAGES_CONTENT_PATH = Path("data/config/pages_content.json")


# ==============================================================================
# 🧩 BRIQUES DE L'ALGORITHME
# ==============================================================================

def min_games_required(player_games):
    median = statistics.median(player_games.values()) if player_games else 0
    return max(MIN_GAMES_FLOOR, math.ceil(median * DYNAMIC_RATIO)) #[cite: 4]


def weight_by_tribe(G, roster, p):
    weights = Counter()
    for n in G.neighbors(p):
        tribe = roster.get(n, UNALIGNED_LABEL)
        if tribe != UNALIGNED_LABEL:
            weights[tribe] += G[p][n]["weight"]
    return weights #[cite: 4]


def is_clearly_apart(G, roster, comm):
    inside = outside = 0.0
    for p in comm:
        for n in G.neighbors(p):
            w = G[p][n]["weight"]
            if n in comm:
                inside += w
            elif roster[p] != UNALIGNED_LABEL and roster[n] == roster[p]:
                outside += w
    return inside > STICKINESS * outside #[cite: 4]


def compass(G, roster, eligible, ever_used_names):
    comms = nx.community.louvain_communities(G.subgraph(eligible), weight="weight", seed=42)
    comms.sort(key=lambda c: (-len(c), sorted(c)))

    members = {}
    for p, t in roster.items():
        if t != UNALIGNED_LABEL:
            members.setdefault(t, set()).add(p)

    overlaps = sorted(((len(c & m), i, t) for i, c in enumerate(comms) for t, m in members.items()),
                      key=lambda x: (-x[0], x[1], x[2]))
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
            ever_used_names.add(chosen_name)  # Marque le nom comme utilisé au moins une fois

    target = {p: name_of[i] for i, c in enumerate(comms) if i in name_of for p in c}
    return target, founded


def _event(player, from_tribe, to_tribe, reason):
    etype = "in" if from_tribe == UNALIGNED_LABEL else ("out" if to_tribe == UNALIGNED_LABEL else "transfer")
    return {
        "player": player,
        "type": etype,
        "from": from_tribe,
        "to": to_tribe,
        "reason": reason,
        "label": REASON_LABELS[reason],
    } #[cite: 4]


def apply_compass(G, roster, target, founded):
    moves, switches = [], []
    for p, t in target.items():
        current = roster[p]
        if current == t:
            continue

        if t in founded:
            moves.append((p, current, t, "fondation"))
        elif current == UNALIGNED_LABEL:
            w = weight_by_tribe(G, roster, p)
            if not w or w[t] == max(w.values()):
                moves.append((p, current, t, "confirmation"))
        else:
            w = weight_by_tribe(G, roster, p)
            if w[t] > STICKINESS * w[current]:
                switches.append((w[t] - w[current], p, current, t))

    switches.sort(reverse=True)
    moves += [(p, current, t, "attraction") for _, p, current, t in switches[:MAX_DAILY_TRANSFERS]]

    events = []
    for p, current, t, reason in moves:
        roster[p] = t
        events.append(_event(p, current, t, reason))
    return events #[cite: 4]


def prune_inactive(roster, last_active, current_date):
    events = []
    if INACTIVITY_LIMIT_DAYS is None:
        return events
    cur = date.fromisoformat(current_date)
    for p, t in roster.items():
        if t == UNALIGNED_LABEL:
            continue
        last = last_active.get(p)
        if last is None or (cur - date.fromisoformat(last)).days > INACTIVITY_LIMIT_DAYS:
            roster[p] = UNALIGNED_LABEL
            events.append(_event(p, t, UNALIGNED_LABEL, "inactivite"))
    return events #[cite: 4]


def dissolve_small_tribes(roster):
    events = []
    counts = Counter(t for t in roster.values() if t != UNALIGNED_LABEL)
    for tribe, n in counts.items():
        if n < MIN_TRIBE_SURVIVAL:
            for p, t in roster.items():
                if t == tribe:
                    roster[p] = UNALIGNED_LABEL
                    events.append(_event(p, tribe, UNALIGNED_LABEL, "dissolution"))
    return events #[cite: 4]


def player_scores(G, roster, p, active_tribes):
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
# 🚀 CHARGEMENT DES DONNÉES
# ==============================================================================

config_path = CONFIG_PATH
if not config_path.exists():
    configs = list(Path(".").rglob("config.json"))
    if configs:
        config_path = configs[0]

pages_content = {}
if PAGES_CONTENT_PATH.exists():
    with open(PAGES_CONTENT_PATH, "r", encoding="utf-8") as f:
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
    print(f"❌ Erreur : Fichier de matchs introuvable à {json_path}")
    exit(1)

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
# 🧠 BOUCLE TEMPORELLE
# ==============================================================================

edge_weights = Counter()
player_games = Counter()
last_active = {}
roster = {}
snapshots = {}
ever_used_names = set()

for d in sorted_dates:
    # 1. Érosion des arêtes + nouveaux matchs du jour
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE

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

    # 2. Boussole
    eligible = [p for p in G.nodes() if player_games[p] >= min_games]
    target, founded = compass(G, roster, eligible, ever_used_names)
    events = apply_compass(G, roster, target, founded)

    # 3. Dissolutions & inactivité
    events += dissolve_small_tribes(roster)
    events += prune_inactive(roster, last_active, d)
    events += dissolve_small_tribes(roster)

    active_tribes = sorted({t for t in roster.values() if t != UNALIGNED_LABEL})

    # Libellés simples (sans numérotation #2, #3...)[cite: 4]
    tribe_labels = {t: t for t in TRIBE_NAMES_POOL}

    # 4. Snapshot
    summary = {t: 0 for t in TRIBE_NAMES_POOL + [UNALIGNED_LABEL]}
    snapshot_players = []
    for p, games in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        main_tribe = roster[p]
        summary[main_tribe] += 1
        snapshot_players.append({
            "name": p,
            "games": games,
            "main_tribe": main_tribe,
            "scores": player_scores(G, roster, p, active_tribes),
        })

    snapshots[d] = {
        "active_tribes": active_tribes,
        "tribe_labels": tribe_labels,
        "summary": summary,
        "players": snapshot_players,
        "events": events,
    }


# ==============================================================================
# 🎨 GÉNÉRATION HTML
# ==============================================================================

if (Path(TEMPLATE_DIR) / TEMPLATE_FILE).exists():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(TEMPLATE_FILE)

    html_content = template.render(
        config=config_data,
        page_id="homelands",
        section_id="homelands",
        path_prefix="",
        dates_json=json.dumps(sorted_dates),
        snapshots_json=json.dumps(snapshots),
        **pages_content.get("homelands", {}),
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Fichier {OUTPUT_FILE} généré avec succès ({len(snapshots)} dates).")
