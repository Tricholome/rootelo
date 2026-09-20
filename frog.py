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
MIN_GAMES_FLOOR = 3        # Parties minimales pour être classé
STATUS_LOYAL_PCT = 60      # % d'interactions avec un Core pour être Loyaliste
STATUS_AFFILIATE_PCT = 40  # % d'interactions avec un Core pour être Affilié

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
# Fallback si le fichier config n'existe pas (évite le crash)
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
# 🧠 MOTEUR DE GRAVITÉ PAR NOYAUX
# ==============================================================================

snapshots = {}
previous_cores = {} # Garde la mémoire des noyaux pour assurer la continuité des noms

for d in sorted_dates:
    cumulative_matches = [m for m in matches_data if m["date"] <= d]
    
    player_counts = Counter()
    pair_counts = Counter()
    
    # 1. Calcul cumulatif strict
    for m in cumulative_matches:
        players = m["players"]
        for p in players:
            player_counts[p] += 1
        for p1, p2 in combinations(sorted(players), 2):
            pair_counts[(p1, p2)] += 1

    # 2. Identification des Noyaux (Les 3 paires les plus fortes, sans chevauchement)
    # Tri par nb de matchs, puis par ordre alphabétique pour un déterminisme total
    sorted_pairs = sorted(pair_counts.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
    
    top_pairs = []
    used_players = set()
    for pair, count in sorted_pairs:
        if pair[0] not in used_players and pair[1] not in used_players:
            top_pairs.append(pair)
            used_players.update(pair)
            if len(top_pairs) == len(TARGET_TRIBES):
                break

    # 3. Continuité des Noms (Mapping avec les noyaux de la veille)
    current_cores = {}
    assigned_tribes = set()
    available_tribes = TARGET_TRIBES.copy()

    # Passe 1 : Réassigner les tribus existantes s'il y a un joueur en commun
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

    # Passe 2 : Assigner les nouveaux noyaux aux noms restants
    for pair in top_pairs:
        if pair not in current_cores.values():
            new_tribe = available_tribes.pop(0)
            current_cores[new_tribe] = pair
            assigned_tribes.add(new_tribe)

    previous_cores = current_cores # Sauvegarde pour le lendemain

    # 4. Calcul de l'Affinité Orbitale pour chaque joueur
    tribe_summary = {t: 0 for t in TARGET_TRIBES + [UNALIGNED_LABEL]}
    snapshot_players = []

    for name, games_played in sorted(player_counts.items(), key=lambda x: (-x[1], x[0])):
        
        raw_affinities = {}
        total_affinity = 0
        is_core_of = None

        # Calculer le volume d'interactions avec chaque Noyau
        for t_name in TARGET_TRIBES:
            if t_name in current_cores:
                core_p1, core_p2 = current_cores[t_name]
                if name == core_p1 or name == core_p2:
                    is_core_of = t_name
                    raw_affinities[t_name] = 0 # Sera forcé à 100% plus bas
                else:
                    # Somme des matchs joués avec les 2 membres du noyau
                    link1 = pair_counts.get(tuple(sorted((name, core_p1))), 0)
                    link2 = pair_counts.get(tuple(sorted((name, core_p2))), 0)
                    raw = link1 + link2
                    raw_affinities[t_name] = raw
                    total_affinity += raw
            else:
                raw_affinities[t_name] = 0

        # Convertir en pourcentages et définir le statut
        formatted_scores = {}
        max_pct = 0
        best_tribe = UNALIGNED_LABEL

        for t_name in TARGET_TRIBES:
            pct = 0
            status = None

            if is_core_of == t_name:
                pct = 100
                best_tribe = t_name
                max_pct = 100
            elif is_core_of is None and total_affinity > 0:
                pct = round((raw_affinities[t_name] / total_affinity) * 100)
                if pct > max_pct:
                    max_pct = pct
                    best_tribe = t_name

            # Définition des statuts visuels
            if pct > 0:
                if is_core_of == t_name:
                    status = "Core"
                elif pct >= STATUS_LOYAL_PCT:
                    status = "Loyalist"
                elif pct >= STATUS_AFFILIATE_PCT:
                    status = "Affiliate"
                else:
                    status = "Wavering"

            formatted_scores[t_name] = {
                "pct": pct,
                "status": status
            }

        # 5. Validation finale (Vérification du volume minimum et de l'alignement)
        final_tribe = best_tribe
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

print(f"Analyse gravitationnelle réussie : {len(sorted_dates)} dates calculées de manière déterministe.")
