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

# --- SECTION 3: ORGANIC TRIBE ENGINE ---
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_PAIR_MATCHES = 2
CORE_CLIQUE_SIZE = 4
MAX_TRIBES = 5

registered_tribes = []
prev_assignments = {}
daily_tribes = {}

for current_date_str in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= current_date_str]
    
    player_matches = defaultdict(list)
    pair_counts = Counter()
    
    for idx, m in enumerate(cumulative_matches):
        players = m["players"]
        for p in players:
            player_matches[p].append(idx)
        for p1, p2 in combinations(sorted(players), 2):
            pair_counts[(p1, p2)] += 1

    # 1. Build interaction graph for strong links (>= 2 joint matches)
    G_core = nx.Graph()
    for (p1, p2), count in pair_counts.items():
        if count >= MIN_PAIR_MATCHES:
            G_core.add_edge(p1, p2)

    # 2. Detect core nuclei (cliques of at least 4 mutually linked players)
    cliques = [set(c) for c in nx.find_cliques(G_core) if len(c) >= CORE_CLIQUE_SIZE]
    cliques.sort(key=len, reverse=True)

    current_assignments = {}
    claimed_tribes = set()
    unmatched_cliques = []

    # Map core cliques to existing tribes using historical affinity
    for clique in cliques:
        history = Counter(prev_assignments.get(p) for p in clique if prev_assignments.get(p) in registered_tribes)
        valid_history = {t: cnt for t, cnt in history.items() if t not in claimed_tribes}
        
        if valid_history:
            assigned_tribe = max(valid_history, key=valid_history.get)
            claimed_tribes.add(assigned_tribe)
            for p in clique:
                current_assignments[p] = assigned_tribe
        else:
            unmatched_cliques.append(clique)

    # Unlock new tribes sequentially when new nuclei emerge
    if len(registered_tribes) < MAX_TRIBES:
        for clique in unmatched_cliques:
            if len(registered_tribes) < MAX_TRIBES:
                new_tribe = ALLOWED_TRIBES[len(registered_tribes)]
                registered_tribes.append(new_tribe)
                claimed_tribes.add(new_tribe)
                for p in clique:
                    current_assignments[p] = new_tribe

    # 3. Règle de la majorité qualifiée
    known_members = {p: t for p, t in current_assignments.items()}
    
    for p, match_indices in player_matches.items():
        if p in current_assignments:
            continue
            
        total_games = len(match_indices)
        
        # VERROU 1: Minimum 3 parties jouées dans la saison pour quitter "Inclassé"
        if total_games < 3:
            continue

        tribe_match_counts = Counter()
        for idx in match_indices:
            m_players = cumulative_matches[idx]["players"]
            match_tribes = {known_members[other] for other in m_players if other != p and other in known_members}
            for t in match_tribes:
                tribe_match_counts[t] += 1

        best_tribe, best_count = tribe_match_counts.most_common(1)[0] if tribe_match_counts else (None, 0)
        
        # VERROU 2: Minimum 2 matchs partagés ET > 50% des parties
        if best_tribe and best_count >= 2 and (best_count / total_games) > 0.50:
            current_assignments[p] = best_tribe

    # 4. Unassigned players default to "Inclassé"
    for p in player_matches:
        if p not in current_assignments:
            current_assignments[p] = "Inclassé"

    prev_assignments = current_assignments
    daily_tribes[current_date_str] = current_assignments

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
