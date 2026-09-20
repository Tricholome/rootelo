import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES
# ==============================================================================

TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"

# --- NIVEAU MACRO (Louvain) ---
LOUVAIN_INTERVAL_DAYS = 14  # Re-calcul des communautés tous les 14 jours
MIN_GAMES_MACRO = 3         # Matchs min pour entrer dans le graphe Louvain
RESOLUTION_LOUVAIN = 1.3

# --- NIVEAU MICRO (Probation & Affichage) ---
PROBATION_DAYS_REQUIRED = 5 # Nombre de jours de régularité requis pour valider une tribu
MIN_GAMES_FLOOR = 3
STATUS_LOYAL_PCT = 55
STATUS_AFFILIATE_PCT = 35

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 CHARGEMENT DES DONNÉES
# ==============================================================================

config_path = CONFIG_PATH if CONFIG_PATH.exists() else Path("data/config.json")
config_data = json.load(open(config_path, "r", encoding="utf-8")) if config_path.exists() else {}

json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

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

# ==============================================================================
# 🧠 MOTEUR DOUBLE VITESSE
# ==============================================================================

snapshots = {}

# Mémoire Macro (Louvain)
active_macro_cores = {}
last_louvain_date_idx = -LOUVAIN_INTERVAL_DAYS

# Mémoire Micro (Probation individuelle)
# { player_name: {"candidate_tribe": str, "consecutive_days": int, "official_tribe": str} }
player_probation = {}

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

    # --------------------------------------------------------------------------
    # 1. ARRIÈRE-PLAN : MISE À JOUR MACRO PAR LOUVAIN (Tous les N jours)
    # --------------------------------------------------------------------------
    should_run_louvain = (date_idx - last_louvain_date_idx) >= LOUVAIN_INTERVAL_DAYS or not active_macro_cores

    if should_run_louvain:
        G = nx.Graph()
        active_players = {p for p, c in player_counts.items() if c >= MIN_GAMES_MACRO}
        G.add_nodes_from(active_players)

        for (p1, p2), joint_count in pair_counts.items():
            if p1 in active_players and p2 in active_players:
                weight = joint_count / math.sqrt(player_counts[p1] * player_counts[p2])
                if weight >= 0.15:
                    G.add_edge(p1, p2, weight=weight)

        raw_communities = []
        if G.number_of_nodes() > 0:
            try:
                raw_communities = list(nx.community.louvain_communities(G, weight="weight", resolution=RESOLUTION_LOUVAIN, seed=42))
            except Exception:
                pass

        # Ne garder que les 3 plus grandes communautés
        raw_communities = sorted(raw_communities, key=len, reverse=True)[:len(TARGET_TRIBES)]
        
        # Extraire le "Core" (top 2 joueurs les plus centraux) de chaque communauté
        new_cores = {}
        for idx, comm in enumerate(raw_communities):
            subgraph = G.subgraph(comm)
            centrality = nx.degree_centrality(subgraph)
            top_2 = sorted(centrality.keys(), key=lambda x: centrality[x], reverse=True)[:2]
            
            # Attribuer un nom de tribu stable
            tribe_name = TARGET_TRIBES[idx] if idx < len(TARGET_TRIBES) else f"Tribe {idx}"
            new_cores[tribe_name] = top_2

        # Raccordement des noms avec la session macro précédente
        if active_macro_cores:
            mapped_cores = {}
            available_names = TARGET_TRIBES.copy()
            for t_new, core_players in new_cores.items():
                best_match = None
                max_overlap = 0
                for t_old, old_players in active_macro_cores.items():
                    if t_old in available_names:
                        overlap = len(set(core_players).intersection(set(old_players)))
                        if overlap > max_overlap:
                            max_overlap = overlap
                            best_match = t_old
                
                assigned_name = best_match if best_match else (available_names[0] if available_names else t_new)
                if assigned_name in available_names:
                    available_names.remove(assigned_name)
                mapped_cores[assigned_name] = core_players
            
            active_macro_cores = mapped_cores
        else:
            active_macro_cores = new_cores

        last_louvain_date_idx = date_idx

    # --------------------------------------------------------------------------
    # 2. PREMIER PLAN : ÉVOLUTION QUOTIDIENNE ET SAS DE PROBATION
    # --------------------------------------------------------------------------
    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}
    snapshot_players = []

    for name, games_played in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        
        # Calcul des affinités brutes avec les noyaux macro actuels
        raw_scores = {}
        total_weight = 0.0

        for t_name in TARGET_TRIBES:
            if t_name in active_macro_cores:
                core_p1, core_p2 = active_macro_cores[t_name][0], (active_macro_cores[t_name][1] if len(active_macro_cores[t_name]) > 1 else active_macro_cores[t_name][0])
                w1 = pair_counts.get(tuple(sorted((name, core_p1))), 0) / math.sqrt(max(1, player_counts[name] * player_counts[core_p1]))
                w2 = pair_counts.get(tuple(sorted((name, core_p2))), 0) / math.sqrt(max(1, player_counts[name] * player_counts[core_p2]))
                score = w1 + w2
                raw_scores[t_name] = score
                total_weight += score
            else:
                raw_scores[t_name] = 0.0

        # Calcul des pourcentages d'affinité
        scores_pct = {}
        for t_name in TARGET_TRIBES:
            scores_pct[t_name] = round((raw_scores[t_name] / total_weight) * 100) if total_weight > 0 else 0

        # Identifier la tribu candidate du jour
        best_tribe = max(scores_pct, key=scores_pct.get) if total_weight > 0 else UNALIGNED_LABEL
        best_pct = scores_pct.get(best_tribe, 0)

        if best_pct < STATUS_AFFILIATE_PCT or games_played < MIN_GAMES_FLOOR:
            best_tribe = UNALIGNED_LABEL

        # --- Gestion de la probation (Inertie temporelle) ---
        if name not in player_probation:
            player_probation[name] = {
                "candidate_tribe": best_tribe,
                "consecutive_days": 1,
                "official_tribe": best_tribe
            }
        else:
            prob = player_probation[name]
            if best_tribe == prob["candidate_tribe"]:
                prob["consecutive_days"] += 1
            else:
                prob["candidate_tribe"] = best_tribe
                prob["consecutive_days"] = 1

            # Si le joueur est stable dans sa tribu candidate depuis assez longtemps, la mutation est validée
            if prob["consecutive_days"] >= PROBATION_DAYS_REQUIRED:
                prob["official_tribe"] = prob["candidate_tribe"]

        final_tribe = player_probation[name]["official_tribe"]
        tribe_summary[final_tribe] = tribe_summary.get(final_tribe, 0) + 1

        # Formattage pour le template HTML
        formatted_scores = {}
        for t_name in TARGET_TRIBES:
            pct_val = scores_pct[t_name]
            status = None
            if t_name == final_tribe:
                is_core = any(name in core for core in active_macro_cores.values())
                if is_core:
                    status = "Core"
                elif pct_val >= STATUS_LOYAL_PCT:
                    status = "Loyalist"
                elif pct_val >= STATUS_AFFILIATE_PCT:
                    status = "Affiliate"
                else:
                    status = "Wavering"

            formatted_scores[t_name] = {
                "pct": pct_val,
                "status": status
            }

        snapshot_players.append({
            "name": name,
            "games": games_played,
            "main_tribe": final_tribe,
            "scores": formatted_scores
        })

    snapshots[d] = {
        "summary": tribe_summary,
        "players": snapshot_players
    }

# ==============================================================================
# 📝 RENDU JINJA2
# ==============================================================================

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.globals["config"] = config_data
template = env.get_template(TEMPLATE_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        snapshots_json=json.dumps(snapshots, ensure_ascii=False), 
        dates_json=json.dumps(sorted_dates, ensure_ascii=False)
    ))

print(f"Analyse double vitesse réussie : Louvain exécuté tous les {LOUVAIN_INTERVAL_DAYS} jours avec {PROBATION_DAYS_REQUIRED} jours de probation.")
