import json
from collections import Counter
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# 1. Charger la configuration globale requise par base.html
config_path = Path("data/config/config.json")
if not config_path.exists():
    config_path = Path("data/config.json")

with open(config_path, "r", encoding="utf-8") as f:
    config_data = json.load(f)

# 2. Charger les matchs depuis les archives
json_path = Path("data/rdl/archives/lh02/matches.json")
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 3. Traiter les matchs et extraire la date au format YYYY-MM-DD
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

# 4. Statistiques cumulées globales (fallback pour le rendu HTML initial)
player_games = Counter()
for m in matches_data:
    for p in m["players"]:
        player_games[p] += 1

players_list = [
    {
        "name": name,
        "games": count,
        "tribe": ""
    }
    for name, count in sorted(player_games.items(), key=lambda x: (-x[1], x[0]))
]

# 5. Initialiser Jinja2 et injecter 'config'
env = Environment(loader=FileSystemLoader("templates"))
env.globals["config"] = config_data

template = env.get_template("frog.html")

# 6. Rendre le template en injectant les données brutes sous forme JSON
rendered_html = template.render(
    active_section="frog",
    players=players_list,
    matches_json=json.dumps(matches_data, ensure_ascii=False),
    dates_json=json.dumps(sorted_dates, ensure_ascii=False)
)

# 7. Écrire le fichier frog.html à la racine
output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(rendered_html)

print(f"Page '{output_path}' générée avec succès ({len(players_list)} joueurs, {len(sorted_dates)} dates).")
