import json
from collections import Counter
from pathlib import Path

# 1. Chemin du fichier matches.json
json_path = Path("rootelo/data/rdl/archives/lh03/matches.json")

# 2. Lecture du fichier JSON
with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

# 3. Comptage du nombre de parties jouées par chaque joueur
player_games = Counter()

for match in matches:
    for player in match.get("players", []):
        player_name = player.get("name")
        if player_name:
            player_games[player_name] += 1

# Tri des joueurs du plus grand au plus petit nombre de parties jouées
sorted_players = sorted(player_games.items(), key=lambda x: (-x[1], x[0]))

# 4. Construction de la table HTML
html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Frog Leaderboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
        }
        table {
            border-collapse: collapse;
            width: 60%;
            margin: 0 auto;
        }
        th, td {
            border: 1px solid #ccc;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #f4f4f4;
        }
        tr:nth-child(even) {
            background-color: #fafafa;
        }
    </style>
</head>
<body>
    <h2 style="text-align: center;">Statistiques des Joueurs</h2>
    <table>
        <thead>
            <tr>
                <th>Player</th>
                <th>Games</th>
                <th>Tribe</th>
            </tr>
        </thead>
        <tbody>
"""

for player, games in sorted_players:
    html_content += f"""            <tr>
                <td>{player}</td>
                <td>{games}</td>
                <td></td>
            </tr>\n"""

html_content += """        </tbody>
    </table>
</body>
</html>
"""

# 5. Écriture du fichier frog.html
output_path = Path("frog.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Fichier '{output_path}' généré avec succès pour {len(sorted_players)} joueurs !")
