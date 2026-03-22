import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone
import json

# --- 1. Configuration (GitHub Secrets) ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24

# --- 2. Date Setup ---
today = date.today()
CUTOFF_DATE = today - timedelta(days=1)
print(f"Update started. Filtering matches closed before: {today}")

# --- 3. Load Correction File (Excel) ---
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

# --- 4. Fetch and Process Match Data ---
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

# --- 5. Data Processing (Time-Preservation Fix) ---
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

# --- 6. ELO Calculation Logic ---
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
    
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')

    match_history_data.append({
        'MatchID': game_id,
        'Date': current_date,
        'Winner': ", ".join(solo_winners + co_winners),
        'Other Players': ", ".join(others),
        'ELO_Sum': round(current_match_sum)
    })
    
    total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
    
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
        
        if elo_ratings[name] > peak_elo[name]:
            peak_elo[name] = elo_ratings[name]

        player_history[name].append([current_date, round(elo_ratings[name])])

# --- 7. Final Leaderboard Preparation ---
def get_tier_icon(rating, games):
    if games < 10: return None, "unranked"
    r = round(rating)
    if r >= 1500: return "assets/icons/bird.png", "suit-bird"
    if r >= 1400: return "assets/icons/fox.png", "suit-fox"
    if r >= 1300: return "assets/icons/rabbit.png", "suit-rabbit"
    if r >= 1200: return "assets/icons/mouse.png", "suit-mouse"
    return None, "unranked"

leaderboard_results = []
for p_name, rating in elo_ratings.items():
    w = player_stats[p_name]['wins']
    g = player_stats[p_name]['games']
    if w >= 1:
        is_qual = (g >= 10 and rating >= 1200)
        formatted_wins = int(w) if w % 1 == 0 else round(w, 1)
        diff = round(last_diff[p_name])
        str_diff = f"+{diff}" if diff > 0 else str(diff)
        leaderboard_results.append({
            'Rank': 0, 'Tier': get_tier_icon(rating, g), 'Player': p_name,
            'ELO': round(rating), 'Games': g, 'Wins': formatted_wins,
            'Win Rate': f"{(w/g):.1%}", 'Peak': round(peak_elo[p_name]),
            'Last': str_diff, 'Qualified': is_qual
        })

final_df = pd.DataFrame(leaderboard_results).sort_values(by='ELO', ascending=False)
curr_rank = 1
rank_list = []
for _, row in final_df.iterrows():
    if row['Qualified']: rank_list.append(curr_rank); curr_rank += 1
    else: rank_list.append("-")
final_df['Rank'] = rank_list

# --- 8. HTML Webpage Generation ---
table_rows = ""
for _, row in final_df.iterrows():
    icon_path, suit_class = get_tier_icon(row['ELO'], row['Games'])
    icon_tag = f'<div class="tier-icon-container"><img src="{icon_path}"></div>' if icon_path else ""
    display_name = str(row['Player']).split('+')[0].split('#')[0]
    table_rows += f"<tr><td>{row['Rank']}</td><td>{icon_tag}</td><td>{display_name}</td><td>{row['ELO']}</td><td>{row['Games']}</td><td>{row['Wins']}</td><td>{row['Win Rate']}</td><td>{row['Peak']}</td><td>{row['Last']}</td></tr>"

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Root League Leaderboard</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/responsive/2.5.0/css/responsive.dataTables.min.css">
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px 5px; }}
        .container {{ width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); }}
        
        nav {{ margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }}
        nav a {{ color: #888; text-decoration: none; font-weight: bold; text-transform: uppercase; font-size: 0.85em; padding: 8px 16px; border-radius: 6px; transition: all 0.3s; }}
        nav a:hover {{ color: #4a90e2; background: rgba(74,144,226,0.05); }}
        nav a.active {{ color: #fff; background: #4a90e2; border: 1px solid #4a90e2; box-shadow: 0 4px 12px rgba(74,144,226,0.3); }}

        .leaderboard-table {{ width: 100% !important; margin-top: 15px; background: #1e1e1e; }}
        .leaderboard-table th {{ background-color: #252525 !important; color: #4a90e2 !important; font-size: 0.75em; text-transform: uppercase; padding: 12px; }}
        .tier-icon-container img {{ height: 24px; }}
        .tier-bird   {{ background: rgba(103, 192, 199, 0.1) !important; border-left: 4px solid #67c0c7 !important; }}
        .tier-fox    {{ background: rgba(230, 55, 45, 0.1) !important; border-left: 4px solid #e6372d !important; }}
        .tier-rabbit {{ background: rgba(247, 235, 91, 0.1) !important; border-left: 4px solid #f7eb5b !important; }}
        .tier-mouse  {{ background: rgba(242, 144, 87, 0.1) !important; border-left: 4px solid #f29057 !important; }}
        .unranked {{ opacity: 0.5; font-style: italic; }}
    </style>
</head>
<body>
    <div class="container">
        <nav><a href="index.html" class="active">Leaderboard</a><a href="matches.html">Match Archive</a><a href="trends.html">Player Trends</a></nav>
        <h1>Root Digital League • Season LH01</h1>
        <h3>Alternative ELO Leaderboard • Data until {CUTOFF_DATE}</h3>
        <table id="leaderboard" class="leaderboard-table display nowrap">
            <thead><tr><th>Rank</th><th>Tier</th><th>Player</th><th>ELO</th><th>Games</th><th>Wins</th><th>Win Rate</th><th>Peak</th><th>Last</th></tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>
    <script>
    $(document).ready(function() {{
        $('#leaderboard').DataTable({{
            "order": [[3, "desc"]], "responsive": true, "pageLength": 50,
            "createdRow": function(row, data, dataIndex) {{
                var elo = parseInt(data[3]);
                if (data[0] === "-") $(row).addClass('unranked');
                else {{
                    if (elo >= 1500) $(row).addClass('tier-bird');
                    else if (elo >= 1400) $(row).addClass('tier-fox');
                    else if (elo >= 1300) $(row).addClass('tier-rabbit');
                    else if (elo >= 1200) $(row).addClass('tier-mouse');
                }}
            }}
        }});
    }});
    </script>
</body></html>
"""
with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

# --- 9. Match Archive Generation ---
df_best_matches = pd.DataFrame(match_history_data).sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
df_best_matches.insert(0, 'Rank', range(1, len(df_best_matches) + 1))

match_rows = ""
for _, row in df_best_matches.iterrows():
    def clean(n): return ", ".join([x.strip().split('+')[0].split('#')[0] for x in str(n).split(',')])
    lineup_html = f'<div style="white-space: normal; min-width: 150px; word-break: break-word;"><span style="color:#f7eb5b; font-weight:bold;">{clean(row["Winner"])}</span>, <span style="color:#888;">{clean(row["Other Players"])}</span></div>'
    match_rows += f"<tr><td>{row['Rank']}</td><td style='font-weight:bold; color:#4a90e2;'>{row['ELO_Sum']}</td><td>{row['Date']}</td><td style='text-align:left;'>{lineup_html}</td><td><a href='https://rootleague.pliskin.dev/match/{row['MatchID']}/' target='_blank' style='color:#666; text-decoration:none; border:1px solid #333; padding:2px 6px; border-radius:4px;'>{row['MatchID']} ↗</a></td></tr>"

matches_html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Match Archive • Root League</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/responsive/2.5.0/css/responsive.dataTables.min.css">
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px 5px; }}
        .container {{ width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 25px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }}
        nav {{ margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }}
        nav a {{ color: #888; text-decoration: none; font-weight: bold; text-transform: uppercase; font-size: 0.85em; padding: 8px 16px; border-radius: 6px; transition: all 0.3s; }}
        nav a.active {{ color: #fff; background: #4a90e2; border: 1px solid #4a90e2; }}
        table.dataTable thead th {{ background-color: #252525 !important; color: #4a90e2 !important; text-transform: uppercase; font-size: 0.75em; }}
        @media (max-width: 600px) {{ 
            table.dataTable td:nth-child(1), table.dataTable th:nth-child(1) {{ display: none; }}
            table.dataTable td {{ font-size: 0.85em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <nav><a href="index.html">Leaderboard</a><a href="matches.html" class="active">Match Archive</a><a href="trends.html">Player Trends</a></nav>
        <h1>Match Archive</h1>
        <table id="matchesTable" class="display nowrap">
            <thead><tr><th>Rank</th><th>ELO Sum</th><th>Date</th><th style="text-align:left;">Lineup</th><th>Game ID</th></tr></thead>
            <tbody>{match_rows}</tbody>
        </table>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>
    <script>
    $(document).ready(function() {{
        $('#matchesTable').DataTable({{
            "order": [[1, "desc"]], "responsive": true, "pageLength": 50,
            "columnDefs": [{{ "responsivePriority": 1, "targets": [1, 3] }}, {{ "responsivePriority": 2, "targets": 2 }}]
        }});
    }});
    </script>
</body></html>
"""
with open("matches.html", "w", encoding="utf-8") as f: f.write(matches_html_content)

# --- 10. Trends Generation ---
clean_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}
history_json = json.dumps(clean_history)
player_names_list = sorted(list(clean_history.keys()))

trends_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Player Progression • Root League</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px; }}
        .container {{ width: 95%; max-width: 1000px; margin: auto; background: #1e1e1e; padding: 30px; border-radius: 12px; }}
        nav {{ margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }}
        nav a {{ color: #888; text-decoration: none; font-weight: bold; text-transform: uppercase; font-size: 0.85em; padding: 8px 16px; border-radius: 6px; }}
        nav a.active {{ color: #fff; background: #4a90e2; border: 1px solid #4a90e2; }}
        input {{ background: #252525; color: #fff; border: 1px solid #444; padding: 12px; border-radius: 6px; width: 100%; max-width: 350px; }}
        .chart-container {{ height: 450px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <nav><a href="index.html">Leaderboard</a><a href="matches.html">Match Archive</a><a href="trends.html" class="active">Player Trends</a></nav>
        <h1>Player Progression</h1>
        <input list="playerList" id="playerName" placeholder="Search for a player..." oninput="updateChart()">
        <datalist id="playerList">{''.join([f'<option value="{name}">' for name in player_names_list])}</datalist>
        <div class="chart-container"><canvas id="progressionChart"></canvas></div>
    </div>
    <script>
        const allData = {history_json}; let myChart;
        function updateChart() {{
            const name = document.getElementById('playerName').value;
            if (allData[name]) {{
                const ctx = document.getElementById('progressionChart').getContext('2d');
                if (myChart) myChart.destroy();
                myChart = new Chart(ctx, {{
                    type: 'line',
                    data: {{ labels: allData[name].map(d=>d[0]), datasets: [{{ label: name, data: allData[name].map(d=>d[1]), borderColor: '#4a90e2', fill: true, tension: 0.2 }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false }}
                }});
            }}
        }}
    </script>
</body></html>
"""
with open("trends.html", "w", encoding="utf-8") as f: f.write(trends_html)
