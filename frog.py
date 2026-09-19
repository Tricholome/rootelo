import networkx as nx
from collections import Counter
from itertools import combinations

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

# --- SECTION 3: LOUVAIN PROGRESSIF & PERSISTANT ---
ALLOWED_TRIBES = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]
MIN_TRIBE_SIZE = 5     # Un cluster Louvain doit faire au moins 5 membres pour devenir une tribu
MAX_LEAGUES = 5

registered_tribes = [] # Registre des tribus débloquées au fil de la saison
prev_assignments = {}  # {player: tribe_name} au jour T-1
daily_tribes = {}

for d in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    # 1. Compter le nombre de parties simples et partagées
    player_counts = Counter()
    pair_counts = Counter()
    for m in cumulative_matches:
        players = m["players"]
        for p in players:
            player_counts[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            pair_counts[(p1, p2)] += 1

    # 2. Construction du graphe (poids = nombre de matchs ensemble)
    G = nx.Graph()
    for (p1, p2), w in pair_counts.items():
        G.add_edge(p1, p2, weight=w)

    current_assignments = {}

    if G.number_of_nodes() > 0:
        # 3. Algorithme de Louvain
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            raw_communities = []

        # Ne retenir que les clusters significatifs (>= 5 joueurs)
        valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]

        # 4. Association avec les tribus existantes (Continuité historique)
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
                # Le cluster reprend la tribu historique avec laquelle il a le plus d'affinité
                assigned_tribe = max(valid_history, key=valid_history.get)
                claimed_today.add(assigned_tribe)
                for p in comm:
                    current_assignments[p] = assigned_tribe
            else:
                unassigned_communities.append(comm)

        # 5. Déverrouillage progressif de nouvelles tribus (1 par 1 au fil des semaines)
        unassigned_communities.sort(key=len, reverse=True)
        for comm in unassigned_communities:
            if len(registered_tribes) < MAX_LEAGUES:
                new_tribe_name = ALLOWED_TRIBES[len(registered_tribes)]
                registered_tribes.append(new_tribe_name)
                claimed_today.add(new_tribe_name)
                for p in comm:
                    current_assignments[p] = new_tribe_name

    # 6. Tous les joueurs hors des grands clusters Louvain restent "Inclassé"
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
