import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES
# ==============================================================================

TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"

DECAY_RATE = 0.95          # Facteur d'oubli quotidien (5% d'atténuation par jour)
NEW_MATCH_WEIGHT = 1.0     # Poids ajouté pour chaque nouvelle rencontre

MIN_GAMES_FLOOR = 3
STATUS_LOYAL_PCT = 55
STATUS_AFFILIATE_PCT = 35

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 CHARGEMENT DES DONNÉES
# ==============================================================================

config_path = CONFIG_PATH if CONFIG_PATH.exists() else Path("data/config.json")
config_data = json.load(open(config_path, "r", encoding="utf-8")) if config_path.exists() else {}

json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

matches_by_date = {}
for m in matches:
    date_str = str(m.get("Date") or m.get("date") or m.get("date_closed") or "")[:10]
    players = [p.get("name") for p in m.get("players", []) if p.get("name")]
    if date_str and players:
        matches_by_date.setdefault(date_str, []).append(players)

sorted_dates = sorted(matches_by_date.keys())

# ==============================================================================
# 🧠 L'ALGORITHME ORGANIQUE (LOUVAIN SUR GRAPHE ATTÉNUÉ)
# ==============================================================================

snapshots = {}
edge_weights = Counter()    # Mémoire persistante des arêtes
player_games = Counter()    # Compteur total des parties

previous_communities = {}   # Alignement continu des noms de tribus

for d in sorted_dates:
    # 1. Atténuation exponentielle des anciens liens
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE
        
    # 2. Injection des nouveaux matchs du jour
    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    # Nettoyage des liens résiduels (< 0.1)
    active_edges = {k: v for k, v in edge_weights.items() if v >= 0.1}

    # 3. Construction du graphe et détection de communautés
    G = nx.Graph()
    for (p1, p2), weight in active_edges.items():
        G.add_edge(p1, p2, weight=weight)

    current_communities = {}
    if G.number_of_nodes() > 0:
        try:
            raw_comms = sorted(
                nx.community.louvain_communities(G, weight="weight", seed=42),
                key=len,
                reverse=True
            )
        except Exception:
            raw_comms = []

        # Mapping des noms pour préserver la stabilité d'un jour à l'autre
        available_names = TARGET_TRIBES.copy()
        for comm in raw_comms[:len(TARGET_TRIBES)]:
            best_name = None
            max_intersect = 0
            for old_name, old_comm in previous_communities.items():
                if old_name in available_names:
                    intersect = len(comm.intersection(old_comm))
                    if intersect > max_intersect:
                        max_intersect = intersect
                        best_name = old_name
            
            if not best_name and available_names:
                best_name = available_names[0]
                
            if best_name:
                available_names.remove(best_name)
                current_communities[best_name] = comm

    previous_communities = current_communities

    # 4. Extraction des affinités individuelles
    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}
    snapshot_players = []

    for name, games_played in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        if name not in G:
            formatted_scores = {t: {"pct": 0, "status": "Wavering"} for t in TARGET_TRIBES}
            snapshot_players.append({
                "name": name,
                "games": games_played,
                "main_tribe": UNALIGNED_LABEL,
                "scores": formatted_scores
            })
            tribe_summary[UNALIGNED_LABEL] += 1
            continue

        comm_affinities = {t: 0.0 for t in TARGET_TRIBES}
        total_affinity = 0.0

        for neighbor in G.neighbors(name):
            weight = G[name][neighbor]["weight"]
            total_affinity += weight
            
            for t_name, comm_players in current_communities.items():
                if neighbor in comm_players:
                    comm_affinities[t_name] += weight

        scores_pct = {}
        for t_name in TARGET_TRIBES:
            scores_pct[t_name] = (
                round((comm_affinities[t_name] / total_affinity) * 100)
                if total_affinity > 0 else 0
            )

        best_tribe = max(scores_pct, key=scores_pct.get) if total_affinity > 0 else UNALIGNED_LABEL
        if scores_pct.get(best_tribe, 0) < STATUS_AFFILIATE_PCT or games_played < MIN_GAMES_FLOOR:
            best_tribe = UNALIGNED_LABEL

        tribe_summary[best_tribe] = tribe_summary.get(best_tribe, 0) + 1

        formatted_scores = {}
        for t_name in TARGET_TRIBES:
            pct = scores_pct[t_name]
            status = "Wavering"
            if t_name == best_tribe:
                if pct >= STATUS_LOYAL_PCT:
                    status = "Loyalist"
                elif pct >= STATUS_AFFILIATE_PCT:
                    status = "Affiliate"
            formatted_scores[t_name] = {"pct": pct, "status": status}

        snapshot_players.append({
            "name": name,
            "games": games_played,
            "main_tribe": best_tribe,
            "scores": formatted_scores
        })

    snapshots[d] = {"summary": tribe_summary, "players": snapshot_players}

# ==============================================================================
# 📝 RENDU HTML (JINJA2)
# ==============================================================================

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.globals["config"] = config_data
template = env.get_template(TEMPLATE_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        snapshots_json=json.dumps(snapshots, ensure_ascii=False), 
        dates_json=json.dumps(sorted_dates, ensure_ascii=False)
    ))

print(f"Analyse terminée avec succès : {len(sorted_dates)} dates calculées sur graphe atténué.")
