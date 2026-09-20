"""
frog.py — tribus dynamiques de joueurs au fil d'une saison.

L'idée tient en une phrase : "on ne bouge que si c'est CLAIREMENT mieux".

Chaque jour :
  1. On met à jour le graphe joueur↔joueur (les vieilles arêtes s'érodent).
  2. LA BOUSSOLE : Louvain propose une tribu "idéale" à chaque joueur éligible.
     Elle ne fait que SUGGÉRER : elle n'expulse jamais personne.
  3. Un joueur sans tribu suit la boussole SI ELLE CONFIRME son lien le plus fort ;
     un joueur déjà en tribu ne la quitte que si l'autre tribu l'attire STICKINESS
     fois plus (et au plus MAX_DAILY_TRANSFERS par jour).
  4. Un cluster qui ne correspond à aucune tribu existante (et ≥ MIN_TRIBE_CREATION_SIZE
     joueurs éligibles) fonde une nouvelle tribu, d'un bloc.
  5. Une tribu qui tombe sous MIN_TRIBE_SURVIVAL membres disparaît ; un joueur resté
     inactif trop longtemps quitte aussi sa tribu, individuellement.

--------------------------------------------------------------------------------
CORRECTIFS apportés à la version précédente (voir commentaires "# FIX" inline) :

1. DÉTERMINISME — networkx.community.louvain_communities n'est PAS reproductible
   d'une exécution à l'autre malgré seed=42 : l'ordre de parcours des nœuds dépend
   en partie du hachage des chaînes Python, randomisé par processus. On fige
   PYTHONHASHSEED avant même que le script ne démarre (ré-exécution unique).

2. ENTRÉE DEPUIS "NON-ALIGNÉ" SANS FILTRE — un joueur qui devient éligible suivait
   la boussole (Louvain) sans aucune vérification, même si son lien réel le plus
   fort était ailleurs. On n'accepte plus le placement immédiat que si la tribu
   proposée est aussi celle avec qui il a le plus de poids réel.

3. SEUIL DE FONDATION == SEUIL DE SURVIE (6 = 6) — une tribu tout juste fondée
   pouvait disparaître entièrement en perdant un seul membre. On fonde plus large
   (8) qu'il ne faut pour survivre (6), pour laisser un peu de marge aux tribus
   naissantes.

4. STATUT "WAVERING" MAL CALCULÉ — la marge comparait les deux meilleurs scores
   globaux, pas la tribu principale contre sa meilleure alternative : un joueur
   pouvait être affiché "Wavering" sur sa tribu principale simplement parce que
   deux AUTRES tribus se talonnaient. Corrigé pour comparer tribu principale vs
   meilleure alternative.

5. MEMBRES FANTÔMES — un joueur inactif restait dans sa tribu indéfiniment tant
   que celle-ci ne s'effondrait pas globalement. On retire désormais aussi les
   joueurs individuellement inactifs depuis plus de INACTIVITY_LIMIT_DAYS jours.

6. IDENTITÉ DES TRIBUS — un nom de tribu libéré (dissolution) pouvait être
   réutilisé pour un groupe de joueurs complètement différent, ce qui brouille
   toute lecture dans le temps ("Tribe D" en avril ≠ "Tribe D" en juin). On
   numérote désormais chaque (re)fondation et on expose un libellé distinct
   (ex. "Tribe D #2") en plus du nom technique, sans rien changer à la logique
   interne (roster, dissolution, etc. utilisent toujours le nom technique).

7. TRAÇABILITÉ — chaque entrée, sortie ou transfert de tribu émet désormais un
   évènement court et standardisé dans le JSON (snapshots[d]["events"]), avec
   un code de raison fixe parmi REASON_LABELS. Objectif : pouvoir afficher
   "AERotters+5277 a rejoint Tribe D (lien le plus fort confirmé)" sans logique
   supplémentaire côté template.
--------------------------------------------------------------------------------
"""

# --- FIX 1 : déterminisme --------------------------------------------------
# networkx (Louvain) est sensible au hachage des chaînes, qui est randomisé par
# processus par défaut en Python. On fige PYTHONHASHSEED avant tout le reste en
# relançant le script une seule fois avec la variable d'environnement posée.
import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)
# -----------------------------------------------------------------------------

import json
import math
import statistics
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

import networkx as nx
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# ⚙️ CONFIGURATION
# ==============================================================================

# --- Tribus ---
MAX_TRIBES = 5                 # Nombre max de tribus simultanées
MIN_TRIBE_CREATION_SIZE = 8    # FIX 3 : fonder plus large que le seuil de survie
MIN_TRIBE_SURVIVAL = 6         # Joueurs minimum pour qu'une tribu SURVIVE

# --- Éligibilité (un seul seuil global, pas de seuil par tribu) ---
MIN_GAMES_FLOOR = 3            # Plancher absolu de matchs
DYNAMIC_RATIO = 2.0            # Seuil = max(plancher, ratio × médiane globale)

# --- Stabilité (LES réglages qui comptent) ---
STICKINESS = 1.5               # Pour quitter sa tribu : affinité ailleurs > STICKINESS × affinité actuelle
MAX_DAILY_TRANSFERS = 3        # Max de changements de tribu (A→B) par jour
INACTIVITY_LIMIT_DAYS = 21     # FIX 5 : au-delà, un joueur sort individuellement de sa tribu

# --- Graphe ---
DECAY_RATE = 0.95              # Érosion quotidienne des arêtes
NEW_MATCH_WEIGHT = 1.0         # Poids d'un match
MIN_EDGE_WEIGHT = 0.1          # Sous ce poids, l'arête est ignorée

UNALIGNED_LABEL = "-"
TRIBE_NAMES_POOL = ["Tribe A", "Tribe B", "Tribe C", "Tribe D", "Tribe E"]

# --- FIX 7 : vocabulaire fixe pour les évènements (entrée / sortie / transfert) ---
# Chaque évènement du journal utilise l'un de ces codes ; le libellé est fourni
# pour un affichage direct, sans logique supplémentaire côté template.
REASON_LABELS = {
    "fondation":    "Nouvelle tribu fondée",
    "confirmation": "Lien le plus fort confirmé",
    "attraction":   "Attiré par une tribu plus forte",
    "dissolution":  "Tribu dissoute (sous le seuil)",
    "inactivite":   f"Inactif depuis plus de {INACTIVITY_LIMIT_DAYS}j" if INACTIVITY_LIMIT_DAYS else "Inactif",
}

CONFIG_PATH = Path("data/config/config.json")
DEFAULT_MATCHES_PATH = Path("data/rdl/archives/lh03/matches.json")
TEMPLATE_DIR = "templates"
TEMPLATE_FILE = "frog.html"
OUTPUT_FILE = Path("frog.html")


# ==============================================================================
# 🧩 BRIQUES DE L'ALGORITHME
# ==============================================================================

def min_games_required(player_games):
    """Seuil d'éligibilité global : max(plancher, ratio × médiane)."""
    median = statistics.median(player_games.values()) if player_games else 0
    return max(MIN_GAMES_FLOOR, math.ceil(median * DYNAMIC_RATIO))


def weight_by_tribe(G, roster, p):
    """Poids total des arêtes de p vers chaque tribu (les non-alignés sont ignorés)."""
    weights = Counter()
    for n in G.neighbors(p):
        tribe = roster.get(n, UNALIGNED_LABEL)
        if tribe != UNALIGNED_LABEL:
            weights[tribe] += G[p][n]["weight"]
    return weights


def is_clearly_apart(G, roster, comm):
    """
    Un cluster ne fonde une tribu que s'il est plus lié à LUI-MÊME qu'au reste de la tribu
    dont il vient — sinon ce n'est qu'un sous-groupe passager (bruit de Louvain).
    Joueurs sans tribu d'origine : rien ne les retient, donc toujours vrai.
    """
    inside = outside = 0.0
    for p in comm:
        for n in G.neighbors(p):
            w = G[p][n]["weight"]
            if n in comm:
                inside += w
            elif roster[p] != UNALIGNED_LABEL and roster[n] == roster[p]:
                outside += w
    return inside > STICKINESS * outside


def compass(G, roster, eligible):
    """
    Louvain sur les joueurs éligibles → tribu "idéale" de chacun.
    Retourne (cible, fondees) :
      cible   = {joueur: nom de tribu}  (les joueurs hors des clusters retenus n'y figurent pas)
      fondees = noms des tribus créées aujourd'hui
    """
    comms = nx.community.louvain_communities(G.subgraph(eligible), weight="weight", seed=42)
    comms.sort(key=lambda c: (-len(c), sorted(c)))  # ordre stable d'un jour à l'autre

    members = {}
    for p, t in roster.items():
        if t != UNALIGNED_LABEL:
            members.setdefault(t, set()).add(p)

    # Chaque cluster hérite de la tribu existante avec laquelle il recoupe le plus (1 pour 1)
    overlaps = sorted(((len(c & m), i, t) for i, c in enumerate(comms) for t, m in members.items()),
                      key=lambda x: (-x[0], x[1], x[2]))
    name_of = {}
    for overlap, i, t in overlaps:
        if overlap > 0 and i not in name_of and t not in name_of.values():
            name_of[i] = t

    # Les clusters restants, assez gros, fondent une nouvelle tribu (dans la limite de MAX_TRIBES)
    free = [n for n in TRIBE_NAMES_POOL if n not in members][:max(0, MAX_TRIBES - len(members))]
    founded = set()
    for i, c in enumerate(comms):
        if i not in name_of and len(c) >= MIN_TRIBE_CREATION_SIZE and free and is_clearly_apart(G, roster, c):
            name_of[i] = free.pop(0)
            founded.add(name_of[i])

    target = {p: name_of[i] for i, c in enumerate(comms) if i in name_of for p in c}
    return target, founded


def _event(player, from_tribe, to_tribe, reason):
    """FIX 7 : construit un évènement court et standardisé pour le journal du jour."""
    etype = "in" if from_tribe == UNALIGNED_LABEL else ("out" if to_tribe == UNALIGNED_LABEL else "transfer")
    return {
        "player": player,
        "type": etype,              # "in" | "out" | "transfer"
        "from": from_tribe,
        "to": to_tribe,
        "reason": reason,           # code fixe, voir REASON_LABELS
        "label": REASON_LABELS[reason],
    }


def apply_compass(G, roster, target, founded):
    """
    Applique la boussole SANS secousses :
      - fondateur d'une nouvelle tribu → on y va tout de suite (le cluster vient d'être
        validé par is_clearly_apart, pas besoin d'un test de poids supplémentaire)
      - sans tribu, boussole pointant vers une tribu EXISTANTE → on ne suit que si cette
        tribu est aussi celle avec qui le joueur a le plus de poids réel (FIX 2) ; sinon
        on attend un jour de plus plutôt que de sauter sur un signal encore fragile
      - déjà en tribu → on ne change que si l'autre tribu attire STICKINESS fois plus,
        et seulement les MAX_DAILY_TRANSFERS cas les plus nets du jour.
    Retourne la liste des évènements du jour (FIX 7).
    """
    moves, switches = [], []
    for p, t in target.items():
        current = roster[p]
        if current == t:
            continue

        if t in founded:
            moves.append((p, current, t, "fondation"))
        elif current == UNALIGNED_LABEL:
            # FIX 2 : ne pas suivre la boussole aveuglément à la première éligibilité.
            w = weight_by_tribe(G, roster, p)
            if not w or w[t] == max(w.values()):
                moves.append((p, current, t, "confirmation"))
            # sinon : signal encore trop faible/ambigu, on reste "-" un jour de plus
        else:
            w = weight_by_tribe(G, roster, p)
            if w[t] > STICKINESS * w[current]:
                switches.append((w[t] - w[current], p, current, t))

    switches.sort(reverse=True)
    moves += [(p, current, t, "attraction") for _, p, current, t in switches[:MAX_DAILY_TRANSFERS]]

    events = []
    for p, current, t, reason in moves:
        roster[p] = t
        events.append(_event(p, current, t, reason))
    return events


def prune_inactive(roster, last_active, current_date):
    """FIX 5 : un joueur individuellement inactif depuis trop longtemps quitte sa tribu,
    même si celle-ci reste par ailleurs au-dessus du seuil de survie.
    Retourne la liste des évènements du jour (FIX 7)."""
    events = []
    if INACTIVITY_LIMIT_DAYS is None:
        return events
    cur = date.fromisoformat(current_date)
    for p, t in roster.items():
        if t == UNALIGNED_LABEL:
            continue
        last = last_active.get(p)
        if last is None or (cur - date.fromisoformat(last)).days > INACTIVITY_LIMIT_DAYS:
            roster[p] = UNALIGNED_LABEL
            events.append(_event(p, t, UNALIGNED_LABEL, "inactivite"))
    return events


def dissolve_small_tribes(roster):
    """Une tribu sous MIN_TRIBE_SURVIVAL membres disparaît.
    Retourne la liste des évènements du jour (FIX 7)."""
    events = []
    counts = Counter(t for t in roster.values() if t != UNALIGNED_LABEL)
    for tribe, n in counts.items():
        if n < MIN_TRIBE_SURVIVAL:
            for p, t in roster.items():
                if t == tribe:
                    roster[p] = UNALIGNED_LABEL
                    events.append(_event(p, tribe, UNALIGNED_LABEL, "dissolution"))
    return events


def player_scores(G, roster, p, active_tribes):
    """Pourcentage d'interactions par tribu + statut (sur la tribu principale uniquement)."""
    scores = {t: {"pct": 0, "status": None} for t in TRIBE_NAMES_POOL}
    if p not in G or G.degree(p) == 0:
        return scores

    by_tribe, total = Counter(), 0.0
    for n in G.neighbors(p):
        w = G[p][n]["weight"]
        total += w
        by_tribe[roster.get(n, UNALIGNED_LABEL)] += w

    pcts = {t: round(100 * by_tribe[t] / total) for t in TRIBE_NAMES_POOL}

    main = roster.get(p, UNALIGNED_LABEL)
    # FIX 4 : la marge doit comparer la tribu PRINCIPALE à sa meilleure alternative,
    # pas les deux meilleurs scores globaux (qui peuvent ne rien avoir à voir avec main).
    main_pct = pcts.get(main, 0)
    best_other = max((pcts[t] for t in TRIBE_NAMES_POOL if t != main), default=0)
    margin = main_pct - best_other

    for t in TRIBE_NAMES_POOL:
        status = None
        if t == main:
            if margin <= 10 and len(active_tribes) > 1:
                status = "Wavering"
            elif pcts[t] >= 85:
                status = "Core"
            elif pcts[t] >= 65:
                status = "Loyalist"
            else:
                status = "Affiliate"
        scores[t] = {"pct": pcts[t], "status": status}
    return scores


# ==============================================================================
# 🚀 CHARGEMENT DES DONNÉES
# ==============================================================================

config_path = CONFIG_PATH
if not config_path.exists():
    configs = list(Path(".").rglob("config.json"))
    if configs:
        config_path = configs[0]

config_data = {}
if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

json_path = DEFAULT_MATCHES_PATH
if not json_path.exists():
    archives = list(Path("data/rdl/archives").rglob("matches.json"))
    json_path = archives[0] if archives else Path("matches.json")

if not json_path.exists():
    print(f"❌ Erreur : Fichier de matchs introuvable à {json_path}")
    exit(1)

with open(json_path, "r", encoding="utf-8") as f:
    matches = json.load(f)

matches_by_date = {}
for m in matches:
    date_str = str(m.get("Date") or m.get("date") or m.get("date_closed") or "")[:10]
    players = list(dict.fromkeys(p.get("name") for p in m.get("players", []) if p.get("name")))
    if date_str and players:
        matches_by_date.setdefault(date_str, []).append(players)

sorted_dates = sorted(matches_by_date)


# ==============================================================================
# 🧠 BOUCLE TEMPORELLE
# ==============================================================================

edge_weights = Counter()
player_games = Counter()
last_active = {}      # FIX 5 : joueur -> dernière date jouée
roster = {}            # joueur -> nom de tribu (ou UNALIGNED_LABEL)
tribe_generation = Counter()   # FIX 6 : nom de tribu -> combien de fois il a été (re)fondé
snapshots = {}

for d in sorted_dates:
    # 1. Érosion des arêtes + nouveaux matchs du jour
    for pair in edge_weights:
        edge_weights[pair] *= DECAY_RATE

    for players in matches_by_date[d]:
        for p in players:
            player_games[p] += 1
            last_active[p] = d
            roster.setdefault(p, UNALIGNED_LABEL)
        for p1, p2 in combinations(sorted(set(players)), 2):
            edge_weights[(p1, p2)] += NEW_MATCH_WEIGHT

    G = nx.Graph()
    for (p1, p2), w in edge_weights.items():
        if w >= MIN_EDGE_WEIGHT:
            G.add_edge(p1, p2, weight=w)

    min_games = min_games_required(player_games)

    # 2. La boussole propose, le roster dispose (hystérésis + quota)
    eligible = [p for p in G.nodes() if player_games[p] >= min_games]
    target, founded = compass(G, roster, eligible)
    events = apply_compass(G, roster, target, founded)
    for t in founded:
        tribe_generation[t] += 1   # FIX 6 : on numérote chaque (re)fondation

    # 3. Mortalité (collective, puis individuelle pour inactivité) — FIX 7 : chaque
    # sortie/entrée est journalisée dans `events`, ajouté au snapshot du jour.
    events += dissolve_small_tribes(roster)
    events += prune_inactive(roster, last_active, d)
    events += dissolve_small_tribes(roster)  # une tribu peut retomber sous le seuil après le pruning

    active_tribes = sorted({t for t in roster.values() if t != UNALIGNED_LABEL})

    # FIX 6 : libellé d'affichage distinct par génération, sans toucher aux noms internes
    tribe_labels = {
        t: (t if tribe_generation[t] <= 1 else f"{t} #{tribe_generation[t]}")
        for t in TRIBE_NAMES_POOL
    }

    # 4. Snapshot pour le template
    summary = {t: 0 for t in TRIBE_NAMES_POOL + [UNALIGNED_LABEL]}
    snapshot_players = []
    for p, games in sorted(player_games.items(), key=lambda x: (-x[1], x[0])):
        main_tribe = roster[p]
        summary[main_tribe] += 1
        snapshot_players.append({
            "name": p,
            "games": games,
            "main_tribe": main_tribe,
            "scores": player_scores(G, roster, p, active_tribes),
        })

    snapshots[d] = {
        "active_tribes": active_tribes,
        "tribe_labels": tribe_labels,   # FIX 6 : {"Tribe D": "Tribe D #2", ...}
        "summary": summary,
        "players": snapshot_players,
        "events": events,               # FIX 7 : entrées/sorties/transferts du jour, avec cause
    }


# ==============================================================================
# 🎨 GÉNÉRATION HTML
# ==============================================================================

if (Path(TEMPLATE_DIR) / TEMPLATE_FILE).exists():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(TEMPLATE_FILE)

    html_content = template.render(
        config=config_data,
        active_section="frog",
        dates_json=json.dumps(sorted_dates),
        snapshots_json=json.dumps(snapshots),
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Fichier {OUTPUT_FILE} généré avec succès ({len(snapshots)} dates).")
else:
    print(f"⚠️ Template {TEMPLATE_DIR}/{TEMPLATE_FILE} introuvable.")
