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

# 4. Calcul de Louvain : Émergence progressive + Persistance permanente
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_MATCHES = 3
NEW_TRIBE_THRESHOLD = 6  # Seuil plus élevé pour ralentir l'émergence des nouvelles tribus
MAX_LEAGUES = 5

registered_tribes = []   # Registre permanent des tribus déjà créées
prev_date_assignments = {}  # {player: tribe_name} à T-1
daily_tribes = {}

for d in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    player_counts = Counter()
    for m in cumulative_matches:
        for p in m["players"]:
            player_counts[p] += 1
            
    active_players = {p for p, count in player_counts.items() if count >= MIN_MATCHES}
    
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
            
        # 1. Protection contre les fusions : Scission si Louvain regroupe deux tribus permanentes
        split_communities = []
        for comm in raw_communities:
            existing_in_comm = Counter(
                prev_date_assignments.get(p) 
                for p in comm 
                if prev_date_assignments.get(p) in registered_tribes
            )
            # Repérer les tribus historiques ayant au moins 2 membres dans ce cluster
            present_tribes = [t for t, count in existing_in_comm.items() if count >= 2]
            
            if len(present_tribes) > 1:
                # Scission : chaque tribu conserve son noyau
                sub_groups = {t: set() for t in present_tribes}
                unassigned = set()
                for p in comm:
                    p_tribe = prev_date_assignments.get(p)
                    if p_tribe in sub_groups:
                        sub_groups[p_tribe].add(p)
                    else:
                        unassigned.add(p)
                        
                # Attribution des joueurs neutres vers le noyau le plus connecté
                for p in unassigned:
                    best_t = max(
                        sub_groups.keys(),
                        key=lambda t: sum(G[p][n].get('weight', 1) for n in sub_groups[t] if G.has_edge(p, n)),
                        default=present_tribes[0]
                    )
                    sub_groups[best_t].add(p)
                    
                for sg in sub_groups.values():
                    split_communities.append(sg)
            else:
                split_communities.append(comm)

        # 2. Assignation prioritaire aux tribus déjà enregistrées
        claimed_tribes_today = set()
        unmatched_communities = []

        for comm in split_communities:
            counts = Counter(
                prev_date_assignments.get(p) 
                for p in comm 
                if prev_date_assignments.get(p) in registered_tribes
            )
            valid_counts = {t: c for t, c in counts.items() if t not in claimed_tribes_today}
            
            if valid_counts:
                best_tribe = max(valid_counts, key=valid_counts.get)
                claimed_tribes_today.add(best_tribe)
                for player in comm:
                    current_assignments[player] = best_tribe
            else:
                unmatched_communities.append(comm)

        # 3. Émergence contrôlée (Déverrouillage progressif de nouvelles tribus)
        if len(registered_tribes) < MAX_LEAGUES:
            unmatched_communities.sort(key=len, reverse=True)
            for comm in unmatched_communities:
                if len(comm) >= NEW_TRIBE_THRESHOLD and len(registered_tribes) < MAX_LEAGUES:
                    new_tribe_name = ALLOWED_TRIBES[len(registered_tribes)]
                    registered_tribes.append(new_tribe_name)
                    claimed_tribes_today.add(new_tribe_name)
                    for player in comm:
                        current_assignments[player] = new_tribe_name

    # Les joueurs hors tribus majeures restent Inclassés
    for player in player_counts:
        if player not in current_assignments:
            current_assignments[player] = "Inclassé"
            
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
