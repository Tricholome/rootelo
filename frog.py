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

# 2. Charger les matchs depuis les archives
json_path = Path("data/rdl/archives/lh02/matches.json")
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 3. Traiter les matchs et dates chronologiques
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

# 4. Calcul des tribus avec filtrage Jaccard + Louvain + Persistance
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_ABSOLUTE_MATCHES = 2     # Au moins 2 matchs partagés
MIN_JACCARD_AFFINITY = 0.15  # 15% d'affinité relative minimum
MIN_TRIBE_SIZE = 5           # Taille minimale d'une tribu
MAX_LEAGUES = 5

registered_tribes = []       # Liste des tribus permanentes apparues au fil de la saison
prev_date_assignments = {}   # Affectations à T-1
daily_tribes = {}

for d in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    player_counts = Counter()
    pair_counts = Counter()
    
    for m in cumulative_matches:
        players = m["players"]
        for p in players:
            player_counts[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            pair_counts[(p1, p2)] += 1

    # Construction du graphe d'affinité (Jaccard auto-adaptatif)
    G = nx.Graph()
    for (p1, p2), joint_games in pair_counts.items():
        if joint_games >= MIN_ABSOLUTE_MATCHES:
            total_unique_games = player_counts[p1] + player_counts[p2] - joint_games
            affinity = joint_games / total_unique_games if total_unique_games > 0 else 0
            
            if affinity >= MIN_JACCARD_AFFINITY:
                G.add_edge(p1, p2, weight=affinity)
                
    current_assignments = {}
    
    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            raw_communities = []
            
        valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]
        
        # Attribution prioritaire aux tribus déjà débloquées à T-1
        claimed_today = set()
        unassigned_communities = []

        for comm in valid_communities:
            counts = Counter(
                prev_date_assignments.get(p) 
                for p in comm 
                if prev_date_assignments.get(p) in registered_tribes
            )
            valid_counts = {t: cnt for t, cnt in counts.items() if t not in claimed_today}
            
            if valid_counts:
                best_tribe = max(valid_counts, key=valid_counts.get)
                claimed_today.add(best_tribe)
                for p in comm:
                    current_assignments[p] = best_tribe
            else:
                unassigned_communities.append(comm)

        # Création progressive de nouvelles tribus (jusqu'à 5 max)
        if len(registered_tribes) < MAX_LEAGUES:
            unassigned_communities.sort(key=len, reverse=True)
            for comm in unassigned_communities:
                if len(registered_tribes) < MAX_LEAGUES:
                    new_tribe_name = ALLOWED_TRIBES[len(registered_tribes)]
                    registered_tribes.append(new_tribe_name)
                    claimed_today.add(new_tribe_name)
                    for p in comm:
                        current_assignments[p] = new_tribe_name

    # Les joueurs hors tribus restent Inclassés
    for player in player_counts:
        if player not in current_assignments:
            current_assignments[player] = "Inclassé"
            
    prev_date_assignments = current_assignments
    daily_tribes[d] = current_assignments

# 5. Préparation des données pour Jinja2
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

print(f"Page '{output_path}' générée avec succès ({len(sorted_dates)} dates analysées).")
