import json
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES
# ==============================================================================

# Gestion dynamique des tribus
MIN_TRIBE_SIZE = 4         # Nombre minimum de joueurs pour former une tribu
MAX_TRIBES = 4             # Nombre maximum de tribus affichées simultanément
TRIBE_NAMES_POOL = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
UNALIGNED_LABEL = "-"

# Hyperparamètres du graphe
DECAY_RATE = 0.95          
NEW_MATCH_WEIGHT = 1.0     

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
# 🧠 MOTEUR DYNAMIQUE
# ==============================================================================

snapshots = {}
edge_weights = Counter()
player_games = Counter()
previous_communities = {}

for d in sorted_dates:
    # 1. Atténuation & Nouveaux Matchs
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE
        
    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    active_edges = {k: v for k, v in edge_weights.items() if v >= 0.1}

    G = nx.Graph()
    for (p1, p2), weight in active_edges.items():
        G.add_edge(p1, p2, weight=weight)

    # 2. Détection & Filtrage des Tribus
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

        # Filtrage par taille min et plafond max
        valid_comms = [c for c in raw_comms if len(c) >= MIN_TRIBE_SIZE][:MAX_TRIBES]

        # 3. Alignement des noms avec la veille
        used_names = set()
        
        for comm in valid_comms:
            best_name = None
            max_intersect = 0
            
            # Chercher le meilleur match dans les tribus de la veille
            for old_name, old_comm in previous_communities.items():
                if old_name not in used_names:
                    intersect = len(comm.intersection(old_comm))
                    if intersect > max_intersect:
                        max_intersect = intersect
                        best_name = old_name
            
            # Si c'est une nouvelle tribu, piocher un nom disponible
            if not best_name:
                for name in TRIBE_NAMES_POOL:
                    if name not in used_names and name not in previous_communities:
                        best_name = name
                        break
            
            # En cas d'épuisement théorique du pool
            if not best_name:
                for name in TRIBE_NAMES_POOL:
                    if name not in used_names:
                        best_name = name
                        break
                        
            if best_name:
                used_names.add(best_name)
                current_communities[best_name] = comm

    previous_communities = current_communities
    active_tribes_today = sorted(list(current_communities.keys()))

    # 4. Affinités individuelles basées sur les tribus actives du jour
    tribe_summary = {t: 0 for t in active_tribes_today + [UNALIGNED_LABEL]}
    snapshot_players = []

    for name, games_played in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        if name not in G:
            formatted_scores = {t: {"pct": 0, "status": "Wavering"} for t in active_tribes_today}
            snapshot_players.append({
                "name": name, "games": games_played,
                "main_tribe": UNALIGNED_LABEL, "scores": formatted_scores
            })
            tribe_summary[UNALIGNED_LABEL] += 1
            continue

        comm_affinities = {t: 0.0 for t in active_tribes_today}
        total_affinity = 0.0

        for neighbor in G.neighbors(name):
            weight = G[name][neighbor]["weight"]
            total_affinity += weight
            
            for t_name, comm_players in current_communities.items():
                if neighbor in comm_players:
                    comm_affinities[t_name] += weight

        scores_pct = {}
        for t_name in active_tribes_today:
            scores_pct[t_name] = round((comm_affinities[t_name] / total_affinity) * 100) if total_affinity > 0 else 0

        best_tribe = max(scores_pct, key=scores_pct.get) if scores_pct else UNALIGNED_LABEL
        if scores_pct.get(best_tribe, 0) < STATUS_AFFILIATE_PCT or games_played < MIN_GAMES_FLOOR:
            best_tribe = UNALIGNED_LABEL

        tribe_summary[best_tribe] += 1

        formatted_scores = {}
        for t_name in active_tribes_today:
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

    # On ajoute la liste des tribus actives pour faciliter le rendu Jinja2
    snapshots[d] = {
        "active_tribes": active_tribes_today,
        "summary": tribe_summary, 
        "players": snapshot_players
    }

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
