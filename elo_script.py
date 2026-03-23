import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone
import json

# =========================================================================
# --- 1. CONFIGURATION ---
# =========================================================================
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 25

today = date.today()
CUTOFF_DATE = today - timedelta(days=1)
print(f"Update started. Filtering matches closed before: {today}")

def get_tier_icon(rating, games):
    if games < 10: return None, "unranked"
    r = round(rating)
    if r >= 1500: return "assets/icons/bird.png", "suit-bird"
    if r >= 1400: return "assets/icons/fox.png", "suit-fox"
    if r >= 1300: return "assets/icons/rabbit.png", "suit-rabbit"
    if r >= 1200: return "assets/icons/mouse.png", "suit-mouse"
    return None, "unranked"

# =========================================================================
# --- 2. LOAD CORRECTIONS ---
# =========================================================================

excel_file_path = 'Root_Elo_LH02_Corrected_Dates.xlsx'
excel_file_path = 'Root_Elo_LH02_Corrections.xlsx'
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(excel_file_path):
        df_updates = pd.read_excel(excel_file_path, engine='openpyxl')
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"✅ Loaded corrections from {excel_file_path}")
except Exception as e:
    print(f"ℹ️ Note: No corrections loaded (File empty or missing): {e}")

# =========================================================================
# --- 3. LOAD ARCHIVE DATA (LH01) ---
# =========================================================================

ARCHIVE_LEADERBOARD_FILE = "data/lh01_final_ratings.csv"
ARCHIVE_MATCHES_FILE = "data/lh01_matches_fixed.csv"
ARCHIVE_TRENDS_FILE = "data/lh01_history_full.json"

archive_final_df = pd.DataFrame()
archive_matches_df = pd.DataFrame()
archive_history = {}

try:
    if os.path.exists(ARCHIVE_LEADERBOARD_FILE):
        archive_final_df = pd.read_csv(ARCHIVE_LEADERBOARD_FILE)
        # Nettoyage si les colonnes Tier/Qualified manquent dans le CSV
        if 'Tier' not in archive_final_df.columns:
            archive_final_df['Tier'] = None 
    
    if os.path.exists(ARCHIVE_MATCHES_FILE):
        archive_matches_df = pd.read_csv(ARCHIVE_MATCHES_FILE)
    
    if os.path.exists(ARCHIVE_TRENDS_FILE):
        with open(ARCHIVE_TRENDS_FILE, "r", encoding="utf-8") as f:
            archive_history = json.load(f)
            archive_history = {k.split('+')[0].split('#')[0]: v for k, v in archive_history.items()}
    print("Archive LH01 loaded successfully.")
except Exception as e:
    print(f"Error loading archive files: {e}")

# =========================================================================
# --- 4. FETCH & PROCESS CURRENT SEASON ---
# =========================================================================

all_matches = []
# Ensure the ID is an integer
T_ID = int(TOURNAMENT_ID)
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={T_ID}"

print(f"🌐 Requesting data for Tournament {T_ID}...")
while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        if res.status_code == 400:
            print(f"ℹ️ Tournament {T_ID} not yet active on API. Proceeding with empty data.")
            break
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except Exception as e:
        print(f"📡 API Note: {e}")
        break

raw_data = [] 
for m in all_matches:
    participants = m.get('participants', [])
    if len(participants) == 4:
        for p in participants:
            raw_data.append({
                'GameID': m['id'],
                'Player': p.get('player'),
                'Score': float(p.get('tournament_score', 0.0)), 
                'Date_Closed': m.get('date_closed')
            })

df = pd.DataFrame(raw_data)
# Create empty columns if df is empty to prevent crashes later
if df.empty:
    print("Empty season detected. Initializing with inherited ratings only.")
    df = pd.DataFrame(columns=['GameID', 'Player', 'Score', 'Date_Closed'])
else:
    df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)
    df = df[df['Date_Closed'].dt.date < today].copy()
    df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# =========================================================================
# --- 5. ELO CALCULATION & STANDINGS ---
# =========================================================================

# 1. INITIALIZE DATASTRUCTURES (Crucial: prevents NameError if API is empty)
current_final_df = pd.DataFrame()
current_matches_df = pd.DataFrame()
current_history = {}
match_history_data = []

# 2. SETUP INITIAL ELO (Inheritance from LH01)
elo_ratings = {}
if not archive_final_df.empty:
    for _, row in archive_final_df.iterrows():
        p_name = str(row['Player'])
        # We start with the ELO they had at the end of LH01
        elo_ratings[p_name] = float(row.get('ELO', 1200))
    print(f"📊 Initialized {len(elo_ratings)} players from LH01 archive.")

# Add new players found in LH02 matches (if any)
if not df.empty:
    for player in df['Player'].unique():
        if player not in elo_ratings:
            elo_ratings[player] = 1200.0

# Initialize tracking for EVERYONE (Vets + Newcomers)
peak_elo = {p: r for p, r in elo_ratings.items()}
last_diff = {p: 0 for p in elo_ratings}
player_stats = {p: {'games': 0, 'wins': 0.0} for p in elo_ratings}
player_history = {p: [["LH01 Final", round(r)]] for p, r in elo_ratings.items()}

# 3. PROCESS LH02 MATCHES (Only runs if matches exist in the API)
if not df.empty:
    for game_id, group in df.groupby('GameID', sort=False):
        match_participants = group.to_dict('records')
        current_match_sum = sum([elo_ratings[p['Player']] for p in match_participants])
        current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
        
        # Identify winners for the match table
        winners = [p['Player'] for p in match_participants if p['Score'] >= 0.5]
        others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
        
        match_history_data.append({
            'MatchID': game_id, 
            'Date': current_date, 
            'Winner': ", ".join(winners),
            'Other Players': ", ".join(others), 
            'ELO_Sum': round(current_match_sum)
        })

        # Calculate Elo changes
        total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
        for p in match_participants:
            name = p['Player']
            expected = (10**(elo_ratings[name]/400)) / total_q
            player_stats[name]['games'] += 1
            player_stats[name]['wins'] += p['Score']
            
            # K-factor logic
            k = 80 if player_stats[name]['games'] <= 10 else (40 if player_stats[name]['games'] <= 50 else 20)
            change = k * (p['Score'] - expected)
            
            elo_ratings[name] += change
            last_diff[name] = change
            if elo_ratings[name] > peak_elo[name]: 
                peak_elo[name] = elo_ratings[name]
            player_history[name].append([current_date, round(elo_ratings[name])])

# 4. FINALIZING DATASETS FOR EXPORT
# Create current_matches_df (even if empty)
current_matches_df = pd.DataFrame(match_history_data)
if not current_matches_df.empty:
    current_matches_df = current_matches_df.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
    current_matches_df.insert(0, 'Rank', range(1, len(current_matches_df) + 1))

# =========================================================================
# --- 6. FINAL LEADERBOARD GENERATION ---
# =========================================================================

leaderboard_list = []
for p_name, rating in elo_ratings.items():
    s = player_stats.get(p_name, {'wins': 0, 'games': 0})
    diff = round(last_diff.get(p_name, 0))
    is_qual = (s['games'] >= 10 and rating >= 1200)
    
    leaderboard_list.append({
        'Rank': 0, 'Player': p_name, 'ELO': round(rating), 'Games': s['games'],
        'Wins': s['wins'], 'Win Rate': f"{(s['wins']/s['games']):.1%}" if s['games'] > 0 else "0.0%",
        'Peak': round(peak_elo.get(p_name, rating)), 
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': is_qual
    })

current_final_df = pd.DataFrame(leaderboard_list).sort_values(by='ELO', ascending=False)

# Assign rank numbers to qualified players only
rank_counter = 1
ranks = []
for _, row in current_final_df.iterrows():
    if row['Qualified']:
        ranks.append(rank_counter)
        rank_counter += 1
    else: 
        ranks.append("-")
current_final_df['Rank'] = ranks

# Trends Dictionary (Cleaning names for Chart.js)
current_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}

# =========================================================================
# --- 7. HTML SKELETON (MATRIX NAVIGATION) ---
# =========================================================================
def generate_page_html(title, page_heading, current_page, content, subtitle="", page_description="", custom_css="", custom_js="", extra_head=""):
    is_archive = "_lh01.html" in current_page
    
    # 1. Main Navigation (Adapts to selected season)
    nav_links = [("index", "Leaderboard"), ("matches", "Top Tables"), ("trends", "Player's Journey"), ("about", "Codex")]
    nav_html = ""
    for base, label in nav_links:
        if base == "about":
            target = "about.html"
        else:
            target = f"{base}_lh01.html" if is_archive else f"{base}.html"
        active = "active" if current_page.startswith(base) else ""
        nav_html += f'<a href="{target}" class="{active}">{label}</a>'

    # 2. Sub Navigation (Season Selector)
    if current_page == "about.html":
        sub_nav_html = ""
    else:
        current_prefix = current_page.replace("_lh01.html", "").replace(".html", "")
        
        seasons = [
            ("LH01", f"{current_prefix}_lh01.html"),
            ("LH02", f"{current_prefix}.html")
        ]
        
        buttons_html = ""
        for name, url in seasons:
            is_active = "active" if url == current_page else ""
            buttons_html += f'<a href="{url}" class="season-btn {is_active}">{name}</a>'
        
        sub_nav_html = f"""
        <div class="season-selector">
            <span class="season-label">Select Season</span>
            {buttons_html}
        </div>
        """

    base_css = """
        body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background: #121212; color: #eee; text-align: center; padding: 20px 5px; margin: 0; overflow-x: hidden; }
        .container { width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); box-sizing: border-box; }
        .site-header { margin-bottom: 20px; }
        .site-title { color: #4a90e2; font-size: 2.2em; margin: 0; letter-spacing: 3px; text-transform: uppercase; }
        .site-subtitle { font-style: italic; color: #555; font-size: 0.85em; margin: 5px 0 0; letter-spacing: 1px; }
        nav { margin: 20px 0; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
        nav a { color: #888; text-decoration: none; font-weight: bold; text-transform: uppercase; font-size: 0.8em; padding: 8px 16px; border-radius: 6px; transition: 0.3s; border: 1px solid transparent; }
        nav a:hover { color: #4a90e2; background: rgba(74,144,226,0.05); }
        nav a.active { color: #fff; background: #4a90e2; box-shadow: 0 4px 12px rgba(74,144,226,0.3); }
        .season-selector { display: flex; align-items: center; justify-content: center; gap: 12px; margin: 0 auto 30px; background: rgba(255,255,255,0.03); padding: 8px 18px; border-radius: 50px; width: fit-content; border: 1px solid #333; }
        .season-label { font-size: 0.7em; text-transform: uppercase; color: #555; letter-spacing: 1.2px; font-weight: bold; }
        .season-btn { text-decoration: none; font-size: 0.75em; font-weight: bold; color: #777; padding: 5px 14px; border-radius: 20px; border: 1px solid #444; transition: 0.2s; }
        .season-btn:hover { border-color: #4a90e2; color: #eee; }
        .season-btn.active { background: #4a90e2; color: #fff; border-color: #4a90e2; box-shadow: 0 0 12px rgba(74,144,226,0.2); }
        .page-intro { margin-bottom: 35px; display: flex; flex-direction: column; align-items: center; gap: 6px; }
        .page-intro h2 { margin: 0; text-transform: uppercase; color: #eee; font-size: 1.3em; }
        .page-intro h3 { margin: 0; color: #4a90e2; font-size: 1em; font-weight: 500; }
        .page-intro p { margin: 0; color: #888; font-size: 0.85em; max-width: 600px; line-height: 1.4; }
        .dataTables_wrapper { color: #eee !important; text-align: left; }
        table.dataTable { width: 100% !important; border-collapse: collapse !important; margin-top: 15px !important; background: #1e1e1e; }
        table.dataTable thead th { background: #252525 !important; color: #4a90e2 !important; font-size: 0.75em; text-transform: uppercase; padding: 12px; border: none; }
        table.dataTable td { border-bottom: 1px solid #2a2a2a; padding: 10px; font-size: 0.9em; text-align: center; vertical-align: middle; }
        @media (max-width: 600px) { .container { padding: 10px; } .site-title { font-size: 1.6em; } .dataTables_filter input { width: 120px !important; } table.dataTable td { font-size: 0.75em; } }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{title}</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/responsive/2.5.0/css/responsive.dataTables.min.css">
    {extra_head}
    <style>
        {base_css}
        /* Style pour le titre fixe */
        .site-header {{ margin-bottom: 20px; }}
        .site-title {{ color: #4a90e2; font-size: 2.5em; margin-bottom: 0; letter-spacing: 3px; }}
        .site-subtitle {{ font-style: italic; color: #777; font-size: 0.9em; margin-top: 5px; letter-spacing: 1px; }}
        .page-heading {{ color: #eee; text-transform: uppercase; font-size: 1.2em; margin-top: 30px; border-bottom: 1px solid #333; display: inline-block; padding-bottom: 5px; }}
        {custom_css}
    </style>
</head>
<body>
    <div class="container">
        <div class="site-header">
            <h1 class="site-title">ROOTELO</h1>
            <p class="site-subtitle">A Metric of Woodland Skill and Will</p>
        </div>

        <nav>{nav_html}</nav>
        {sub_nav_html}

        <header class="page-intro">
            <h2>{page_heading}</h2>
            {f"<h3>{subtitle}</h3>" if subtitle else ""}
            {f"<p>{page_description}</p>" if page_description else ""}
        </header>
    
        <main>
            {content}
        </main>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>
    {custom_js}
</body>
</html>"""


# =========================================================================
# --- 8. PAGE BUILDERS (REUSABLE COMPONENTS) ---
# =========================================================================

def build_leaderboard_page(df, filename, title, heading, subtitle, description):
    table_rows = ""
    if not df.empty:
        for _, row in df.iterrows():
            icon_path, _ = get_tier_icon(row['ELO'], row['Games'])
            icon_tag = f'<div class="tier-icon-container"><img src="{icon_path}"></div>' if icon_path else ""
            display_name = str(row['Player']).split('+')[0].split('#')[0]
            table_rows += f"""
            <tr>
                <td>{row['Rank']}</td><td>{icon_tag}</td><td class="player-name-cell">{display_name}</td>
                <td>{row['ELO']}</td><td>{row['Games']}</td><td>{row['Wins']}</td>
                <td>{row['Win Rate']}</td><td>{row['Peak']}</td><td>{row['Last']}</td>
            </tr>"""

    content = f"""
        <table id="leaderboard" class="display nowrap">
            <thead>
                <tr><th>Rank</th><th>Tier</th><th>Player</th><th>ELO</th><th>Games</th><th>Wins</th><th>Win Rate</th><th>Peak</th><th>Last</th></tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
        <div class="footer">
            <strong>Tier System</strong> (min 10 games):<br>
            <span class="footer-tier-item"><img src="assets/icons/bird.png"> 1500+</span>
            <span class="footer-tier-item"><img src="assets/icons/fox.png"> 1400+</span>
            <span class="footer-tier-item"><img src="assets/icons/rabbit.png"> 1300+</span>
            <span class="footer-tier-item"><img src="assets/icons/mouse.png"> 1200+</span><br>
            Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
        </div>
    """
    css = """
        .tier-icon-container { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; margin: 0 auto; }
        .tier-icon-container img { max-width: 100%; max-height: 100%; object-fit: contain; }
        .tier-bird   { background-color: rgba(103, 192, 199, 0.1) !important; border-left: 4px solid #67c0c7 !important; }
        .tier-fox    { background-color: rgba(230, 55, 45, 0.1) !important; border-left: 4px solid #e6372d !important; }
        .tier-rabbit { background-color: rgba(247, 235, 91, 0.1) !important; border-left: 4px solid #f7eb5b !important; }
        .tier-mouse  { background-color: rgba(242, 144, 87, 0.1) !important; border-left: 4px solid #f29057 !important; }
        .tier-bird td:nth-child(3), .tier-bird td:nth-child(4)   { color: #67c0c7; font-weight: bold; }
        .tier-fox td:nth-child(3), .tier-fox td:nth-child(4)     { color: #e6372d; font-weight: bold; }
        .tier-rabbit td:nth-child(3), .tier-rabbit td:nth-child(4) { color: #f7eb5b; font-weight: bold; }
        .tier-mouse td:nth-child(3), .tier-mouse td:nth-child(4)  { color: #f29057; font-weight: bold; }
        .unranked { opacity: 0.5; font-style: italic; }
        .footer { margin-top: 30px; font-size: 0.75em; color: #777; border-top: 1px solid #333; padding-top: 15px; line-height: 2; }
        .footer-tier-item { display: inline-block; margin: 0 10px; vertical-align: middle; }
        .footer-tier-item img { height: 18px; width: auto; vertical-align: middle; margin-right: 4px; }
        .player-name-cell { text-align: left !important; padding-left: 15px !important; font-weight: 500; }
    """
    js = """<script>
    $(document).ready(function() {
        $.extend($.fn.dataTable.ext.type.order, { "rank-pre": function (d) { return d === "-" ? 9999 : parseInt(d); } });
        $('#leaderboard').DataTable({
            "order": [[3, "desc"]], "responsive": true, "pageLength": 50,
            "columnDefs": [ { "targets": 2, "className": "player-name-cell" }, { "responsivePriority": 1, "targets": [0, 2, 3] } ],
            "createdRow": function(row, data) {
                var rank = data[0]; var elo = parseInt(data[3]); 
                if (rank === "-") { $(row).addClass('unranked'); } else {
                    if (elo >= 1500) $(row).addClass('tier-bird');
                    else if (elo >= 1400) $(row).addClass('tier-fox');
                    else if (elo >= 1300) $(row).addClass('tier-rabbit');
                    else if (elo >= 1200) $(row).addClass('tier-mouse');
                }
            }
        });
    });
    </script>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_page_html(title, heading, filename, content, subtitle=subtitle, page_description=description, custom_css=css, custom_js=js))

def build_matches_page(df, filename, title, heading, subtitle, description):
    match_rows = ""
    if not df.empty:
        for _, row in df.iterrows():
            def clean_names(name_str):
                if pd.isna(name_str) or not str(name_str).strip(): return ""
                return ", ".join([str(n).strip().split('+')[0].split('#')[0] for n in str(name_str).split(',')])

            cleaned_winner = clean_names(row.get("Winner", ""))
            cleaned_others = clean_names(row.get("Other Players", ""))
            winner_html = f'<span style="color: #f7eb5b; font-weight: bold;">{cleaned_winner}</span>'
            others_html = f'<span style="color: #888;">{cleaned_others}</span>'
            lineup_html = f'<div style="white-space: normal; word-break: break-word; min-width: 150px;">{winner_html}, {others_html}</div>'
            match_url = f"https://rootleague.pliskin.dev/match/{row['MatchID']}/"
        
            match_rows += f"""
            <tr>
                <td>{row['Rank']}</td><td style="font-weight:bold; color:#4a90e2;">{row['ELO_Sum']}</td>
                <td>{row['Date']}</td><td style="text-align: left; padding-left: 20px;">{lineup_html}</td>
                <td><a href="{match_url}" target="_blank" style="color: #666; text-decoration: none; font-family: monospace; font-size: 0.9em; border: 1px solid #333; padding: 2px 6px; border-radius: 4px;">{row['MatchID']} ↗</a></td>
            </tr>"""

    content = f"""
        <table id="matchesTable" class="display nowrap responsive" style="width:100%">
            <thead><tr><th>Rank</th><th>ELO</th><th>Date</th><th>Lineup (Winner First)</th><th>ID</th></tr></thead>
            <tbody>{match_rows}</tbody>
        </table>
    """
    css = """
        .lineup-cell { white-space: normal !important; word-wrap: break-word; overflow-wrap: break-word; min-width: 120px; max-width: 250px; line-height: 1.4; text-align: left; }
        table.dataTable.dtr-inline.collapsed > tbody > tr > td.dtr-control:before { background-color: #4a90e2 !important; }
        table.dataTable > tbody > tr.child ul.dtr-details { width: 100%; background: #252525; }
        table.dataTable > tbody > tr.child span.dtr-title { color: #4a90e2; font-weight: bold; }
    """
    js = """<script>
    $(document).ready(function() {
        $('#matchesTable').DataTable({
            "order": [[1, "desc"]], 
            "responsive": true, 
            "pageLength": 25,
            "columnDefs": [
                { "width": "40px", "targets": [0, 1] },
                { "className": "lineup-cell", "targets": 3 }, 
                { "responsivePriority": 1, "targets": [0, 1, 3] },
                { "responsivePriority": 2, "targets": 2 }, 
                { "responsivePriority": 3, "targets": 4 }
            ]
        });
    });
    </script>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_page_html(title, heading, filename, content, subtitle=subtitle, page_description=description, custom_css=css, custom_js=js))

def build_trends_page(history_dict, filename, title, heading, subtitle, description):
    if not history_dict: return
    
    history_json = json.dumps(history_dict)
    player_names_list = sorted(list(history_dict.keys()))

    content = f"""
        <div class="search-box">
            <input list="playerList" id="playerName" placeholder="Search Player..." oninput="updateChart()">
            <datalist id="playerList">
                {''.join([f'<option value="{name}">' for name in player_names_list])}
            </datalist>
        </div>
        <div class="landscape-hint">🔄 Rotate phone for detail</div>
        <div class="chart-wrapper">
            <div class="chart-container"><canvas id="progressionChart"></canvas></div>
        </div>
    """
    css = """
        .search-box { margin: 10px 0; }
        input { background: #252525; color: #fff; border: 1px solid #444; padding: 12px; border-radius: 8px; width: 90%; max-width: 400px; font-size: 16px; box-sizing: border-box; }
        .landscape-hint { display: none; color: #666; font-size: 0.7em; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; }
        .chart-wrapper { width: 100%; padding: 0 5px; box-sizing: border-box; }
        .chart-container { position: relative; width: 100%; height: 50vh; background: #1a1a1a; border-radius: 8px; }
        @media (max-width: 768px) and (orientation: portrait) { .landscape-hint { display: block; } }
    """
    extra_head = '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
    js = f"""<script>
        const allData = {history_json};
        let myChart;
        function updateChart() {{
            const name = document.getElementById('playerName').value;
            const ctx = document.getElementById('progressionChart').getContext('2d');
            if (allData[name]) {{
                const rawData = allData[name];
                const labels = rawData.map(d => d[0]);
                const eloScores = rawData.map(d => d[1]);
                if (myChart) myChart.destroy();
                myChart = new Chart(ctx, {{
                    type: 'line',
                    data: {{ labels: labels, datasets: [{{ data: eloScores, borderColor: '#4a90e2', backgroundColor: 'rgba(74, 144, 226, 0.1)', borderWidth: 2, fill: true, tension: 0.3, pointRadius: 2, pointHitRadius: 20 }}] }},
                    options: {{
                        responsive: true, maintainAspectRatio: false,
                        plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: true, mode: 'index', intersect: false, backgroundColor: '#222' }} }},
                        scales: {{ y: {{ grid: {{ color: '#252525' }}, ticks: {{ color: '#666', font: {{ size: 9 }} }} }}, x: {{ grid: {{ display: false }}, ticks: {{ color: '#666', font: {{ size: 9 }}, maxTicksLimit: 6, maxRotation: 0 }} }} }}
                    }}
                }});
            }}
        }}
    </script>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_page_html(title, heading, filename, content, subtitle=subtitle, page_description=description, custom_css=css, custom_js=js, extra_head=extra_head))
        
def build_about_page(filename, title, heading):
    codex_text = f"""
    <style>
        .codex-section {{ margin-bottom: 40px; text-align: left; max-width: 800px; margin-left: auto; margin-right: auto; line-height: 1.7; color: #ccc; }}
        .tier-list {{ list-style: none; padding: 0; }}
        .tier-item {{ 
            display: flex; 
            align-items: center; 
            margin-bottom: 15px; 
            background: #252525; 
            padding: 12px; 
            border-radius: 8px;
            border-left: 4px solid #333;
        }}
        .tier-item img {{ height: 32px; width: auto; margin-right: 15px; }}
        .tier-bird {{ border-color: #67c0c7; }}
        .tier-fox {{ border-color: #e6372d; }}
        .tier-rabbit {{ border-color: #f7eb5b; }}
        .tier-mouse {{ border-color: #f29057; }}
        .k-table {{ width: 100%; border-collapse: collapse; background: #1a1a1a; margin-top: 10px; }}
        .k-table td {{ padding: 12px; border-bottom: 1px solid #333; }}
        .k-val {{ color: #4a90e2; font-weight: bold; font-family: monospace; font-size: 1.1em; }}
    </style>

    <div class="codex-section">
        <h2 style="color: #4a90e2; border-bottom: 1px solid #333; padding-bottom: 10px;">How does this system work?</h2>
        <p>To ensure fairness in a 4-player format, this leaderboard uses a <strong> multi-player Elo model</strong>.</p>
        <p>Unlike a simple win-count, it calculates your score based on the <em>"Strength of Schedule"</em>. If you beat high-ranked players, you gain more. If you lose as the favorite, you drop more.</p>

        <h2 style="color: #4a90e2; margin-top: 40px;">The Tier System</h2>
        <p>After your 10-game calibration phase, you officially join the ranks and unlock your tier icon:</p>
        
        <div class="tier-list">
            <div class="tier-item tier-bird">
                <img src="assets/icons/bird.png">
                <div><strong style="color: #67c0c7;">Bird (1500+)</strong> – The Grandmasters.</div>
            </div>
            <div class="tier-item tier-fox">
                <img src="assets/icons/fox.png">
                <div><strong style="color: #e6372d;">Fox (1400+)</strong> – The top predators.</div>
            </div>
            <div class="tier-item tier-rabbit">
                <img src="assets/icons/rabbit.png">
                <div><strong style="color: #f7eb5b;">Rabbit (1300+)</strong> – High-level competitors.</div>
            </div>
            <div class="tier-item tier-mouse">
                <img src="assets/icons/mouse.png">
                <div><strong style="color: #f29057;">Mouse (1200+)</strong> – Established consistent players.</div>
            </div>
        </div>

        <h2 style="color: #4a90e2; margin-top: 40px;">Dynamic K-Factor</h2>
        <p>Your score's volatility changes as you play more games to ensure stability:</p>
        <table class="k-table">
            <tr>
                <td><strong>Calibration</strong> (0-10 games)</td>
                <td class="k-val">K = 80</td>
                <td style="font-size: 0.85em; color: #888;">Find your rank quickly.</td>
            </tr>
            <tr>
                <td><strong>Active</strong> (11-50 games)</td>
                <td class="k-val">K = 40</td>
                <td style="font-size: 0.85em; color: #888;">Competitive weighting.</td>
            </tr>
            <tr>
                <td style="border:none;"><strong>Veteran</strong> (50+ games)</td>
                <td class="k-val" style="border:none;">K = 20</td>
                <td style="font-size: 0.85em; color: #888; border:none;">Long-term stability.</td>
            </tr>
        </table>

        <p style="margin-top: 60px; font-size: 0.8em; color: #555; text-align: center; border-top: 1px solid #333; padding-top: 20px;">
            Every player starts the season with a base score of 1200.<br>
            Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
        </p>
    </div>
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_page_html(title, heading, filename, codex_text))

# =========================================================================
# --- 9. FILTERS ---
# ========================================================================
# Rule: To be displayed on the leaderboard, a player needs at least 1 win.

# Filter Current Season (LH02)
display_current_df = pd.DataFrame()
if not current_final_df.empty:
    display_current_df = current_final_df[current_final_df['Wins'].astype(float) >= 1].copy()

# Filter Archive Season (LH01)
display_archive_df = pd.DataFrame()
if not archive_final_df.empty:
    display_archive_df = archive_final_df[archive_final_df['Wins'].astype(float) >= 1].copy()

# =========================================================================
# --- 10. EXECUTE GENERATION ---
# =========================================================================

# A. Generate Current Season Pages (Live API Data)
print("Generating Current Season pages...")
build_leaderboard_page(
    display_current_df, 
    "index.html", 
    "Leaderboard • Rootelo", 
    "Leaderboard", 
    "LH02 • Apr–Jun 2026", 
    f"Minimum 1 win required for display. Data tracked until {CUTOFF_DATE}. Use the search bar to find a specific player."
)
build_matches_page(
    current_matches_df, 
    "matches.html", 
    "Top Tables • Rootelo", 
    "Top Tables", 
    "LH02 • Apr–Jun 2026",
    f"Games ranked by total ELO. Search by player or date. Click a Game ID to view full match details on the League website."
)
build_trends_page(
    current_history, 
    "trends.html", 
    "Player's Journey • Rootelo", 
    "Player's Journey", 
    "LH02 • Apr–Jun 2026",
    "Search for a player to see their ELO evolution over the season."
)

# B. Generate Archive LH01 Pages (Loaded Data)
print("Generating Archive LH01 pages...")
build_leaderboard_page(
    display_archive_df, 
    "index_lh01.html", 
    "Leaderboard • Rootelo", 
    "Leaderboard", 
    "LH01 • Jan–Mar 2026", 
    f"Minimum 1 win required for display. Data tracked until 2026-03-31. Use the search bar to find a specific player."
)
build_matches_page(
    archive_matches_df, 
    "matches_lh01.html", 
    "Top Tables • Rootelo", 
    "Top Tables",
    "LH01 • Jan–Mar 2026",
    f"Games ranked by total ELO. Search by player or date. Click a Game ID to view full match details on the League website."
)
build_trends_page(
    archive_history, 
    "trends_lh01.html", 
    "Player's Journey • Rootelo", 
    "Player's Journey", 
    "LH01 • Jan–Mar 2026",
    "Search for a player to see their ELO evolution over the season."
)

# C. Generate Codex Page
build_about_page("about.html", "Codex • Root League", "The Woodland Codex")

print("Done! All files generated.")
