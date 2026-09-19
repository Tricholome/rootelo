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

# 3. Moteur Louvain progressif à sévérité dynamique & persistance
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_TRIBE_SIZE = 5     # Taille minimale d'un cluster pour former/rejoindre une tribu
MAX_LEAGUES = 5

registered_tribes = [] # Registre permanent des tribus débloquées
prev_assignments = {}  # Historique à T-1 {player: tribe_name}
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

    # RÈGLE 1 : Exclusion stricte des joueurs occasionnels (<= 2 matchs au total)
    active_players = {p for p, count in player_counts.items() if count >= 3}

    # RÈGLE 2 : Sévérité progressive de la saison (de 2 matchs partagés à 5)
    season_progress = date_idx / max(1, len(sorted_dates) - 1)
    min_joint_matches = 2 + int(season_progress * 3)

    # Construction du graphe restreint aux joueurs actifs et liens significatifs
    G = nx.Graph()
    G.add_nodes_from(active_players)

    for (p1, p2), joint_count in pair_counts.items():
        if p1 in active_players and p2 in active_players and joint_count >= min_joint_matches:
            # Affinité relative (Jaccard) pour privilégier l'exclusivité des interactions
            total_unique = player_counts[p1] + player_counts[p2] - joint_count
            affinity = joint_count / total_unique if total_unique > 0 else 0
            
            if affinity >= 0.12:  # Seuil de pertinence minimum
                G.add_edge(p1, p2, weight=affinity)

    current_assignments = {}

    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            raw_communities = []

        valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]

        # RÈGLE 3 : Continuité historique sans fusions destructrices
        claimed_today = set()
        unassigned_communities = []

        for comm in valid_communities:
            history_counts = Counter(
                prev_assignments.get(p)
                for p in comm
                if prev_assignments.get(p) in registered_tribes
            )
            valid_history = {t: cnt for t, cnt in history_counts.items() if t not in claimed_today}

            if valid_history:
                assigned_tribe = max(valid_history, key=valid_history.get)
                claimed_today.add(assigned_tribe)
                for p in comm:
                    current_assignments[p] = assigned_tribe
            else:
                unassigned_communities.append(comm)

        # Déverrouillage contrôlé de nouvelles tribus
        unassigned_communities.sort(key=len, reverse=True)
        for comm in unassigned_communities:
            if len(registered_tribes) < MAX_LEAGUES:
                new_tribe = ALLOWED_TRIBES[len(registered_tribes)]
                registered_tribes.append(new_tribe)
                claimed_today.add(new_tribe)
                for p in comm:
                    current_assignments[p] = new_tribe

    # RÈGLE 4 : Rétention des acquis vs statut Inclassé
    for p in player_counts:
        if p not in current_assignments:
            prev_tribe = prev_assignments.get(p)
            # Un joueur déjà membre d'une tribu enregistrée conserve son appartenance
            if prev_tribe in registered_tribes:
                current_assignments[p] = prev_tribe
            else:
                current_assignments[p] = "Inclassé"

    prev_assignments = current_assignments
    daily_tribes[d] = current_assignments

# 4. Génération de la page HTML via Jinja2
player_games = Counter(p for m in matches_data for p in m["players"])
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

output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        players=players_list,
        matches_json=json.dumps(matches_data, ensure_ascii=False),
        dates_json=json.dumps(sorted_dates, ensure_ascii=False),
        tribes_json=json.dumps(daily_tribes, ensure_ascii=False)
    ))

print(f"Génération réussie : {len(sorted_dates)} dates analysées.")
