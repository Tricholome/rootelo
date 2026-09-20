import json
import math
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMETERS
# ==============================================================================

# --- 1. Tribe Names & Boundaries ---
TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"
MIN_TRIBE_SIZE = 5        
MIN_ACTIVE_MEMBERS = 3    
CORE_TOP_N = 3            

# --- 2. Graph & Connection Filtering ---
MIN_PLAYER_GAMES_GRAPH = 3  
MIN_JOINT_BASE = 2          
MIN_JOINT_SLOPE = 3         
MIN_COSINE_WEIGHT = 0.18    
LOUVAIN_SEED = 42           
LOUVAIN_RESOLUTION = 1.5    
HYSTERESIS_MARGIN = 10
WAVERING_MARGIN = 5

# --- 3. Volume Filtering (Median Organic Volume) ---
TRIBE_MEDIAN_RATIO = 0.4   
MIN_GAMES_FLOOR = 3        

# --- 4. Status Tiers & Display Thresholds ---
STATUS_CORE_PCT = 65       
STATUS_LOYAL_PCT = 45      
DISPLAY_MIN_PCT = 10       

# --- 5. Files & Paths ---
CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 PIPELINE EXECUTION
# ==============================================================================

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
    subgraph = G.subgraph(community_nodes)
    centrality = nx.degree_centrality(subgraph)
    return sorted(centrality.keys(), key=lambda x: centrality[x], reverse=True)[:top_n]

snapshots = {}
previous_cores = {}
daily_tribes = {}
prev_assignments = {}

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

    G = nx.Graph()
    G.add_nodes_from(active_players)

    for (p1, p2), joint_count in pair_counts.items():
        if p1 in active_players and p2 in active_players and joint_count >= min_joint_matches:
            weight = joint_count / math.sqrt(player_counts[p1] * player_counts[p2])
            if weight >= MIN_COSINE_WEIGHT:
                G.add_edge(p1, p2, weight=weight)

    raw_communities = []
    if G.number_of_nodes() > 0:
        try:
            raw_communities = list(nx.community.louvain_communities(
                G, weight="weight", resolution=LOUVAIN_RESOLUTION, seed=LOUVAIN_SEED
            ))
        except Exception:
            pass

    valid_communities = [c for c in raw_communities if len(c) >= MIN_TRIBE_SIZE]
    
    current_assignments = {}
    current_cores = {}
    
    if not previous_cores:
        for idx, comm in enumerate(valid_communities):
            if idx < len(TARGET_TRIBES):
                tribe_name = TARGET_TRIBES[idx]
                current_cores[tribe_name] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = tribe_name
    else:
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
                    
        unassigned_comms = [c for c in valid_communities if not any(p in current_assignments for p in c)]
        for comm in unassigned_comms:
            available_tribes = [t for t in TARGET_TRIBES if t not in assigned_tribes]
            if available_tribes:
                new_tribe = available_tribes[0]
                assigned_tribes.add(new_tribe)
                current_cores[new_tribe] = get_community_core(comm, G)
                for p in comm:
                    current_assignments[p] = new_tribe

    for p in player_counts:
        if p not in current_assignments:
            prev_tribe = prev_assignments.get(p, UNALIGNED_LABEL)
            if prev_tribe in current_cores:
                current_assignments[p] = prev_tribe
            else:
                current_assignments[p] = UNALIGNED_LABEL

    active_tribe_counts = Counter(current_assignments.values())
    for p, tribe in list(current_assignments.items()):
        if tribe in TARGET_TRIBES and active_tribe_counts[tribe] < MIN_ACTIVE_MEMBERS:
            current_assignments[p] = UNALIGNED_LABEL

    daily_tribes[d] = current_assignments
    previous_cores = current_cores
    prev_assignments = current_assignments

    player_global_affinity = {p: Counter() for p in player_counts}

    for (p1, p2), joint_count in pair_counts.items():
        if p1 in active_players and p2 in active_players:
            weight = joint_count / math.sqrt(player_counts[p1] * player_counts[p2])

            t1 = current_assignments.get(p1, UNALIGNED_LABEL)
            t2 = current_assignments.get(p2, UNALIGNED_LABEL)
            
            # Enregistre TOUTES les interactions (y compris inclassés)
            player_global_affinity[p1][t2] += weight
            player_global_affinity[p2][t1] += weight

    louvain_tribe_sizes = Counter(current_assignments.values())

    tribe_thresholds = {}
    for t in TARGET_TRIBES:
        tribe_members = [p for p, tribe in current_assignments.items() if tribe == t]
        if tribe_members:
            tribe_volumes = [player_counts[p] for p in tribe_members]
            tribe_median = statistics.median(tribe_volumes)
            tribe_thresholds[t] = max(MIN_GAMES_FLOOR, math.ceil(tribe_median * TRIBE_MEDIAN_RATIO))
        else:
            tribe_thresholds[t] = MIN_GAMES_FLOOR

    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}
    snapshot_players = []

    all_categories = TARGET_TRIBES + [UNALIGNED_LABEL]

    for name, count in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        normalized_affinities = {}
        total_normalized = 0.0

        # Normalisation sur TOUTES les catégories (tribus + inclassés)
        for cat in all_categories:
            cat_size = max(1, louvain_tribe_sizes.get(cat, 1))
            norm_aff = player_global_affinity[name][cat] / math.sqrt(cat_size)
            normalized_affinities[cat] = norm_aff
            total_normalized += norm_aff
            
        scores = {}
        for t in TARGET_TRIBES:
            if total_normalized > 0:
                scores[t] = round((normalized_affinities[t] / total_normalized) * 100)
            else:
                scores[t] = 0
                
        sorted_scores = sorted(scores.values(), reverse=True)
        top_margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 100

        raw_max_tribe = max(scores, key=scores.get) if total_normalized > 0 else UNALIGNED_LABEL
        raw_max_pct = scores.get(raw_max_tribe, 0)

        max_tribe = raw_max_tribe
        max_pct = raw_max_pct

        prev_tribe = prev_assignments.get(name, UNALIGNED_LABEL)
        if prev_tribe in TARGET_TRIBES and raw_max_tribe != prev_tribe:
            prev_score = scores.get(prev_tribe, 0)
            if raw_max_pct - prev_score < HYSTERESIS_MARGIN:
                max_tribe = prev_tribe
                max_pct = prev_score

        is_core = any(name in cores for cores in current_cores.values())
        required_games = tribe_thresholds.get(max_tribe, MIN_GAMES_FLOOR)

        if count < required_games:
            final_tribe = UNALIGNED_LABEL
        elif is_core:
            final_tribe = current_assignments.get(name, UNALIGNED_LABEL)
        elif max_pct >= DISPLAY_MIN_PCT: 
            final_tribe = max_tribe 
        else:
            final_tribe = UNALIGNED_LABEL

        tribe_summary[final_tribe] = tribe_summary.get(final_tribe, 0) + 1

        formatted_scores = {}
        for t in TARGET_TRIBES:
            pct = scores[t]
            status = None
            if t == final_tribe:
                if top_margin <= WAVERING_MARGIN:
                    status = "Wavering"
                elif is_core or pct >= STATUS_CORE_PCT:
                    status = "Core"
                elif pct >= STATUS_LOYAL_PCT:
                    status = "Loyalist"
                else:
                    status = "Affiliate"

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
       
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.globals["config"] = config_data
template = env.get_template(TEMPLATE_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        snapshots_json=json.dumps(snapshots, ensure_ascii=False), 
        dates_json=json.dumps(sorted_dates, ensure_ascii=False)
    ))

print(f"Analysis successful: {len(sorted_dates)} dates calculated (Wavering margin tightened to 10%).")
