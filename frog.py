import json
import math
import statistics
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

# 3. Paramètres du graphe et des tribus
TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
MIN_TRIBE_SIZE = 5
MIN_ACTIVE_MEMBERS = 3

def get_community_core(community_nodes, G, top_n=3):
    """Identifie les 'piliers' d'une tribu grâce à leur centralité de degré au sein de la communauté"""
    subgraph = G.subgraph(community_nodes)
    centrality = nx.degree_centrality(subgraph)
    return sorted(centrality.keys(), key=lambda x: centrality[x], reverse=True)[:top_n]

snapshots = {}
previous_cores = {}
daily_tribes = {}
prev_assignments = {}

# 4. Boucle temporelle : Calcul total jour par jour
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

    # --- ÉTAPE A : Construction du graphe avec Similarité Cosinus ---
    G = nx.Graph()
    G.add_nodes_from(active_players)

    for (p1, p2), joint_count in pair_counts.items():
        if p1 in active_players and p2 in active_players and joint_count >= min_joint_matches:
            # Poids mathématique propre : Similarité Cosinus
            weight = joint_count / math.sqrt(player_counts[p1] * player_counts[p2])
            if weight >= 0.12:
                G.add_edge(p1, p2, weight=weight)

    # --- ÉTAPE B : Détection Louvain et Continuité par Noyau (Core Anchoring) ---
    raw_communities = []
    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42))
        except Exception:
            pass

    valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]
    
    current_assignments = {}
    current_cores = {}
    
    if not previous_cores:
        # Jour 1 : Assignation initiale brute
        for idx, comm in enumerate(valid_communities):
            if idx < 3:
                tribe_name = TARGET_TRIBES[idx]
                current_cores[tribe_name] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = tribe_name
    else:
        # Jours suivants : Suivi par l'inertie des noyaux
        assigned_tribes = set()
        
        # 1. Assigner les communautés existantes
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
                    
        # 2. Gérer l'apparition de nouvelles communautés (si une tribu a disparu et laissé un "slot" vide)
        unassigned_comms = [c for c in valid_communities if not any(p in current_assignments for p in c)]
        for comm in unassigned_comms:
            available_tribes = [t for t in TARGET_TRIBES if t not in assigned_tribes]
            if available_tribes:
                new_tribe = available_tribes[0]
                assigned_tribes.add(new_tribe)
                current_cores[new_tribe] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = new_tribe

    # --- ÉTAPE C : Rattrapage des inclassés et filtrage volume ---
    for p in player_counts:
        if p not in current_assignments:
            prev_tribe = prev_assignments.get(p, "Inclassé")
            if prev_tribe in current_cores:  # Si sa tribu d'hier existe toujours, il y reste par inertie
                current_assignments[p] = prev_tribe
            else:
                current_assignments[p] = "Inclassé"

    active_tribe_counts = Counter(current_assignments.values())
    for p, tribe in list(current_assignments.items()):
        if tribe in TARGET_TRIBES and active_tribe_counts[tribe] < MIN_ACTIVE_MEMBERS:
            current_assignments[p] = "Inclassé"

    # Sauvegarde de l'état purement algorithmique pour ce jour
    daily_tribes[d] = current_assignments
    previous_cores = current_cores
    prev_assignments = current_assignments

    # --- ÉTAPE D : Arbitrage Métier et Préparation Frontend ("Dumb Frontend") ---
    # Calcul de la loyauté cumulative à date
    player_loyalty_sum = {p: Counter() for p in player_counts}
    for m in cumulative_matches:
        players = m["players"]
        n_players = len(players)
        if n_players <= 1: continue
        for p in players:
            for other in players:
                if other != p:
                    other_tribe = current_assignments.get(other, "Inclassé")
                    if other_tribe in TARGET_TRIBES:
                        player_loyalty_sum[p][other_tribe] += 1 / (n_players - 1)

    # Calcul de la médiane dynamique
    all_counts = list(player_counts.values())
    global_median = statistics.median(all_counts) if all_counts else 0
    min_games_tribe = max(3, math.ceil(global_median * 0.30))

    tribe_summary = {t: 0 for t in TARGET_TRIBES + ["Inclassé"]}
    snapshot_players = []

    for name, count in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        louvain_tribe = current_assignments.get(name, "Inclassé")
        
        # Calcul des pourcentages
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

        # Arbitrage métier final (remplace ton ancien code JS)
        if count < min_games_tribe:
            final_tribe = "Inclassé"
        else:
            final_tribe = louvain_tribe
            if louvain_tribe == "Inclassé":
                if max_pct >= 30:
                    final_tribe = max_tribe
            else:
                louvain_pct = scores.get(louvain_tribe, 0)
                if max_tribe and max_tribe != louvain_tribe and max_pct > louvain_pct:
                    if max_pct >= 30:
                        final_tribe = max_tribe
                    else:
                        final_tribe = "Inclassé"

        tribe_summary[final_tribe] = tribe_summary.get(final_tribe, 0) + 1

        # Formatage des statuts pour l'affichage
        formatted_scores = {}
        for t in TARGET_TRIBES:
            pct = scores[t]
            status = None
            if t == final_tribe:
                if pct >= 60: status = "Noyau"
                elif pct >= 30: status = "Membre"
                else: status = "Fragile"
            
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

    # Enregistrement du cliché (snapshot) du jour
    snapshots[d] = {
        "summary": tribe_summary,
        "players": snapshot_players
    }

# 5. Génération HTML
env = Environment(loader=FileSystemLoader("templates"))
env.globals["config"] = config_data
template = env.get_template("frog.html")

output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        # Le JS n'a plus besoin de calculer quoi que ce soit, on lui passe tout prémâché :
        snapshots_json=json.dumps(snapshots, ensure_ascii=False), 
        dates_json=json.dumps(sorted_dates, ensure_ascii=False)
    ))

print(f"Analyse réussie : {len(sorted_dates)} dates calculées (Similarité Cosinus + Core Anchoring + Dumb Frontend).")
