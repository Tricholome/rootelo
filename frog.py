import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# Config & Chargement des données
config_path = Path("data/config/config.json") if Path("data/config/config.json").exists() else Path("data/config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config_data = json.load(f)

json_path = Path("data/rdl/archives/lh02/matches.json")
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# Traitement chronologique
matches_data = []
dates_set = set()
for match in matches:
    raw_date = match.get("Date") or match.get("date") or match.get("date_closed") or ""
    date_str = str(raw_date)[:10] if raw_date else "1970-01-01"
    player_names = [p.get("name") for p in match.get("players", []) if p.get("name")]
    if player_names:
        matches_data.append({"date": date_str, "players": player_names})
        dates_set.add(date_str)

sorted_dates = sorted(list(dates_set))

# --- PARAMÈTRES DU MOTEUR ORGANIQUE ---
HALF_LIFE_DAYS = 21  # Demi-vie des matchs (les matchs d'il y a 21j pèsent 50%)
LAMBDA = math.log(2) / HALF_LIFE_DAYS
ATTRACTION_THRESHOLD = 0.35  # 35% du temps de jeu récent consacré à un groupe pour l'intégrer
MIN_TRIBE_SIZE = 4
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]

daily_tribes = {}
prev_assignments = {}  # {player: tribe} au jour T-1
registered_tribes = []

for current_date_str in sorted_dates:
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    cumulative_matches = [m for m in matches_data if m["date"] <= current_date_str]
    
    # 1. Calcul du graphe pondéré par décroissance temporelle
    G = nx.Graph()
    player_activity = defaultdict(float)
    
    for m in cumulative_matches:
        m_date = datetime.strptime(m["date"], "%Y-%m-%d")
        days_ago = (current_date - m_date).days
        weight = math.exp(-LAMBDA * days_ago)
        
        for p in m["players"]:
            player_activity[p] += weight
            
        for p1, p2 in combinations(sorted(m["players"]), 2):
            if G.has_edge(p1, p2):
                G[p1][p2]["weight"] += weight
            else:
                G.add_edge(p1, p2, weight=weight)

    # 2. Détection initiale des noyaux durs (Louvain sur le graphe temporel)
    active_players = {p for p, act in player_activity.items() if act >= 1.0}
    G_active = G.subgraph(active_players)
    
    current_assignments = {}
    if G_active.number_of_nodes() > 0:
        try:
            communities = list(nx.community.louvain_communities(G_active, weight="weight", seed=42))
        except Exception:
            communities = []

        # Identifier les communautés stables (>= MIN_TRIBE_SIZE)
        major_communities = [c for c in communities if len(c) >= MIN_TRIBE_SIZE]
        
        # 3. Association continue avec l'historique (Inertie)
        claimed_tribes = set()
        for comm in sorted(major_communities, key=len, reverse=True):
            history_counts = Counter(prev_assignments.get(p) for p in comm if prev_assignments.get(p) in registered_tribes)
            valid_history = {t: cnt for t, cnt in history_counts.items() if t not in claimed_tribes}
            
            if valid_history:
                assigned_name = max(valid_history, key=valid_history.get)
            elif len(registered_tribes) < len(ALLOWED_TRIBES):
                assigned_name = ALLOWED_TRIBES[len(registered_tribes)]
                registered_tribes.append(assigned_name)
            else:
                continue
                
            claimed_tribes.add(assigned_name)
            for p in comm:
                current_assignments[p] = assigned_name

        # 4. Attributs d'attraction pour les joueurs périphériques
        for p in active_players:
            if p not in current_assignments:
                total_p_weight = sum(G[p][nbr]["weight"] for nbr in G[p])
                if total_p_weight > 0:
                    tribe_attractions = defaultdict(float)
                    for nbr in G[p]:
                        nbr_tribe = current_assignments.get(nbr) or prev_assignments.get(nbr)
                        if nbr_tribe in registered_tribes:
                            tribe_attractions[nbr_tribe] += G[p][nbr]["weight"]
                            
                    best_tribe, best_score = max(tribe_attractions.items(), key=lambda x: x[1], default=(None, 0))
                    if best_tribe and (best_score / total_p_weight) >= ATTRACTION_THRESHOLD:
                        current_assignments[p] = best_tribe

    # Tous les autres joueurs sont Inclassés
    for p in player_activity:
        if p not in current_assignments:
            current_assignments[p] = "Inclassé"

    prev_assignments = current_assignments
    daily_tribes[current_date_str] = current_assignments

# Génération HTML (Jinja2)
player_games = Counter(p for m in matches_data for p in m["players"])
latest_date = sorted_dates[-1] if sorted_dates else ""
players_list = [
    {"name": name, "games": count, "tribe": daily_tribes.get(latest_date, {}).get(name, "Inclassé")}
    for name, count in sorted(player_games.items(), key=lambda x: (-x[1], x[0]))
]

env = Environment(loader=FileSystemLoader("templates"))
env.globals["config"] = config_data
template = env.get_template("frog.html")

output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        players=players_list,
        matches_json=json.dumps(matches_data, ensure_ascii=False),
        dates_json=json.dumps(sorted_dates, ensure_ascii=False),
        tribes_json=json.dumps(daily_tribes, ensure_ascii=False)
    ))

print(f"Moteur organique prêt : {len(sorted_dates)} dates calculées.")
