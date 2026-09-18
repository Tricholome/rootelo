import json
from collections import Counter
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# 1. Chargement des données brutes
json_path = Path("data/rdl/archives/lh02/matches.json")
with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 2. Extraction & préparation des objets joueurs
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
    for name, count in player_games.items()
]

# 3. Rendu Jinja2 avec templates/frog.html
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("frog.html")

rendered_html = template.render(
    players=players_list
)

with open("frog.html", "w", encoding="utf-8") as f:
    f.write(rendered_html)
