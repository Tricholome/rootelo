import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# 1. Chargement des configurations et archives
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

# 2. Traitement chronologique cumulatif
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

# 3. Moteur de calcul par Exclusivité Relative
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_MATCHES_THRESHOLD = 3   # Joueur actif s'il a joué au moins 3 matchs
EXCLUSIVITY_THRESHOLD = 0.22 # Seuil d'exclusivité minimum pour créer un lien fort (0.0 à 1.0)
MIN_TRIBE_SIZE = 4
MAX_LEAGUES = 5

registered_tribes = []
prev_assignments = {}
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

    # Construction du graphe pondéré par l'exclusivité relative
    G = nx.Graph()
    active_players = {p for p, count in player_counts.items() if count >= MIN_MATCHES_THRESHOLD}
    G.add_nodes_from(active_players)

    for (p1, p2), joint_matches in pair_counts.items():
        if p1 in active_players and p2 in active_players:
            # Calcul du poids normalisé par les totaux cumulés des deux joueurs
            norm_weight = joint_matches / math.sqrt(player_counts[p1] * player_counts[p2])
            
            if norm_weight >= EXCLUSIVITY_THRESHOLD:
                G.add_edge(p1, p2, weight=norm_weight)

    current_assignments = {}
    if G.number_of_nodes() > 0:
        try:
            communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            communities = []

        # Ne retenir que les noyaux d'au moins MIN_TRIBE_SIZE joueurs
        valid_communities = [c for c in communities if len(c) >= MIN_TRIBE_SIZE]
        
        # Suivi temporel par proximité historique (Continuite)
        claimed_today = set()
        unmatched_comms = []

        for comm in valid_communities:
            history = Counter(prev_assignments.get(p) for p in comm if prev_assignments.get(p) in registered_tribes)
            valid_history = {t: cnt for t, cnt in history.items() if t not in claimed_today}
            
            if valid_history:
                assigned_name = max(valid_history, key=valid_history.get)
                claimed_today.add(assigned_name)
                for p in comm:
                    current_assignments[p] = assigned_name
            else:
                unmatched_comms.append(comm)

        # Déverrouillage progressif des nouvelles tribus (jusqu'à 5 max)
        if len(registered_tribes) < MAX_LEAGUES:
            unmatched_comms.sort(key=len, reverse=True)
            for comm in unmatched_comms:
                if len(registered_tribes) < MAX_LEAGUES:
                    new_name = ALLOWED_TRIBES[len(registered_tribes)]
                    registered_tribes.append(new_name)
                    claimed_today.add(new_name)
                    for p in comm:
                        current_assignments[p] = new_name

    # Les joueurs sans liens d'exclusivité forts restent Inclassés
    for p in player_counts:
        if p not in current_assignments:
            current_assignments[p] = "Inclassé"

    prev_assignments = current_assignments
    daily_tribes[d] = current_assignments

# 4. Génération de la page HTML via Jinja2
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

print(f"Calcul terminé : {len(sorted_dates)} dates analysées avec la métrique d'exclusivité.")
