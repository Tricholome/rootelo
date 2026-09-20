import json
import os
from collections import Counter
from itertools import combinations
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION & HYPERPARAMÈTRES
# ==============================================================================

MAX_DAILY_TRANSFERS = 3    # Le fameux goulot d'étranglement (2-3 par jour max)
MAX_TRIBES = 3             # Limite stricte à 3 tribus
MIN_TRIBE_SIZE_LOUVAIN = 4 # Taille mini pour qu'un cluster soit considéré par Louvain
MIN_TRIBE_SURVIVAL = 2     # Si une tribu tombe sous 2 joueurs, elle est dissoute
MIN_GAMES_FLOOR = 3        # Matchs minimum pour avoir le droit de rejoindre une tribu

DECAY_RATE = 0.95
NEW_MATCH_WEIGHT = 1.0
UNALIGNED_LABEL = "-"
TRIBE_NAMES_POOL = [f"Tribe {chr(65+i)}" for i in range(26)] # Tribe A, Tribe B, etc.

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh02/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")

# ==============================================================================
# 🚀 CHARGEMENT DES DONNÉES
# ==============================================================================

# Si le script ne trouve pas le json, il cherche dans les sous-dossiers
json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    if archives:
        json_path = archives[0]
    else:
        # Fallback pour test local sans la structure de dossiers
        json_path = Path("matches.json")

if not json_path.exists():
    print(f"❌ Erreur : Fichier de matchs introuvable à {json_path}")
    exit(1)

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

matches_by_date = {}
for m in matches:
    date_str = str(m.get("Date") or m.get("date") or m.get("date_closed") or "")[:10]
    players = [p.get("name") for p in m.get("players", []) if p.get("name")]
    if date_str and players:
        matches_by_date.setdefault(date_str, []).append(players)

sorted_dates = sorted(matches_by_date.keys())

# ==============================================================================
# 🧠 MOTEUR D'ÉTAT : LOUVAIN BRIDÉ
# ==============================================================================

edge_weights = Counter()
player_games = Counter()

current_roster = {}  # L'état OFFICIEL des tribus { "Adrien": "Tribe A" }
active_tribes = []   # Liste des tribus vivantes ["Tribe A", "Tribe B"]
next_name_idx = 0    # Pour piocher A, puis B, puis C...
snapshots = {}

for d in sorted_dates:
    # 1. Atténuation & Ajout des nouveaux matchs
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE
        
    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
            if p not in current_roster:
                current_roster[p] = UNALIGNED_LABEL
        for p1, p2 in combinations(sorted(players), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    G = nx.Graph()
    for (p1, p2), w in edge_weights.items():
        if w >= 0.1:
            G.add_edge(p1, p2, weight=w)

    # 2. La Boussole : Calcul de l'idéal théorique avec Louvain
    ideal_assignments = {p: UNALIGNED_LABEL for p in G.nodes()}
    
    if G.number_of_nodes() > 0:
        try:
            raw_comms = sorted(nx.community.louvain_communities(G, weight="weight", seed=42), key=len, reverse=True)
        except Exception:
            raw_comms = []

        valid_comms = [c for c in raw_comms if len(c) >= MIN_TRIBE_SIZE_LOUVAIN][:MAX_TRIBES]
        
        used_ideal_names = set()
        for comm in valid_comms:
            best_name = None
            max_intersect = 0
            
            # Tente de lier ce cluster à une tribu existante
            for t_name in active_tribes:
                if t_name not in used_ideal_names:
                    current_members = {p for p, t in current_roster.items() if t == t_name}
                    intersect = len(comm.intersection(current_members))
                    if intersect > max_intersect:
                        max_intersect = intersect
                        best_name = t_name
            
            # Si le cluster est nouveau, on le baptise
            if not best_name and next_name_idx < len(TRIBE_NAMES_POOL):
                best_name = TRIBE_NAMES_POOL[next_name_idx]
                next_name_idx += 1
                
            if best_name:
                used_ideal_names.add(best_name)
                for p in comm:
                    ideal_assignments[p] = best_name

    # 3. Le Goulot d'étranglement (Quota de transfert)
    pending_migrations = []
    
    for p in G.nodes():
        curr_t = current_roster.get(p, UNALIGNED_LABEL)
        ideal_t = ideal_assignments.get(p, UNALIGNED_LABEL)
        
        if curr_t != ideal_t and player_games[p] >= MIN_GAMES_FLOOR:
            # Force d'attraction vers la NOUVELLE tribu théorique (Louvain)
            w_ideal = sum(G[p][n]["weight"] for n in G.neighbors(p) if ideal_assignments.get(n) == ideal_t)
            # Force d'ancrage dans l'ANCIENNE tribu (Roster actuel)
            w_curr = sum(G[p][n]["weight"] for n in G.neighbors(p) if current_roster.get(n) == curr_t)
            
            urgency = w_ideal - w_curr
            
            pending_migrations.append({
                "player": p,
                "from": curr_t,
                "to": ideal_t,
                "urgency": urgency
            })

    # On trie par urgence (ceux qui ont le plus grand écart de poids passent en premier)
    pending_migrations.sort(key=lambda x: x["urgency"], reverse=True)
    
    # Exception de Bootstrap : Le tout premier jour, on laisse passer tout le monde. 
    # Ensuite, le plafond de 3 joueurs/jour s'active.
    if len(active_tribes) == 0:
        allowed_moves = pending_migrations
    else:
        allowed_moves = pending_migrations[:MAX_DAILY_TRANSFERS]
        
    for move in allowed_moves:
        current_roster[move["player"]] = move["to"]

    # 4. Nettoyage & Mortalité
    tribe_counts = Counter(current_roster.values())
    for t in list(active_tribes):
        if tribe_counts[t] < MIN_TRIBE_SURVIVAL:
            # Dissolution : La tribu meurt, ses rescapés deviennent non-alignés
            for p, t_assigned in list(current_roster.items()):
                if t_assigned == t:
                    current_roster[p] = UNALIGNED_LABEL
                    
    # Mise à jour stricte des tribus actives pour l'affichage
    active_tribes = sorted({t for t in current_roster.values() if t != UNALIGNED_LABEL})

    # 5. Formatage pour le frontend (Jinja2)
    snapshot_players = []
    tribe_summary = {t: 0 for t in active_tribes + [UNALIGNED_LABEL]}
    
    for p, games in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        main_t = current_roster.get(p, UNALIGNED_LABEL)
        tribe_summary[main_t] = tribe_summary.get(main_t, 0) + 1
        
        scores = {}
        if p in G and G.degree(p) > 0:
            total_w = sum(G[p][n]["weight"] for n in G.neighbors(p))
            for t in active_tribes:
                t_w = sum(G[p][n]["weight"] for n in G.neighbors(p) if current_roster.get(n) == t)
                pct = round((t_w / total_w) * 100) if total_w > 0 else 0
                
                status = "Wavering"
                if t == main_t:
                    status = "Loyalist" if pct >= 55 else "Affiliate"
                scores[t] = {"pct": pct, "status": status}
        else:
            scores = {t: {"pct": 0, "status": "Wavering"} for t in active_tribes}
            
        snapshot_players.append({
            "name": p,
            "games": games,
            "main_tribe": main_t,
            "scores": scores
        })
        
    snapshots[d] = {
        "active_tribes": active_tribes,
        "summary": tribe_summary,
        "players": snapshot_players
    }

# ==============================================================================
# 🎨 GÉNÉRATION HTML
# ==============================================================================

if Path(TEMPLATE_DIR).exists() and (Path(TEMPLATE_DIR) / TEMPLATE_FILE).exists():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(TEMPLATE_FILE)
    
    html_content = template.render(
        dates_json=json.dumps(sorted_dates),
        snapshots_json=json.dumps(snapshots)
    )
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Fichier {OUTPUT_FILE} généré avec succès.")
else:
    print(f"⚠️ Template {TEMPLATE_DIR}/{TEMPLATE_FILE} introuvable. Écriture d'un JSON de dump pour vérifier la structure.")
    with open("snapshots_dump.json", "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=4)
