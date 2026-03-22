import os
import requests
import pandas as pd
import json
from datetime import datetime, timedelta, date, timezone

# --- 1. Configuration (GitHub Secrets) ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24

# --- 2. Date Setup ---
today = date.today()
CUTOFF_DATE = today - timedelta(days=1)
print(f"Update started. Data until: {CUTOFF_DATE}")

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

# --- 4. Fetch Match Data ---
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

# --- 5. Data Processing ---
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
            print(f"Corrected {mask.sum() // 4} games.")
except Exception as e:
    print(f"Date mapping note: {e}")

df = df[df['Date_Closed'].dt.date < today].copy()
df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# --- 6. ELO Calculation Logic (The "Memorizer") ---
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
    current_date = pd.to_datetime(match_participants[0]['Date_Closed']).strftime('%Y-%m-%d')
    
    solo_winners = [p['Player'] for p in match_participants if p['Score'] == 1.0]
    co_winners = [p['Player'] for p in match_participants if p['Score'] == 0.5]
    others = [p['Player'] for p in match_participants if p['Score'] == 0.0]
    
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
        
        k = 80 if player_stats[name]['games'] <= 10 else (40 if player_stats[name]['games'] <= 50 else 20)
            
        change = k * (actual - expected)
        elo_ratings[name] += change
        last_diff[name] = change
        if elo_ratings[name] > peak_elo[name]: peak_elo[name] = elo_ratings[name]
        
        # Save [Date, ELO] for Trends
        player_history[name].append([current_date, round(elo_ratings[name])])

# --- 7. Final Leaderboard Prep ---
def get_tier_icon(rating, games):
    if games < 10: return None, "unranked"
    r = round(rating)
    if r >= 1500: return "assets/icons/bird.png", "tier-bird"
    if r >= 1400: return "assets/icons/fox.png", "tier-fox"
    if r >= 1300: return "assets/icons/rabbit.png", "tier-rabbit"
    if r >= 1200: return "assets/icons/mouse.png", "tier-mouse"
    return None, "unranked"

leaderboard_results = []
for p_name, rating in elo_ratings.items():
    g = player_stats[p_name]['games']
    w = player_stats[p_name]['wins']
    if w >= 1:
        formatted_wins = int(w) if w % 1 == 0 else round(w, 1)
        diff = round(last_diff[p_name])
        leaderboard_results.append({
            'Rank': 0, 'Player': p_name, 'ELO': round(rating), 'Games': g,
            'Wins': formatted_wins, 'Win Rate': f"{(w/g):.1%}",
            'Peak': round(peak_elo[p_name]), 'Last': f"+{diff}" if diff > 0 else str(diff),
            'Qualified': (g >= 10 and rating >= 1200)
        })

final_df = pd.DataFrame(leaderboard_results).sort_values(by='ELO', ascending=False)
curr_rank = 1
ranks = []
for _, row in final_df.iterrows():
    if row['Qualified']:
        ranks.append(curr_rank); curr_rank += 1
    else: ranks.append("-")
final_df['Rank'] = ranks

# --- 8. HTML: index.html ---
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
    <meta charset="UTF-8">
    <title>Root League Leaderboard</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <style>
        body {{ font-family: sans-serif; background: #121212; color: #eee; text-align: center; }}
        .container {{ width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; }}
        nav {{ margin-bottom: 20px; border-bottom: 1px solid #333; padding: 10px; }}
        nav a {{ color: #4a90e2; text-decoration: none; margin: 0 15px; font-weight: bold; }}
        table {{ width: 100% !important; background: #1e1e1e; color: #eee; }}
        .tier-icon-container img {{ height: 24px; }}
        .unranked {{ opacity: 0.5; }}
    </style>
</head>
<body>
    <div class="container">
        <nav><a href="index.html" style="border-bottom: 2px solid #4a90e2;">Leaderboard</a><a href="matches.html">Match Archive</a><a href="trends.html">Player Trends</a></nav>
        <h1>Root Digital League Leaderboard</h1>
        <table id="leaderboard">
            <thead><tr><th>Rank</th><th>Tier</th><th>Player</th><th>ELO</th><th>Games</th><th>Wins</th><th>WR</th><th>Peak</th><th>Last</th></tr></thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script>$(document).ready(function() {{ $('#leaderboard').DataTable({{"order": [[3, "desc"]], "pageLength": 50}}); }});</script>
</body>
</html>
"""
with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

# --- 9. HTML: matches.html ---
df_matches = pd.DataFrame(match_history_data).sort_values(by='ELO_Sum', ascending=False)
df_matches.insert(0, 'Rank', range(1, len(df_matches) + 1))

match_rows = ""
for _, row in df_matches.iterrows():
    def clean(n): return ", ".join([x.strip().split('+')[0].split('#')[0] for x in n.split(',')])
    lineup = f'<span style="color:#f7eb5b;font-weight:bold;">{clean(row["Winner"])}</span>, <span style="color:#888;">{clean(row["Other Players"])}</span>'
    match_rows += f"<tr><td>{row['Rank']}</td><td style='color:#4a90e2;font-weight:bold;'>{row['ELO_Sum']}</td><td>{row['Date']}</td><td style='text-align:left;'>{lineup}</td><td><a href='https://rootleague.pliskin.dev/match/{row['MatchID']}/' target='_blank' style='color:#666;'>{row['MatchID']} ↗</a></td></tr>"

matches_html = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Match Archive</title><link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"><style>body{{background:#121212;color:#eee;font-family:sans-serif;}} .container{{width:95%;max-width:1100px;margin:auto;background:#1e1e1e;padding:20px;border-radius:12px;}} nav{{margin-bottom:20px;border-bottom:1px solid #333;padding:10px;}} nav a{{color:#4a90e2;text-decoration:none;margin:0 15px;font-weight:bold;}} table{{width:100% !important;}}</style></head>
<body>
    <div class="container">
        <nav><a href="index.html">Leaderboard</a><a href="matches.html" style="border-bottom: 2px solid #4a90e2;">Match Archive</a><a href="trends.html">Player Trends</a></nav>
        <h1>Match Archive</h1>
        <table id="mTable"><thead><tr><th>Rank</th><th>ELO Sum</th><th>Date</th><th style='text-align:left;'>Lineup</th><th>ID</th></tr></thead><tbody>{match_rows}</tbody></table>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script>$(document).ready(function() {{ $('#mTable').DataTable({{"order": [[1, "desc"]], "pageLength": 50}}); }});</script>
</body></html>
"""
with open("matches.html", "w", encoding="utf-8") as f: f.write(matches_html)

# --- 11. HTML: trends.html ---
clean_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}
history_json = json.dumps(clean_history)
p_names = sorted(list(clean_history.keys()))

trends_html = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Trends</title><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><style>body{{background:#121212;color:#eee;font-family:sans-serif;}} .container{{width:95%;max-width:900px;margin:auto;background:#1e1e1e;padding:30px;border-radius:12px;}} nav{{margin-bottom:20px;border-bottom:1px solid #333;padding:10px;}} nav a{{color:#4a90e2;text-decoration:none;margin:0 15px;font-weight:bold;}} input{{background:#252525;color:#fff;padding:10px;width:300px;}}</style></head>
<body>
    <div class="container">
        <nav><a href="index.html">Leaderboard</a><a href="matches.html">Match Archive</a><a href="trends.html" style="border-bottom: 2px solid #4a90e2;">Player Trends</a></nav>
        <h1>Player Progression</h1>
        <input list="pList" id="pName" placeholder="Search Player..." oninput="updateChart()"><datalist id="pList">{''.join([f'<option value="{n}">' for n in p_names])}</datalist>
        <div style="height:400px; margin-top:20px;"><canvas id="pChart"></canvas></div>
    </div>
    <script>
        const allData = {history_json}; let chart;
        function updateChart() {{
            const name = document.getElementById('pName').value;
            if (allData[name]) {{
                const ctx = document.getElementById('pChart').getContext('2d');
                if (chart) chart.destroy();
                chart = new Chart(ctx, {{
                    type: 'line',
                    data: {{ labels: allData[name].map(d=>d[0]), datasets: [{{ label: name, data: allData[name].map(d=>d[1]), borderColor: '#4a90e2', tension:0.2 }}] }},
                    options: {{ responsive:true, maintainAspectRatio:false, scales:{{ y:{{ grid:{{color:'#333'}}}} }} }}
                }});
            }}
        }}
    </script>
</body></html>
"""
with open("trends.html", "w", encoding="utf-8") as f: f.write(trends_html)
