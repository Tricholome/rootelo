import json
from collections import Counter
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# 1. Charger la configuration globale requise par base.html
config_path = Path("data/config/config.json")
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

# 3. Traiter les statistiques des joueurs
player_games = Counter()
for match in matches:
    for player in match.get("players", []):
        if player.get("name"):
            player_games[player["name"]] += 1

players_list = [
    {
        "name": name,
        "games": count,
        "tribe": ""
    }
    for name, count in sorted(player_games.items(), key=lambda x: (-x[1], x[0]))
]

# 4. Initialiser Jinja2 et injecter 'config' globalement
env = Environment(loader=FileSystemLoader("templates"))
env.globals["config"] = config_data

template = env.get_template("frog.html")

# 5. Rendre le template
rendered_html = template.render(
    active_section="frog",
    players=players_list
)

# 6. Écrire le fichier frog.html à la racine
output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(rendered_html)

print(f"Page '{output_path}' générée avec succès pour {len(players_list)} joueurs.")
