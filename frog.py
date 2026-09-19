import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# 1. Configuration et chargement des données
config_path = Path("data/config/config.json")
if not config_path.exists():
    config_path = Path("data/config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config_data = json.load(f)

json_path = Path("data/rdl/archives/lh02/matches.json")
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 2. Traitement chronologique cumulatif
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

# 3. Moteur Louvain progressif à 3 tribus
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
MIN_TRIBE_SIZE = 5     # Taille minimale pour fonder/rejoindre une tribu
MIN_ACTIVE_MEMBERS = 3 # Plancher pour éviter les tribus fantômes
MAX_LEAGUES = 3

registered_tribes = []
prev_assignments = {}
daily_tribes = {}

for date_idx, d in enumerate(sorted_dates):
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    player_counts = Counter()
    pair_counts = Counter()
    
    for m in cumulative_matches:
        players = m["players"]
        for p in players:
            player_counts[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            pair_counts[(p1, p2)] += 1

    active_players = {p for p, count in player_counts.items() if count >= 3}

    season_progress = date_idx / max(1, len(sorted_dates) - 1)
    min_joint_matches = 2 + int(season_progress * 3)

    G = nx.Graph()
    G.add_nodes_from(active_players)

    for (p1, p2), joint_count in pair_counts.items():
        if p1 in active_players and p2 in active_players and joint_count >= min_joint_matches:
            total_unique = player_counts[p1] + player_counts[p2] - joint_count
            affinity = joint_count / total_unique if total_unique > 0 else 0
            
            if affinity >= 0.12:
                G.add_edge(p1, p2, weight=affinity)

    current_assignments = {}

    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            raw_communities = []

        valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]

        # Continuité historique par chevauchement maximal (Anti-hold-up)
        candidate_matches = []
        for comm_idx, comm in enumerate(valid_communities):
            history_counts = Counter(
                prev_assignments.get(p)
                for p in comm
                if prev_assignments.get(p) in registered_tribes
            )
            for tribe, count in history_counts.items():
                candidate_matches.append((count, comm_idx, tribe))

        # Tri par score d'ancienneté décroissant : le plus grand sous-groupe gagne le nom de sa tribu historique
        candidate_matches.sort(reverse=True, key=lambda x: x[0])

        assigned_communities = set()
        claimed_today = set()

        for count, comm_idx, tribe in candidate_matches:
            if comm_idx not in assigned_communities and tribe not in claimed_today:
                assigned_communities.add(comm_idx)
                claimed_today.add(tribe)
                for p in valid_communities[comm_idx]:
                    current_assignments[p] = tribe

        # Attribuer les clusters orphelins à de nouvelles tribus
        unassigned_communities = [
            comm for idx, comm in enumerate(valid_communities)
            if idx not in assigned_communities
        ]
        unassigned_communities.sort(key=len, reverse=True)

        for comm in unassigned_communities:
            if len(registered_tribes) < MAX_LEAGUES:
                new_tribe = ALLOWED_TRIBES[len(registered_tribes)]
                registered_tribes.append(new_tribe)
                claimed_today.add(new_tribe)
                for p in comm:
                    current_assignments[p] = new_tribe

    # Gestion de la rétention individuelle
    for p in player_counts:
        if p not in current_assignments:
            prev_tribe = prev_assignments.get(p)
            if prev_tribe in registered_tribes:
                current_assignments[p] = prev_tribe
            else:
                current_assignments[p] = "Inclassé"

    # Sécurité anti-tribu fantôme (< 3 membres)
    active_tribe_counts = Counter(current_assignments.values())
    for p, tribe in list(current_assignments.items()):
        if tribe in registered_tribes and active_tribe_counts[tribe] < MIN_ACTIVE_MEMBERS:
            current_assignments[p] = "Inclassé"

    prev_assignments = current_assignments
    daily_tribes[d] = current_assignments

# 4. Calcul de la loyauté pondérée par la taille de la table
player_games = Counter(p for m in matches_data for p in m["players"])
latest_date = sorted_dates[-1] if sorted_dates else ""
latest_tribes = daily_tribes.get(latest_date, {})

player_loyalty_sum = Counter()

for m in matches_data:
    players = m["players"]
    n_players = len(players)
    if n_players <= 1:
        continue
        
    for p in players:
        p_tribe = latest_tribes.get(p, "Inclassé")
        if p_tribe != "Inclassé":
            same_tribe_count = sum(
                1 for other in players 
                if other != p and latest_tribes.get(other, "Inclassé") == p_tribe
            )
            # Densité de la tribu sur la table (hors joueur lui-même)
            player_loyalty_sum[p] += same_tribe_count / (n_players - 1)

players_list = []
for name, count in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
    tribe = latest_tribes.get(name, "Inclassé")
    if tribe != "Inclassé":
        loyalty_score = player_loyalty_sum[name] / count if count > 0 else 0
        loyalty_pct = round(loyalty_score * 100)
        loyalty_str = f"{loyalty_pct} %"
        
        if loyalty_pct >= 60:
            status = "Noyau"
            status_style = "background:#2e7d32; color:#fff;"
        elif loyalty_pct >= 30:
            status = "Membre"
            status_style = "background:#1565c0; color:#fff;"
        else:
            status = "Fragile"
            status_style = "background:#c62828; color:#fff;"
    else:
        loyalty_str = "-"
        status = "Nomade"
        status_style = "background:#6c757d; color:#fff;"

    players_list.append({
        "name": name,
        "games": count,
        "tribe": tribe,
        "loyalty": loyalty_str,
        "status": status,
        "status_style": status_style
    })

# 5. Génération HTML
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

print(f"Analyse réussie : {len(sorted_dates)} dates calculées avec Max Overlap.")
