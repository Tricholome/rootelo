import json
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION
# ==============================================================================

TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"

DECAY_RATE = 0.95          # Chaque jour sans jouer, la force du lien conserve 95% de sa valeur
NEW_MATCH_WEIGHT = 1.0     # Poids ajouté pour chaque nouvelle partie jouée ensemble

MIN_GAMES_FLOOR = 3
STATUS_LOYAL_PCT = 55
STATUS_AFFILIATE_PCT = 35

# ==============================================================================
# 🚀 INITIALISATION
# ==============================================================================

matches = json.load(open("data/rdl/archives/lh02/matches.json", "r", encoding="utf-8"))

matches_by_date = {}
for m in matches:
    date_str = str(m.get("Date") or m.get("date") or "")[:10]
    players = [p.get("name") for p in m.get("players", []) if p.get("name")]
    if date_str and players:
        matches_by_date.setdefault(date_str, []).append(players)

sorted_dates = sorted(matches_by_date.keys())

# ==============================================================================
# 🧠 L'ALGORITHME ORGANIQUE (LOUVAIN SUR GRAPHE LISSÉ)
# ==============================================================================

snapshots = {}
edge_weights = Counter()    # Mémoire persistante des arêtes
player_games = Counter()    # Compteur total des parties

# Pour stabiliser les noms des tribus d'un jour à l'autre
previous_communities = {}

for d in sorted_dates:
    # 1. VIEILLISSEMENT DU GRAPHE (Déclin exponentiel)
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE
        
    # 2. INJECTION DES NOUVEAUX MATCHS DU JOUR
    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    # Nettoyage des liens fantômes pour optimiser Louvain
    active_edges = {k: v for k, v in edge_weights.items() if v > 0.1}

    # 3. CONSTRUCTION DU GRAPHE ET LOUVAIN
    G = nx.Graph()
    for (p1, p2), weight in active_edges.items():
        G.add_edge(p1, p2, weight=weight)

    current_communities = {}
    if G.number_of_nodes() > 0:
        # Louvain trouve naturellement la meilleure structure
        raw_comms = sorted(nx.community.louvain_communities(G, weight="weight"), key=len, reverse=True)
        
        # Mapping des noms pour la stabilité visuelle
        available_names = TARGET_TRIBES.copy()
        for idx, comm in enumerate(raw_comms[:len(TARGET_TRIBES)]):
            best_name = None
            max_intersect = 0
            for old_name, old_comm in previous_communities.items():
                if old_name in available_names:
                    intersect = len(comm.intersection(old_comm))
                    if intersect > max_intersect:
                        max_intersect = intersect
                        best_name = old_name
            
            if not best_name and available_names:
                best_name = available_names[0]
                
            if best_name:
                available_names.remove(best_name)
                current_communities[best_name] = comm

    previous_communities = current_communities

    # 4. EXTRACTION DES POURCENTAGES D'AFFINITÉ INDIVIDUELS
    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}
    snapshot_players = []

    for name, games_played in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        if name not in G:
            continue

        # Calculer le poids total des liens du joueur vers chaque communauté
        comm_affinities = {t: 0.0 for t in TARGET_TRIBES}
        total_affinity = 0.0

        for neighbor in G.neighbors(name):
            weight = G[name][neighbor]['weight']
            total_affinity += weight
            
            for t_name, comm_players in current_communities.items():
                if neighbor in comm_players:
                    comm_affinities[t_name] += weight

        # Conversion en pourcentages
        scores_pct = {}
        for t_name in TARGET_TRIBES:
            scores_pct[t_name] = round((comm_affinities[t_name] / total_affinity) * 100) if total_affinity > 0 else 0

        # Assignation finale
        best_tribe = max(scores_pct, key=scores_pct.get) if total_affinity > 0 else UNALIGNED_LABEL
        if scores_pct.get(best_tribe, 0) < STATUS_AFFILIATE_PCT or games_played < MIN_GAMES_FLOOR:
            best_tribe = UNALIGNED_LABEL

        tribe_summary[best_tribe] = tribe_summary.get(best_tribe, 0) + 1

        # Formatage Jinja2
        formatted_scores = {}
        for t_name in TARGET_TRIBES:
            pct = scores_pct[t_name]
            status = "Wavering"
            if t_name == best_tribe:
                if pct >= STATUS_LOYAL_PCT: status = "Loyalist"
                elif pct >= STATUS_AFFILIATE_PCT: status = "Affiliate"
            formatted_scores[t_name] = {"pct": pct, "status": status}

        snapshot_players.append({
            "name": name,
            "games": games_played,
            "main_tribe": best_tribe,
            "scores": formatted_scores
        })

    snapshots[d] = {"summary": tribe_summary, "players": snapshot_players}

# Export et Rendu Jinja2 (inchangé)
