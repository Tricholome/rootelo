import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# --- CONFIGURATION ---
TARGET_TRIBES = ["Tribe A", "Tribe B", "Tribe C"]
UNALIGNED_LABEL = "-"

ALPHA_SMOOTHING = 0.15     # Poids du jour présent (0.15 = 15% jour, 85% mémoire). Empêche les sauts.
HYSTERESIS_MARGIN = 15     # Il faut 15% d'écart lissé pour changer de tribu principale.
MIN_GAMES_FLOOR = 3        # Minimum de parties disputées pour avoir une tribu attribuée.

STATUS_LOYAL_PCT = 55
STATUS_AFFILIATE_PCT = 35

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# --- CHARGEMENT ---
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

# --- ÉTAT PERMANENT DU RESEAU ---
snapshots = {}
player_smoothed_scores = {}  # Stocke l'EMA des scores {player: {Tribe A: pct, Tribe B: pct, ...}}
player_assigned_tribe = {}   # Stocke la tribu attribuée au joueur
stable_cores = {}            # Anciens noyaux pour garder la stabilité des noms

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

    # 1. IDENTIFICATION DES PÔLES PAR DENSITÉ RELATIVE (COSINUS)
    weighted_pairs = []
    for (p1, p2), joint_count in pair_counts.items():
        if joint_count >= 2:
            # Similarité Cosinus : mesure l'exclusivité de la relation
            weight = joint_count / math.sqrt(player_counts[p1] * player_counts[p2])
            weighted_pairs.append(((p1, p2), weight))

    sorted_pairs = sorted(weighted_pairs, key=lambda x: -x[1])
    
    top_pairs = []
    used_players = set()
    for pair, weight in sorted_pairs:
        if pair[0] not in used_players and pair[1] not in used_players:
            top_pairs.append(pair)
            used_players.update(pair)
            if len(top_pairs) == len(TARGET_TRIBES):
                break

    # Alignement continu des nom de tribus
    current_cores = {}
    available_tribes = TARGET_TRIBES.copy()
    
    for pair in top_pairs:
        best_match = None
        max_overlap = 0
        for t_name, prev_core in stable_cores.items():
            if t_name in available_tribes:
                overlap = len(set(pair).intersection(set(prev_core)))
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_match = t_name
        if best_match:
            current_cores[best_match] = pair
            available_tribes.remove(best_match)

    for pair in top_pairs:
        if pair not in current_cores.values() and available_tribes:
            new_t = available_tribes.pop(0)
            current_cores[new_t] = pair

    stable_cores = current_cores

    # 2. CALCUL DU SCORE BRUT DU JOUR
    snapshot_players = []
    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}

    for name, games_played in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        
        # Calcul de l'affinité brute du jour envers chaque pôle
        raw_scores = {}
        total_rel_weight = 0.0

        for t_name in TARGET_TRIBES:
            if t_name in current_cores:
                core_p1, core_p2 = current_cores[t_name]
                w1 = pair_counts.get(tuple(sorted((name, core_p1))), 0) / math.sqrt(max(1, player_counts[name] * player_counts[core_p1]))
                w2 = pair_counts.get(tuple(sorted((name, core_p2))), 0) / math.sqrt(max(1, player_counts[name] * player_counts[core_p2]))
                score = w1 + w2
                raw_scores[t_name] = score
                total_rel_weight += score
            else:
                raw_scores[t_name] = 0.0

        # Normalisation en pourcentages bruts
        raw_pcts = {}
        for t_name in TARGET_TRIBES:
            if total_rel_weight > 0:
                raw_pcts[t_name] = (raw_scores[t_name] / total_rel_weight) * 100
            else:
                raw_pcts[t_name] = 0.0

        # 3. APPLICATION DU LISSAGE TEMPOREL (EMA)
        if name not in player_smoothed_scores:
            # Premier jour du joueur : score brut direct
            player_smoothed_scores[name] = raw_pcts
        else:
            # Jour suivant : lissage exponentiel
            prev_scores = player_smoothed_scores[name]
            smoothed = {}
            for t_name in TARGET_TRIBES:
                smoothed[t_name] = (1 - ALPHA_SMOOTHING) * prev_scores.get(t_name, 0.0) + ALPHA_SMOOTHING * raw_pcts[t_name]
            player_smoothed_scores[name] = smoothed

        current_smoothed = player_smoothed_scores[name]

        # 4. DETERMINATION DE LA TRIBU ET HYSTERESIS
        best_tribe = max(current_smoothed, key=current_smoothed.get)
        best_val = current_smoothed[best_tribe]
        
        current_assigned = player_assigned_tribe.get(name, UNALIGNED_LABEL)

        if current_assigned in TARGET_TRIBES and best_tribe != current_assigned:
            current_val = current_smoothed.get(current_assigned, 0.0)
            # Règle de bascule : la nouvelle tribu doit dépasser l'ancienne de la marge d'hystérésis
            if best_val > current_val + HYSTERESIS_MARGIN:
                final_tribe = best_tribe
            else:
                final_tribe = current_assigned
        else:
            final_tribe = best_tribe if best_val >= STATUS_AFFILIATE_PCT else UNALIGNED_LABEL

        # Filtre sur le nombre de matchs minimum
        if games_played < MIN_GAMES_FLOOR:
            final_tribe = UNALIGNED_LABEL

        player_assigned_tribe[name] = final_tribe
        tribe_summary[final_tribe] = tribe_summary.get(final_tribe, 0) + 1

        # Formattage pour Jinja2
        formatted_scores = {}
        for t_name in TARGET_TRIBES:
            pct_val = round(current_smoothed[t_name])
            status = None
            if t_name == final_tribe:
                if pct_val >= STATUS_LOYAL_PCT:
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

# --- RENDU ---
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
env.globals["config"] = config_data
template = env.get_template(TEMPLATE_FILE)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(template.render(
        active_section="frog",
        snapshots_json=json.dumps(snapshots, ensure_ascii=False), 
        dates_json=json.dumps(sorted_dates, ensure_ascii=False)
    ))

print("Traitement terminé : affinités lissées sans sauts de tribu.")
