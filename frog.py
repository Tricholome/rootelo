import json
import math
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES (À AJUSTER SELON TES BESOINS)
# ==============================================================================

# --- 1. Noms et Limites des Tribus ---
TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
MIN_TRIBE_SIZE = 5        # Nb min de membres pour valider une communauté Louvain
MIN_ACTIVE_MEMBERS = 3    # Nb min de membres pour éviter de conserver une tribu fantôme
CORE_TOP_N = 3            # Nombre de piliers suivis par tribu (Core Anchoring)

# --- 2. Graphe & Filtrage des Connexions ---
MIN_PLAYER_GAMES_GRAPH = 3  # Nb min de parties d'un joueur pour entrer dans le graphe
MIN_JOINT_BASE = 2          # Nb min de parties communes (début de saison)
MIN_JOINT_SLOPE = 3         # Facteur d'augmentation des parties communes en fin de saison
MIN_COSINE_WEIGHT = 0.12    # Seuil minimal de similarité Cosinus pour relier deux joueurs
LOUVAIN_SEED = 42           # Graine de reproductibilité pour Louvain

# --- 3. Filtrage du Volume (Volume Guardrail) ---
MEDIAN_RATIO_THRESHOLD = 0.30  # % de la médiane globale requis (ex: 0.30 = 30 %)
MIN_GAMES_FLOOR = 3            # Plancher absolu de parties (quel que soit le résultat de la médiane)

# --- 4. Attribution & Affiliation (Loyalty Rules) ---
MIN_LOYALTY_PCT = 30      # Loyauté minimale (%) requise dans la tribu cible pour y être classé

# --- 5. Seuils d'Affichage & Badges (Frontend) ---
STATUS_CORE_PCT = 60      # Loyauté >= 60 % -> Badge "Noyau"
STATUS_MEMBER_PCT = 30    # Loyauté >= 30 % -> Badge "Membre" (< 30 % -> "Fragile")
DISPLAY_MIN_PCT = 10      # Loyauté < 10 % -> Masqué ("-") dans le tableau

# --- 6. Fichiers et Chemins ---
CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 EXECUTION DU TRAITEMENT
# ==============================================================================

# 1. Chargement de la configuration
config_path = CONFIG_PATH if CONFIG_PATH.exists() else Path("data/config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config_data = json.load(f)

json_path = DEFAULT_MATCHES_PATH
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

def get_community_core(community_nodes, G, top_n=CORE_TOP_N):
    """Identifie les piliers d'une tribu via leur centralité de degré au sein du sous-graphe."""
    subgraph = G.subgraph(community_nodes)
    centrality = nx.degree_centrality(subgraph)
    return sorted(centrality.keys(), key=lambda x: centrality[x], reverse=True)[:top_n]

snapshots = {}
previous_cores = {}
daily_tribes = {}
prev_assignments = {}

# 3. Boucle temporelle
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

    active_players = {p for p, count in player_counts.items() if count >= MIN_PLAYER_GAMES_GRAPH}
    season_progress = date_idx / max(1, len(sorted_dates) - 1)
    min_joint_matches = MIN_JOINT_BASE + int(season_progress * MIN_JOINT_SLOPE)

    # ÉTAPE A : Construction du Graphe (Similarité Cosinus)
    G = nx.Graph()
    G.add_nodes_from(active_players)

    for (p1, p2), joint_count in pair_counts.items():
        if p1 in active_players and p2 in active_players and joint_count >= min_joint_matches:
            weight = joint_count / math.sqrt(player_counts[p1] * player_counts[p2])
            if weight >= MIN_COSINE_WEIGHT:
                G.add_edge(p1, p2, weight=weight)

    # ÉTAPE B : Détection Louvain et Core Anchoring
    raw_communities = []
    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=LOUVAIN_SEED))
        except Exception:
            pass

    valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]
    
    current_assignments = {}
    current_cores = {}
    
    if not previous_cores:
        # Initialisation (Jour 1)
        for idx, comm in enumerate(valid_communities):
            if idx < len(TARGET_TRIBES):
                tribe_name = TARGET_TRIBES[idx]
                current_cores[tribe_name] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = tribe_name
    else:
        # Suivi par l'inertie des noyaux
        assigned_tribes = set()
        
        for comm in valid_communities:
            best_match = None
            max_core_overlap = 0
            
            for tribe_name, old_core in previous_cores.items():
                if tribe_name in assigned_tribes:
                    continue
                overlap = len(set(comm).intersection(set(old_core)))
                if overlap > max_core_overlap:
                    max_core_overlap = overlap
                    best_match = tribe_name
            
            if best_match:
                assigned_tribes.add(best_match)
                current_cores[best_match] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = best_match
                    
        # Remplacement de tribus disparues
        unassigned_comms = [c for c in valid_communities if not any(p in current_assignments for p in c)]
        for comm in unassigned_comms:
            available_tribes = [t for t in TARGET_TRIBES if t not in assigned_tribes]
            if available_tribes:
                new_tribe = available_tribes[0]
                assigned_tribes.add(new_tribe)
                current_cores[new_tribe] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = new_tribe

    # ÉTAPE C : Rattrapage inertiel et nettoyage
    for p in player_counts:
        if p not in current_assignments:
            prev_tribe = prev_assignments.get(p, "Inclassé")
            if prev_tribe in current_cores:
                current_assignments[p] = prev_tribe
            else:
                current_assignments[p] = "Inclassé"

    active_tribe_counts = Counter(current_assignments.values())
    for p, tribe in list(current_assignments.items()):
        if tribe in TARGET_TRIBES and active_tribe_counts[tribe] < MIN_ACTIVE_MEMBERS:
            current_assignments[p] = "Inclassé"

    daily_tribes[d] = current_assignments
    previous_cores = current_cores
    prev_assignments = current_assignments

    # ÉTAPE D : Loyauté, Médiane et Arbitrage Métier
    player_loyalty_sum = {p: Counter() for p in player_counts}
    for m in cumulative_matches:
        players = m["players"]
        n_players = len(players)
        if n_players <= 1:
            continue
        for p in players:
            for other in players:
                if other != p:
                    other_tribe = current_assignments.get(other, "Inclassé")
                    if other_tribe in TARGET_TRIBES:
                        player_loyalty_sum[p][other_tribe] += 1 / (n_players - 1)

    # Seuil dynamique de volume
    all_counts = list(player_counts.values())
    global_median = statistics.median(all_counts) if all_counts else 0
    min_games_tribe = max(MIN_GAMES_FLOOR, math.ceil(global_median * MEDIAN_RATIO_THRESHOLD))

    tribe_summary = {t: 0 for t in TARGET_TRIBES + ["Inclassé"]}
    snapshot_players = []

    for name, count in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        # Repérage du meilleur score de loyauté
        scores = {}
        max_tribe = None
        max_pct = -1
        for t in TARGET_TRIBES:
            score = player_loyalty_sum[name][t] / count if count > 0 else 0
            pct = round(score * 100)
            scores[t] = pct
            if pct > max_pct:
                max_pct = pct
                max_tribe = t

        # Règle d'arbitrage unifiée & équitable
        if count < min_games_tribe or max_pct < MIN_LOYALTY_PCT:
            final_tribe = "Inclassé"
        else:
            final_tribe = max_tribe

        tribe_summary[final_tribe] = tribe_summary.get(final_tribe, 0) + 1

        # Attribution des badges
        formatted_scores = {}
        for t in TARGET_TRIBES:
            pct = scores[t]
            status = None
            if t == final_tribe:
                if pct >= STATUS_CORE_PCT:
                    status = "Noyau"
                elif pct >= STATUS_MEMBER_PCT:
                    status = "Membre"
                else:
                    status = "Fragile"
            
            formatted_scores[t] = {
                "pct": pct,
                "status": status
            }

        snapshot_players.append({
            "name": name,
            "games": count,
            "main_tribe": final_tribe,
            "scores": formatted_scores
        })

    snapshots[d] = {
        "summary": tribe_summary,
        "players": snapshot_players
    }

# 4. Génération HTML
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.globals["config"] = config_data
template = env.get_template(TEMPLATE_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        snapshots_json=json.dumps(snapshots, ensure_ascii=False), 
        dates_json=json.dumps(sorted_dates, ensure_ascii=False)
    ))

print(f"Analyse réussie : {len(sorted_dates)} dates calculées.")
