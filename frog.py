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

# 4. Calcul de Louvain avec suivi temporel (Strictement limité à 5 Tribus)
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_MATCHES = 3
MIN_COMMUNITY_SIZE = 5
MAX_LEAGUES = 5

prev_date_assignments = {}  # {player: tribe_name} à la date T-1
daily_tribes = {}

for d in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    player_counts = Counter()
    for m in cumulative_matches:
        for p in m["players"]:
            player_counts[p] += 1
            
    active_players = {p for p, count in player_counts.items() if count >= MIN_MATCHES}
    
    # Construction du graphe
    G = nx.Graph()
    G.add_nodes_from(active_players)
    
    for m in cumulative_matches:
        m_active = [p for p in m["players"] if p in active_players]
        for p1, p2 in combinations(m_active, 2):
            if G.has_edge(p1, p2):
                G[p1][p2]["weight"] += 1
            else:
                G.add_edge(p1, p2, weight=1)
                
    current_assignments = {}
    
    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            raw_communities = []
            
        # 1. Ne retenir que les 5 plus grandes communautés éligibles
        valid_communities = [c for c in raw_communities if len(c) >= MIN_COMMUNITY_SIZE]
        valid_communities = sorted(valid_communities, key=len, reverse=True)[:MAX_LEAGUES]
        
        # 2. Calcul du chevauchement avec la date précédente
        matches = []
        for comm_idx, comm in enumerate(valid_communities):
            counts = Counter(
                prev_date_assignments.get(p) 
                for p in comm 
                if prev_date_assignments.get(p) in ALLOWED_TRIBES
            )
            for tribe_name, overlap in counts.items():
                if overlap > 0:
                    matches.append((overlap, comm_idx, tribe_name))
        
        matches.sort(reverse=True, key=lambda x: x[0])
        
        matched_comms = set()
        claimed_tribes_today = set()
        comm_to_tribe = {}
        
        # 3. Conserver l'identité des tribus existantes
        for overlap, comm_idx, tribe_name in matches:
            if comm_idx not in matched_comms and tribe_name not in claimed_tribes_today:
                comm_to_tribe[comm_idx] = tribe_name
                matched_comms.add(comm_idx)
                claimed_tribes_today.add(tribe_name)
                
        # 4. Attribuer les noms libérés/disponibles (parmi A..E) aux nouvelles tribus
        available_names = [name for name in ALLOWED_TRIBES if name not in claimed_tribes_today]
        
        for comm_idx in range(len(valid_communities)):
            if comm_idx not in comm_to_tribe:
                assigned_name = available_names.pop(0)
                comm_to_tribe[comm_idx] = assigned_name
                claimed_tribes_today.add(assigned_name)
                
        # 5. Enregistrer les affectations de la journée
        for comm_idx, comm in enumerate(valid_communities):
            tribe_name = comm_to_tribe[comm_idx]
            for player in comm:
                current_assignments[player] = tribe_name

    # Les joueurs non classés dans les 5 tribus majeures deviennent "Inclassé"
    for player in player_counts:
        if player not in current_assignments:
            current_assignments[player] = "-"
            
    prev_date_assignments = current_assignments
    daily_tribes[d] = current_assignments

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
