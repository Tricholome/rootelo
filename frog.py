import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES
# ==============================================================================

TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"

# --- Seuils du Modèle de Gravité ---
MIN_MATCHES_TO_START = 50  # Buffer : matchs cumulés requis avant d'afficher les tribus
MIN_GAMES_FLOOR = 3        # Parties minimales pour qu'un joueur puisse être classé
STATUS_LOYAL_PCT = 60      # % d'interactions avec la tribu entière pour être Loyaliste
STATUS_AFFILIATE_PCT = 40  # % d'interactions avec la tribu entière pour être Affilié

# --- Fichiers & Chemins ---
CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 INITIALISATION DES DONNÉES
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
        matches_data.append({
            "date": date_str,
            "players": player_names
        })
        dates_set.add(date_str)

sorted_dates = sorted(list(dates_set))

# ==============================================================================
# 🧠 MOTEUR DE GRAVITÉ (APPROCHE À DOUBLE PASSE)
# ==============================================================================

snapshots = {}
previous_cores = {}

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

    # ⏳ BUFFER DE DÉBUT DE SAISON
    # Tant que la ligue n'a pas atteint le volume minimal, on met tout le monde en attente
    if len(cumulative_matches) < MIN_MATCHES_TO_START:
        tribe_summary = {UNALIGNED_LABEL: len(player_counts)}
        for t in TARGET_TRIBES:
            tribe_summary[t] = 0
            
        snapshot_players = []
        for name, games_played in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
            formatted_scores = {t: {"pct": 0, "status": "Wavering"} for t in TARGET_TRIBES}
            snapshot_players.append({
                "name": name,
                "games": games_played,
                "main_tribe": UNALIGNED_LABEL,
                "scores": formatted_scores
            })
        snapshots[d] = {"summary": tribe_summary, "players": snapshot_players}
        continue

    # ==========================================================================
    # ÉTAPE 1 : IDENTIFICATION DES NOYAUX ET CONTINUITÉ
    # ==========================================================================
    
    sorted_pairs = sorted(pair_counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
    top_pairs = []
    used_players = set()
    
    for pair, count in sorted_pairs:
        if pair[0] not in used_players and pair[1] not in used_players:
            top_pairs.append(pair)
            used_players.update(pair)
            if len(top_pairs) == len(TARGET_TRIBES):
                break

    current_cores = {}
    assigned_tribes = set()
    available_tribes = TARGET_TRIBES.copy()

    # Raccord avec les noms de tribus de la veille (stabilité visuelle)
    for pair in top_pairs:
        best_match = None
        max_overlap = 0
        for t_name, prev_core in previous_cores.items():
            if t_name in available_tribes:
                overlap = len(set(pair).intersection(set(prev_core)))
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_match = t_name
        
        if best_match:
            current_cores[best_match] = pair
            assigned_tribes.add(best_match)
            available_tribes.remove(best_match)

    for pair in top_pairs:
        if pair not in current_cores.values():
            new_tribe = available_tribes.pop(0)
            current_cores[new_tribe] = pair
            assigned_tribes.add(new_tribe)

    previous_cores = current_cores 

    # ==========================================================================
    # ÉTAPE 2 : PASSE 1 - ASSIGNATION PROVISOIRE (GRAVITÉ DES NOYAUX)
    # ==========================================================================
    
    provisional_assignments = {}
    for name in player_counts.keys():
        best_tribe = UNALIGNED_LABEL
        max_core_links = 0
        
        for t_name, (core_p1, core_p2) in current_cores.items():
            if name == core_p1 or name == core_p2:
                best_tribe = t_name
                break
                
            link1 = pair_counts.get(tuple(sorted((name, core_p1))), 0)
            link2 = pair_counts.get(tuple(sorted((name, core_p2))), 0)
            total_core_links = link1 + link2
            
            if total_core_links > max_core_links:
                max_core_links = total_core_links
                best_tribe = t_name
                
        provisional_assignments[name] = best_tribe

    # ==========================================================================
    # ÉTAPE 3 : PASSE 2 - CALCUL FINAL ET RENDU (GRAVITÉ DE LA TRIBU ENTIÈRE)
    # ==========================================================================
    
    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}
    snapshot_players = []

    for name, games_played in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        
        raw_affinities = {t: 0 for t in TARGET_TRIBES}
        total_interactions = 0
        is_core_of = next((t for t, core in current_cores.items() if name in core), None)

        # Addition de l'historique complet du joueur
        for p2 in player_counts.keys():
            if name != p2:
                link = pair_counts.get(tuple(sorted((name, p2))), 0)
                if link > 0:
                    total_interactions += link
                    p2_tribe = provisional_assignments.get(p2, UNALIGNED_LABEL)
                    if p2_tribe in TARGET_TRIBES:
                        raw_affinities[p2_tribe] += link

        formatted_scores = {}
        max_pct = 0
        best_tribe = UNALIGNED_LABEL

        for t_name in TARGET_TRIBES:
            pct = 0
            status = "Wavering"

            if is_core_of == t_name:
                pct = 100
                best_tribe = t_name
                max_pct = 100
                status = "Core"
            elif is_core_of is None and total_interactions > 0:
                pct = round((raw_affinities[t_name] / total_interactions) * 100)
                if pct > max_pct:
                    max_pct = pct
                    best_tribe = t_name

                if pct > 0:
                    if pct >= STATUS_LOYAL_PCT:
                        status = "Loyalist"
                    elif pct >= STATUS_AFFILIATE_PCT:
                        status = "Affiliate"

            formatted_scores[t_name] = {
                "pct": pct,
                "status": status
            }

        final_tribe = best_tribe
        # Le joueur bascule hors réseau s'il n'atteint pas l'affinité minimale ou le volume minimal
        if games_played < MIN_GAMES_FLOOR or max_pct < STATUS_AFFILIATE_PCT:
            final_tribe = UNALIGNED_LABEL

        tribe_summary[final_tribe] = tribe_summary.get(final_tribe, 0) + 1

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
# 📝 RENDU HTML (JINJA2)
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

print(f"Analyse gravitationnelle réussie : {len(sorted_dates)} dates calculées (Buffer de {MIN_MATCHES_TO_START} matchs actif).")
