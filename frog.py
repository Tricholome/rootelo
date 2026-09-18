import json
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# 1. Configuration globale
config_path = Path("data/config/config.json")
if not config_path.exists():
    config_path = Path("data/config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config_data = json.load(f)

# 2. Fichier d'archives des matchs
json_path = Path("data/rdl/archives/lh02/matches.json")
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 3. Extraction chronologique des matchs
matches_data = []
dates_set = set()

for match in matches:
    raw_date = match.get("Date") or match.get("date") or match.get("date_closed") or ""
    date_str = str(raw_date)[:10] if raw_date else "1970-01-01"
    
    player_names = [p.get("name") for p in match.get("players", []) if p.get("name")]
    if player_names:
        matches_data.append({
            "date": date_str,
            "players": player_names
        })
        dates_set.add(date_str)

sorted_dates = sorted(list(dates_set))

# 4. Calcul de Louvain jour par jour (méthode cumulative)
LEAGUE_LABELS = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_MATCHES = 3
MIN_COMMUNITY_SIZE = 5
MAX_LEAGUES = 5

daily_tribes = {}

for d in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    player_counts = Counter()
    for m in cumulative_matches:
        for p in m["players"]:
            player_counts[p] += 1
            
    # Joueurs actifs à la date d
    active_players = {p for p, count in player_counts.items() if count >= MIN_MATCHES}
    
    # Construction du graphe de co-occurrence
    G = nx.Graph()
    G.add_nodes_from(active_players)
    
    for m in cumulative_matches:
        m_active = [p for p in m["players"] if p in active_players]
        for p1, p2 in combinations(m_active, 2):
            if G.has_edge(p1, p2):
                G[p1][p2]["weight"] += 1
            else:
                G.add_edge(p1, p2, weight=1)
                
    date_assignments = {}
    
    if G.number_of_nodes() > 0:
        try:
            # Algorithme de Louvain pour maximiser la modularité Q
            communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            communities = []
            
        # Tri des communautés par taille décroissante
        communities = sorted(communities, key=lambda c: len(c), reverse=True)
        
        assigned_league_idx = 0
        for comm in communities:
            if len(comm) >= MIN_COMMUNITY_SIZE and assigned_league_idx < MAX_LEAGUES:
                label = LEAGUE_LABELS[assigned_league_idx]
                assigned_league_idx += 1
                for player in comm:
                    date_assignments[player] = label
            else:
                for player in comm:
                    date_assignments[player] = "Inclassé"
                    
    for player in player_counts:
        if player not in date_assignments:
            date_assignments[player] = "Inclassé"
            
    daily_tribes[d] = date_assignments

# 5. Rendu Jinja2
player_games = Counter()
for m in matches_data:
    for p in m["players"]:
        player_games[p] += 1

latest_date = sorted_dates[-1] if sorted_dates else ""
players_list = [
    {
        "name": name,
        "games": count,
        "tribe": daily_tribes.get(latest_date, {}).get(name, "Inclassé")
    }
    for name, count in sorted(player_games.items(), key=lambda x: (-x[1], x[0]))
]

env = Environment(loader=FileSystemLoader("templates"))
env.globals["config"] = config_data

template = env.get_template("frog.html")

rendered_html = template.render(
    active_section="frog",
    players=players_list,
    matches_json=json.dumps(matches_data, ensure_ascii=False),
    dates_json=json.dumps(sorted_dates, ensure_ascii=False),
    tribes_json=json.dumps(daily_tribes, ensure_ascii=False)
)

output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(rendered_html)

print(f"Fichier '{output_path}' généré avec succès ({len(sorted_dates)} dates analysées).")
