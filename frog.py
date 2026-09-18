import json
from collections import Counter
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# 1. Sélection et chargement du fichier JSON de la saison
json_path = Path("data/rdl/archives/lh02/matches.json")

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 2. Agrégation pure des données
player_games = Counter()
for match in matches:
    for p in match.get("players", []):
        if p.get("name"):
            player_games[p["name"]] += 1

# Structuration des données sous forme de liste de dictionnaires
players_data = [
    {
        "name": name,
        "games": count,
        "tribe": ""  # Champ disponible pour la tribu
    }
    for name, count in sorted(player_games.items(), key=lambda x: (-x[1], x[0]))
]

# 3. Rendu du template Jinja2
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("frogs.html")

output_html = template.render(
    page_heading="Welcome, frogs!",
    players=players_data
)

# 4. Écriture du fichier HTML final
output_path = Path("frogs.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_html)

print(f"Page '{output_path}' générée avec succès pour {len(players_data)} joueurs.")
