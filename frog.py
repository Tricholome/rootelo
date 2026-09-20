import json
import math
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES
# ==============================================================================

MAX_DAILY_TRANSFERS = 3       # Max migrations autorisées par jour
MAX_TRIBES = 3                # Limite absolue de tribus
MIN_TRIBE_SIZE_LOUVAIN = 4    # Taille mini pour qu'un cluster soit valide dans Louvain
MIN_TRIBE_SURVIVAL = 2        # Dissolution d'une tribu si moins de 2 membres
MIN_GAMES_FLOOR = 3           # Plancher absolu de matchs
DYNAMIC_RATIO = 0.40          # Ratio de la médiane (ex: 40 %) pour élever le seuil

DECAY_RATE = 0.95             # Dépréciation temporelle des arêtes
NEW_MATCH_WEIGHT = 1.0        # Poids d'un nouveau match
UNALIGNED_LABEL = "-"         # Étiquette des joueurs non alignés

TRIBE_NAMES_POOL = ["Tribe A", "Tribe B", "Tribe C"]

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 CHARGEMENT DES CONFIGURATIONS ET DONNÉES
# ==============================================================================

config_path = CONFIG_PATH
if not config_path.exists():
    configs = list(Path(".").rglob("config.json"))
    if configs:
        config_path = configs[0]

config_data = {}
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    json_path = archives[0] if archives else Path("matches.json")

if not json_path.exists():
    print(f"❌ Erreur : Fichier de matchs introuvable à {json_path}")
    exit(1)

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

matches_by_date = {}
for m in matches:
    date_str = str(m.get("Date") or m.get("date") or m.get("date_closed") or "")[:10]
    players = [p.get("name") for p in m.get("players", []) if p.get("name")]
    if date_str and players:
        matches_by_date.setdefault(date_str, []).append(players)

sorted_dates = sorted(matches_by_date.keys())

# ==============================================================================
# 🧠 MOTEUR D'ÉTAT : LOUVAIN BRIDÉ ET VERROUILLÉ
# ==============================================================================

edge_weights = Counter()
player_games = Counter()

current_roster = {}  
active_tribes = []   
snapshots = {}

for d in sorted_dates:
    # 1. Atténuation & Ajout des nouveaux matchs du jour
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE
        
    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
            if p not in current_roster:
                current_roster[p] = UNALIGNED_LABEL
        for p1, p2 in combinations(sorted(players), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    # --------------------------------------------------------------------------
    # 🎯 CALCUL DU SEUIL DYNAMIQUE ET PURGE DES INACTIFS
    # --------------------------------------------------------------------------
    all_games = list(player_games.values())
    global_median = statistics.median(all_games) if all_games else 0
    global_min_games = max(MIN_GAMES_FLOOR, math.ceil(global_median * DYNAMIC_RATIO))

    # PURGE : Expulsion directe des membres sous le seuil dynamique du jour
    for p, curr_t in list(current_roster.items()):
        if curr_t != UNALIGNED_LABEL:
            tribe_members = [m for m, t in current_roster.items() if t == curr_t]
            tribe_median = statistics.median([player_games[m] for m in tribe_members]) if tribe_members else 0
            required_games = max(global_min_games, math.ceil(tribe_median * DYNAMIC_RATIO))
            
            if player_games[p] < required_games:
                current_roster[p] = UNALIGNED_LABEL

    # Construction du graphe NetworkX
    G = nx.Graph()
    for (p1, p2), w in edge_weights.items():
        if w >= 0.1:
            G.add_edge(p1, p2, weight=w)

    # 2. La Boussole : Louvain pour identifier l'idéal théorique
    ideal_assignments = {p: UNALIGNED_LABEL for p in G.nodes()}
    
    if G.number_of_nodes() > 0:
        try:
            raw_comms = sorted(nx.community.louvain_communities(G, weight="weight", seed=42), key=len, reverse=True)
        except Exception:
            raw_comms = []

        valid_comms = [c for c in raw_comms if len(c) >= MIN_TRIBE_SIZE_LOUVAIN][:MAX_TRIBES]
        
        used_ideal_names = set()
        community_mapping = {}
        
        # PASSE 1 : Continuité avec les tribus existantes
        for i, comm in enumerate(valid_comms):
            best_name = None
            max_intersect = 0
            for t_name in active_tribes:
                if t_name not in used_ideal_names:
                    current_members = {p for p, t in current_roster.items() if t == t_name}
                    intersect = len(comm.intersection(current_members))
                    if intersect > max_intersect and intersect > 0:
                        max_intersect = intersect
                        best_name = t_name
            
            if best_name:
                community_mapping[i] = best_name
                used_ideal_names.add(best_name)
        
        # PASSE 2 : Nouveaux clusters depuis le pool autorisé
        available_names = [n for n in TRIBE_NAMES_POOL if n not in used_ideal_names]
        for i in range(len(valid_comms)):
            if i not in community_mapping and available_names:
                new_name = available_names.pop(0)
                community_mapping[i] = new_name
                used_ideal_names.add(new_name)
                
        for i, comm in enumerate(valid_comms):
            name = community_mapping.get(i)
            if name:
                for p in comm:
                    ideal_assignments[p] = name

    # 3. Le Goulot d'étranglement (Quota de transfert)
    pending_migrations = []
    
    for p in G.nodes():
        curr_t = current_roster.get(p, UNALIGNED_LABEL)
        ideal_t = ideal_assignments.get(p, UNALIGNED_LABEL)
        
        # Calcul du seuil d'accès requis pour la tribu visée
        req_games = global_min_games
        if ideal_t != UNALIGNED_LABEL:
            t_members = [m for m, t in current_roster.items() if t == ideal_t]
            if t_members:
                t_median = statistics.median([player_games[m] for m in t_members])
                req_games = max(global_min_games, math.ceil(t_median * DYNAMIC_RATIO))

        # Condition de migration : le joueur doit avoir atteint req_games
        if curr_t != ideal_t and player_games[p] >= req_games:
            w_ideal = sum(G[p][n]["weight"] for n in G.neighbors(p) if ideal_assignments.get(n) == ideal_t) if ideal_t != UNALIGNED_LABEL else 0
            w_curr = sum(G[p][n]["weight"] for n in G.neighbors(p) if current_roster.get(n) == curr_t) if curr_t != UNALIGNED_LABEL else 0
            
            urgency = w_ideal - w_curr
            if ideal_t == UNALIGNED_LABEL and curr_t != UNALIGNED_LABEL:
                urgency = 0.5 
            
            pending_migrations.append({
                "player": p,
                "from": curr_t,
                "to": ideal_t,
                "urgency": urgency
            })

    pending_migrations.sort(key=lambda x: x["urgency"], reverse=True)
    
    allowed_moves = pending_migrations if len(active_tribes) == 0 else pending_migrations[:MAX_DAILY_TRANSFERS]
        
    for move in allowed_moves:
        current_roster[move["player"]] = move["to"]

    # 4. Nettoyage & Mortalité
    tribe_counts = Counter(current_roster.values())
    for t in list(active_tribes):
        if tribe_counts[t] < MIN_TRIBE_SURVIVAL:
            for p, t_assigned in list(current_roster.items()):
                if t_assigned == t:
                    current_roster[p] = UNALIGNED_LABEL
                    
    active_tribes = sorted({t for t in current_roster.values() if t != UNALIGNED_LABEL})

    # 5. Formatage pour Jinja2
    snapshot_players = []
    tribe_summary = {t: 0 for t in active_tribes + [UNALIGNED_LABEL]}
    
    for p, games in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        main_t = current_roster.get(p, UNALIGNED_LABEL)
        tribe_summary[main_t] = tribe_summary.get(main_t, 0) + 1
        
        scores = {}
        if p in G and G.degree(p) > 0:
            total_w = sum(G[p][n]["weight"] for n in G.neighbors(p))
            for t in active_tribes:
                t_w = sum(G[p][n]["weight"] for n in G.neighbors(p) if current_roster.get(n) == t)
                pct = round((t_w / total_w) * 100) if total_w > 0 else 0
                
                status = "Wavering"
                if t == main_t:
                    status = "Loyalist" if pct >= 55 else "Affiliate"
                scores[t] = {"pct": pct, "status": status}
        else:
            scores = {t: {"pct": 0, "status": "Wavering"} for t in active_tribes}
            
        snapshot_players.append({
            "name": p,
            "games": games,
            "main_tribe": main_t,
            "scores": scores
        })
        
    snapshots[d] = {
        "active_tribes": active_tribes,
        "summary": tribe_summary,
        "players": snapshot_players
    }

# ==============================================================================
# 🎨 GÉNÉRATION HTML
# ==============================================================================

if Path(TEMPLATE_DIR).exists() and (Path(TEMPLATE_DIR) / TEMPLATE_FILE).exists():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(TEMPLATE_FILE)
    
    html_content = template.render(
        config=config_data,
        active_section="frog",
        dates_json=json.dumps(sorted_dates),
        snapshots_json=json.dumps(snapshots)
    )
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Fichier {OUTPUT_FILE} généré avec succès.")
else:
    print(f"⚠️ Template {TEMPLATE_DIR}/{TEMPLATE_FILE} introuvable.")
