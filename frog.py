import json
import os
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

# Constantes de navigation reprises de main.py
NAV_ITEMS = [
    {'id': 'index', 'url': 'index.html', 'label': 'Leaderboard'},
    {'id': 'matches', 'url': 'matches.html', 'label': 'Top Tables'},
    {'id': 'trends', 'url': 'trends.html', 'label': "Player's Journey"},
    {'id': 'about', 'url': 'about.html', 'label': 'Codex'}
]


def load_json(filepath, default=None):
    """Charge un fichier JSON de manière sécurisée (identique à main.py)."""
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Erreur lors de la lecture de {filepath}: {e}")
    return default


def main():
    # 1. Chargement des configurations globales (comme dans main.py)
    config = load_json(os.path.join("data", "config", "config.json"))

    # 2. Configuration de l'environnement Jinja2
    env = Environment(loader=FileSystemLoader(['templates', '.']))
    env.globals['config'] = config

    # 3. Chargement du template (templates/frog.html)
    template = env.get_template("frog.html")

    # 4. Context/Variables transmises au template HTML
    context = {
        "nav_items": NAV_ITEMS,
        "page_id": "frog",
        "section_id": "frog",
        "title": "Frog Test Zone 🐸",
        "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "path_prefix": "",
        "is_static": True
    }

    # 5. Rendu et enregistrement du fichier de sortie frog.html
    output_path = "frog.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(template.render(**context))

    print(f"✅ Page générée avec succès : {output_path}")


if __name__ == "__main__":
    main()
