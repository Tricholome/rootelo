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
TOURNAMENT_ID = 24

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
excel_file_path = 'Root_Elo_LH01_Corrected_Dates.xlsx'
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(excel_file_path):
        df_updates = pd.read_excel(excel_file_path, engine='openpyxl')
        if not df_updates.empty and 'GameID' in df_updates.columns:
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"Loaded {len(game_id_mapping)} manual corrections.")
except Exception as e:
    print(f"Note: Excel skipped or error: {e}")


# =========================================================================
# --- 3. FETCH & PROCESS CURRENT SEASON (API) ---
# =========================================================================
all_matches = []
next_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"
while next_url:
    try:
        res = requests.get(next_url, headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        all_matches.extend(data.get('results', []))
        next_url = data.get('next')
    except: 
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
df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

try:
    if not game_id_mapping.empty:
        mask = df['GameID'].isin(game_id_mapping.index)
        if mask.any():
            original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
            new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
            combined_datetimes = new_dates + ' ' + original_times
            df.loc[mask, 'Date_Closed'] = pd.to_datetime(combined_datetimes, utc=True)
            print(f"Corrected {mask.sum() // 4} games while preserving original timestamps.")
except Exception as e:
    print(f"Date mapping note: {e}")

df = df[df['Date_Closed'].dt.date < today].copy()
df = df.sort_values(by='Date_Closed').reset_index(drop=True)


# =========================================================================
# --- 4. ELO CALCULATION (CURRENT SEASON) ---
# =========================================================================
elo_ratings = {player: 1200 for player in df['Player'].unique()}
peak_elo = {player: 1200 for player in df['Player'].unique()}
last_diff = {player: 0 for player in df['Player'].unique()}
player_stats = {player: {'games': 0, 'wins': 0.0} for player in df['Player'].unique()}
player_history = {player: [["Start", 1200]] for player in df['Player'].unique()}

match_history_data = []

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    if len(match_participants) != 4: continue
    
    current_match_sum = sum([elo_ratings.get(p['Player'], 1200) for p in match_participants])
    solo_winners = [p['Player'] for p in match_participants if p['Score'] == 1.0]
    co_winners = [p['Player'] for p in match_participants if p['Score'] == 0.5]
    others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
    
    match_history_data.append({
        'MatchID': game_id,
        'Date': pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d'),
        'Winner': ", ".join(solo_winners + co_winners),
        'Other Players': ", ".join(others),
        'ELO_Sum': round(current_match_sum)
    })
    
    total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
    
    for p in match_participants:
        name = p['Player']
        actual = p['Score']
        expected = (10**(elo_ratings[name]/400)) / total_q
        
        player_stats[name]['games'] += 1
        player_stats[name]['wins'] += actual
        
        if player_stats[name]['games'] <= 10: k = 80
        elif player_stats[name]['games'] <= 50: k = 40
        else: k = 20
            
        change = k * (actual - expected)
        elo_ratings[name] += change
        last_diff[name] = change
        
        if elo_ratings[name] > peak_elo[name]: peak_elo[name] = elo_ratings[name]
        player_history[p['Player']].append([current_date, round(elo_ratings[p['Player']])])


# =========================================================================
# --- 5. PREPARE CURRENT SEASON DATAFRAMES ---
# =========================================================================
# Leaderboard DF
leaderboard_results = []
for p_name, rating in elo_ratings.items():
    w = player_stats[p_name]['wins']
    g = player_stats[p_name]['games']
    if w >= 1:
        is_qual = (g >= 10 and rating >= 1200)
        diff = round(last_diff[p_name])
        leaderboard_results.append({
            'Rank': 0, 'Player': p_name, 'ELO': round(rating), 'Games': g, 
            'Wins': int(w) if w % 1 == 0 else round(w, 1),
            'Win Rate': f"{(w/g):.1%}", 'Peak': round(peak_elo[p_name]),
            'Last': f"+{diff}" if diff > 0 else str(diff), 'Qualified': is_qual
        })

current_final_df = pd.DataFrame(leaderboard_results).sort_values(by='ELO', ascending=False)
rank_list = []
curr_rank = 1
for _, row in current_final_df.iterrows():
    if row['Qualified']: rank_list.append(curr_rank); curr_rank += 1
    else: rank_list.append("-")
current_final_df['Rank'] = rank_list

# Matches DF
current_matches_df = pd.DataFrame(match_history_data).sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
current_matches_df.insert(0, 'Rank', range(1, len(current_matches_df) + 1))

# Trends Dict
current_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}


# =========================================================================
# --- 6. LOAD ARCHIVE DATA (LH01) ---
# =========================================================================

ARCHIVE_LEADERBOARD_FILE = "lh01_final_ratings.csv"
ARCHIVE_MATCHES_FILE = "lh01_matches_fixed.csv"
ARCHIVE_TRENDS_FILE = "lh01_history_full.json"

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
    print("Archive LH01 loaded successfully.")
except Exception as e:
    print(f"Error loading archive files: {e}")


# =========================================================================
# --- 7. HTML SKELETON (MATRIX NAVIGATION) ---
# =========================================================================
def generate_page_html(title, page_heading, current_page, content, custom_css="", custom_js="", extra_head=""):
    is_archive = "_lh01.html" in current_page
    
    # 1. Main Navigation (Adapts to selected season)
    nav_links = [("index", "Leaderboard"), ("matches", "Match Archive"), ("trends", "Player Trends")]
    nav_html = ""
    for base, label in nav_links:
        target = f"{base}_lh01.html" if is_archive else f"{base}.html"
        active = "active" if current_page.startswith(base) else ""
        nav_html += f'<a href="{target}" class="{active}">{label}</a>'

    # 2. Sub Navigation (Season Selector)
    current_prefix = current_page.replace("_lh01.html", "").replace(".html", "")
    sub_links = {
        f"{current_prefix}.html": "Current Season",
        f"{current_prefix}_lh01.html": "Season LH01"
    }
    sub_items_html = "".join([
        f'<a href="{url}" class="sub-nav-item {"active" if url == current_page else ""}">{name}</a>'
        for url, name in sub_links.items()
    ])
    sub_nav_html = f'<div class="sub-nav-container">{sub_items_html}</div>'

    base_css = """
        body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px 5px; margin: 0; overflow-x: hidden; }
        .container { width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); box-sizing: border-box; }
        h1 { color: #4a90e2; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; font-size: 1.5em; }
        h3 { color: #777; font-weight: 400; font-size: 0.85em; margin-bottom: 20px; }
        nav { margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }
        nav a { color: #888; text-decoration: none; font-weight: bold; text-transform: uppercase; font-size: 0.85em; padding: 8px 16px; border-radius: 6px; transition: all 0.3s ease; border: 1px solid transparent; }
        nav a:hover { color: #4a90e2; background: rgba(74,144,226,0.05); }
        nav a.active { color: #fff; background: #4a90e2; border: 1px solid #4a90e2; box-shadow: 0 4px 12px rgba(74,144,226,0.3); }
        .sub-nav-container { display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; margin-top: -5px; }
        .sub-nav-item { font-size: 0.75em; text-decoration: none; color: #666; padding: 5px 15px; border-radius: 20px; border: 1px solid #333; transition: 0.3s; font-weight: 500; }
        .sub-nav-item:hover { color: #aaa; border-color: #555; }
        .sub-nav-item.active { background: #2a2a2a; color: #4a90e2; border-color: #4a90e2; }
        .dataTables_wrapper { color: #eee !important; text-align: left; }
        table.dataTable { width: 100% !important; border-collapse: collapse !important; margin-top: 15px !important; background: #1e1e1e; }
        table.dataTable thead th { background-color: #252525 !important; color: #4a90e2 !important; font-size: 0.75em; text-transform: uppercase; padding: 12px; border-bottom: none; }
        table.dataTable td { border-bottom: 1px solid #2a2a2a; padding: 10px; font-size: 0.9em; text-align: center; vertical-align: middle; }
        @media (max-width: 600px) { .container { padding: 10px; } .dataTables_filter input { width: 150px !important; } table.dataTable td { font-size: 0.75em; } }
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
    <style>{base_css}{custom_css}</style>
</head>
<body>
    <div class="container">
        <nav>{nav_html}</nav>
        {sub_nav_html}
        <h1>{page_heading}</h1>
        {content}
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

def build_leaderboard_page(df, filename, title, heading, subtitle):
    if df.empty: return # Skip if no data
    
    table_rows = ""
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
        <h3>{subtitle}</h3>
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
        f.write(generate_page_html(title, heading, filename, content, css, js))


def build_matches_page(df, filename, title, heading):
    if df.empty: return

    match_rows = ""
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
            "order": [[1, "desc"]], "responsive": { details: { type: 'column', target: 0 } }, "pageLength": 25,
            "columnDefs": [
                { "className": "dtr-control", "targets": 0 }, { "width": "40px", "targets": [0, 1] },
                { "className": "lineup-cell", "targets": 3 }, { "responsivePriority": 1, "targets": [1, 3] },
                { "responsivePriority": 2, "targets": 2 }, { "responsivePriority": 3, "targets": 4 }
            ]
        });
    });
    </script>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_page_html(title, heading, filename, content, css, js))


def build_trends_page(history_dict, filename, title, heading):
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
        f.write(generate_page_html(title, heading, filename, content, css, js, extra_head))


# =========================================================================
# --- 9. EXECUTE GENERATION ---
# =========================================================================

# A. Generate Current Season Pages (Live API Data)
print("Generating Current Season pages...")
build_leaderboard_page(current_final_df, "index.html", "Leaderboard • Root League", "Current Season", f"Alternative ELO Leaderboard • Data until {CUTOFF_DATE}")
build_matches_page(current_matches_df, "matches.html", "Match Archive • Root League", "Match Archive")
build_trends_page(current_history, "trends.html", "Player Progression • Root League", "Player Progression")

# B. Generate Archive LH01 Pages (Loaded Data)
print("Generating Archive LH01 pages...")
build_leaderboard_page(archive_final_df, "index_lh01.html", "Archive LH01 Leaderboard", "Season LH01 Archive", "Final Standings • Season LH01")
build_matches_page(archive_matches_df, "matches_lh01.html", "Archive LH01 Matches", "Match Archive • Season LH01")
build_trends_page(archive_history, "trends_lh01.html", "Archive LH01 Trends", "Player Progression • Season LH01")

print("Done! All files generated.")
