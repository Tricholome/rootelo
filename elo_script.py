import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone

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

# This fixes the NameError 'raw_data'
raw_data = [] 
for m in all_matches:
    participants = m.get('participants', [])
    if len(participants) == 4:
        for p in participants:
            raw_data.append({
                'GameID': m['id'],
                'Player': p.get('player'),
                # We use 'Score' here; ensure your Step 6 uses p['Score']
                'Score': float(p.get('tournament_score', 0.0)), 
                'Date_Closed': m.get('date_closed')
            })

# --- 5. Data Processing (Time-Preservation Fix) ---
df = pd.DataFrame(raw_data)
df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

# This preserves the original HH:MM:SS from the API so the Elo order stays identical
try:
    if not game_id_mapping.empty:
        mask = df['GameID'].isin(game_id_mapping.index)
        if mask.any():
            # 1. Get original times (e.g. 14:30:05)
            original_times = df.loc[mask, 'Date_Closed'].dt.strftime('%H:%M:%S.%f')
            # 2. Get new dates from Excel (e.g. 2024-03-20)
            new_dates = df.loc[mask, 'GameID'].map(game_id_mapping).dt.strftime('%Y-%m-%d')
            # 3. Combine them
            combined_datetimes = new_dates + ' ' + original_times
            df.loc[mask, 'Date_Closed'] = pd.to_datetime(combined_datetimes, utc=True)
            print(f"Corrected {mask.sum() // 4} games while preserving original timestamps.")
except Exception as e:
    print(f"Date mapping note: {e}")

# Filter for yesterday's data
df = df[df['Date_Closed'].dt.date < today].copy()

# Sort by the new combined date/time to ensure Elo chain reaction is correct
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
        
        if elo_ratings[name] > peak_elo[name]:
            peak_elo[name] = elo_ratings[name]

        player_history[p['Player']].append([current_date, round(elo_ratings[p['Player']])])

# --- 7. Final Leaderboard Preparation ---
def get_tier_icon(rating, games):
    if games < 10:
        return None, "unranked"
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
        
        # Formatting Wins: Remove .0, keep .5
        formatted_wins = int(w) if w % 1 == 0 else round(w, 1)
        
        diff = round(last_diff[p_name])
        str_diff = f"+{diff}" if diff > 0 else str(diff)

        leaderboard_results.append({
            'Rank': 0,
            'Tier': get_tier_icon(rating, g),
            'Player': p_name,
            'ELO': round(rating),
            'Games': g,
            'Wins': formatted_wins,
            'Win Rate': f"{(w/g):.1%}",
            'Peak': round(peak_elo[p_name]),
            'Last': str_diff,
            'Qualified': is_qual
        })

final_df = pd.DataFrame(leaderboard_results).sort_values(by='ELO', ascending=False)
curr_rank = 1
rank_list = []
for _, row in final_df.iterrows():
    if row['Qualified']:
        rank_list.append(curr_rank)
        curr_rank += 1
    else:
        rank_list.append("-")

final_df['Rank'] = rank_list
final_df = final_df.drop(columns=['Qualified'])

# Set strict Column Order
final_df = final_df[['Rank', 'Tier', 'Player', 'ELO', 'Games', 'Wins', 'Win Rate', 'Peak', 'Last']]

# --- 8. HTML Webpage Generation ---

table_rows = ""
for _, row in final_df.iterrows():
    icon_path, suit_class = get_tier_icon(row['ELO'], row['Games'])
    icon_tag = f'<div class="tier-icon-container"><img src="{icon_path}"></div>' if icon_path else ""
    display_name = str(row['Player']).split('+')[0].split('#')[0]
    table_rows += f"""
    <tr>
        <td>{row['Rank']}</td>
        <td>{icon_tag}</td>
        <td class="player-name-cell">{display_name}</td>
        <td>{row['ELO']}</td>
        <td>{row['Games']}</td>
        <td>{row['Wins']}</td>
        <td>{row['Win Rate']}</td>
        <td>{row['Peak']}</td>
        <td>{row['Last']}</td>
    </tr>"""

html_table = f"""
<table id="leaderboard" class="leaderboard-table display nowrap">
    <thead>
        <tr>
            <th>Rank</th>
            <th>Tier</th>
            <th>Player</th>
            <th>ELO</th>
            <th>Games</th>
            <th>Wins</th>
            <th>Win Rate</th>
            <th>Peak</th>
            <th>Last</th>
        </tr>
    </thead>
    <tbody>
        {table_rows}
    </tbody>
</table>"""

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Root League Leaderboard</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/responsive/2.5.0/css/responsive.dataTables.min.css">
    <style>
        body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px 5px; }}
        .container {{ width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); }}
        h1 {{ color: #4a90e2; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; font-size: 1.5em; }}
        h3 {{ color: #777; font-weight: 400; font-size: 0.85em; margin-bottom: 20px; }}

        /* Unified Navigation CSS */
        nav {{ 
            margin-bottom: 30px; 
            border-bottom: 1px solid #333; 
            padding-bottom: 15px; 
            display: flex; 
            justify-content: center; 
            gap: 10px;
            flex-wrap: wrap; 
        }}
        nav a {{ 
            color: #888; 
            text-decoration: none; 
            font-weight: bold; 
            text-transform: uppercase; 
            font-size: 0.85em; 
            padding: 8px 16px;
            border-radius: 6px;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }}
        nav a:hover {{ color: #4a90e2; background: rgba(74,144,226,0.05); }}
        nav a.active {{ color: #fff; background: #4a90e2; border: 1px solid #4a90e2; box-shadow: 0 4px 12px rgba(74,144,226,0.3); }}

        .leaderboard-table {{ width: 100% !important; border-collapse: collapse; margin-top: 15px; background: #1e1e1e; }}
        .leaderboard-table th {{ background-color: #252525 !important; color: #4a90e2 !important; font-size: 0.75em; text-transform: uppercase; padding: 12px; }}
        .leaderboard-table td {{ border-bottom: 1px solid #2a2a2a; padding: 10px; font-size: 0.9em; text-align: center; vertical-align: middle; }}

        .tier-icon-container {{ width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; margin: 0 auto; }}
        .tier-icon-container img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}

        .tier-bird   {{ background-color: rgba(103, 192, 199, 0.1) !important; border-left: 4px solid #67c0c7 !important; }}
        .tier-fox    {{ background-color: rgba(230, 55, 45, 0.1) !important; border-left: 4px solid #e6372d !important; }}
        .tier-rabbit {{ background-color: rgba(247, 235, 91, 0.1) !important; border-left: 4px solid #f7eb5b !important; }}
        .tier-mouse  {{ background-color: rgba(242, 144, 87, 0.1) !important; border-left: 4px solid #f29057 !important; }}
        
        .tier-bird td:nth-child(3), .tier-bird td:nth-child(4)   {{ color: #67c0c7; font-weight: bold; }}
        .tier-fox td:nth-child(3), .tier-fox td:nth-child(4)     {{ color: #e6372d; font-weight: bold; }}
        .tier-rabbit td:nth-child(3), .tier-rabbit td:nth-child(4) {{ color: #f7eb5b; font-weight: bold; }}
        .tier-mouse td:nth-child(3), .tier-mouse td:nth-child(4)  {{ color: #f29057; font-weight: bold; }}

        .unranked {{ opacity: 0.5; font-style: italic; }}
        .footer {{ margin-top: 30px; font-size: 0.75em; color: #777; border-top: 1px solid #333; padding-top: 15px; line-height: 2; }}
        .footer-tier-item {{ display: inline-block; margin: 0 10px; vertical-align: middle; }}
        .footer-tier-item img {{ height: 18px; width: auto; vertical-align: middle; margin-right: 4px; }}
        .player-name-cell {{
            text-align: left !important; 
            padding-left: 15px !important; 
            font-weight: 500; 
        }}
    </style>
</head>
<body>
    <div class="container">
        <nav>
            <a href="index.html" class="active">Leaderboard</a>
            <a href="matches.html">Match Archive</a>
            <a href="trends.html">Player Trends</a>
        </nav>
        <h1>Root Digital League • Season LH01</h1>
        <h3>Alternative ELO Leaderboard • Data until {CUTOFF_DATE}</h3>
        {html_table}
        <div class="footer">
            <strong>Tier System</strong> (min 10 games):<br>
            <span class="footer-tier-item"><img src="assets/icons/bird.png"> 1500+</span>
            <span class="footer-tier-item"><img src="assets/icons/fox.png"> 1400+</span>
            <span class="footer-tier-item"><img src="assets/icons/rabbit.png"> 1300+</span>
            <span class="footer-tier-item"><img src="assets/icons/mouse.png"> 1200+</span>
            <br>
            Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
        </div>
    </div>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>
    <script>
    $(document).ready(function() {{
        $.extend($.fn.dataTable.ext.type.order, {{
            "rank-pre": function (d) {{ return d === "-" ? 9999 : parseInt(d); }}
        }});

        $('#leaderboard').DataTable({{
            "order": [[3, "desc"]],
            "responsive": true,
            "pageLength": 50,
            "columnDefs": [
                {{ "targets": 2, "className": "player-name-cell" }}, // Target index 2 (Player column)
                {{ "responsivePriority": 1, "targets": [0, 2, 3] }}
            ],
            "createdRow": function(row, data, dataIndex) {{
                var rank = data[0];         
                var elo = parseInt(data[3]); 
                if (rank === "-") {{
                    $(row).addClass('unranked');
                }} else {{
                    if (elo >= 1500) $(row).addClass('tier-bird');
                    else if (elo >= 1400) $(row).addClass('tier-fox');
                    else if (elo >= 1300) $(row).addClass('tier-rabbit');
                    else if (elo >= 1200) $(row).addClass('tier-mouse');
                }}
            }}
        }});
    }});
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
    
# --- 9. Best Matches Calculation ---

df_best_matches = pd.DataFrame(match_history_data)
df_best_matches = df_best_matches.sort_values(by='ELO_Sum', ascending=False).reset_index(drop=True)
df_best_matches.insert(0, 'Rank', range(1, len(df_best_matches) + 1))

# --- 10. Generate matches.html (Searchable Archive with Links) ---

match_rows = ""
for _, row in df_best_matches.iterrows():
    # Helper to clean names: Removes everything after + or #
    def clean_names(name_str):
        if not name_str: return ""
        names = [n.strip().split('+')[0].split('#')[0] for n in name_str.split(',')]
        return ", ".join(names)

    cleaned_winner = clean_names(row["Winner"])
    cleaned_others = clean_names(row["Other Players"])

    # Color-coded participants
    winner_html = f'<span style="color: #f7eb5b; font-weight: bold;">{cleaned_winner}</span>'
    others_html = f'<span style="color: #888;">{cleaned_others}</span>'
    lineup_html = f'<div style="white-space: normal; word-break: break-word; min-width: 150px;">{winner_html}, {others_html}</div>'
    
    # Create the link to the official website
    match_url = f"https://rootleague.pliskin.dev/match/{row['MatchID']}/"
    
    match_rows += f"""
    <tr>
        <td>{row['Rank']}</td>
        <td style="font-weight:bold; color:#4a90e2;">{row['ELO_Sum']}</td>
        <td>{row['Date']}</td>
        <td style="text-align: left; padding-left: 20px;">{lineup_html}</td>
        <td>
            <a href="{match_url}" target="_blank" style="color: #666; text-decoration: none; font-family: monospace; font-size: 0.9em; border: 1px solid #333; padding: 2px 6px; border-radius: 4px; transition: 0.3s;">
                {row['MatchID']} ↗
            </a>
        </td>
    </tr>"""

matches_html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Match Archive • Root League</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/responsive/2.5.0/css/responsive.dataTables.min.css">
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px 5px; }}
        .container {{ width: 95%; max-width: 1100px; margin: auto; background: #1e1e1e; padding: 15px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); overflow: hidden; }}
        
        /* Unified Navigation */
        nav {{ margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }}
        nav a {{ color: #888; text-decoration: none; font-weight: bold; text-transform: uppercase; font-size: 0.8em; padding: 8px 12px; border-radius: 6px; transition: 0.3s; border: 1px solid transparent; }}
        nav a:hover {{ color: #4a90e2; background: rgba(74,144,226,0.05); }}
        nav a.active {{ color: #fff; background: #4a90e2; border: 1px solid #4a90e2; }}
        
        h1 {{ color: #4a90e2; text-transform: uppercase; letter-spacing: 1px; font-size: 1.4em; margin-bottom: 10px; }}
        
        /* Table Tweaks */
        .dataTables_wrapper {{ color: #eee !important; }}
        table.dataTable {{ width: 100% !important; margin-top: 10px !important; background: #1e1e1e; border-collapse: collapse !important; }}
        table.dataTable thead th {{ background-color: #252525 !important; color: #4a90e2 !important; font-size: 0.7em; padding: 10px 5px !important; text-transform: uppercase; }}
        table.dataTable td {{ border-bottom: 1px solid #2a2a2a; padding: 10px 5px; font-size: 0.85em; vertical-align: middle; }}

        /* The Lineup Fix: Force wrapping and prevent overflow */
        .lineup-cell {{ 
            white-space: normal !important; 
            word-wrap: break-word; 
            overflow-wrap: break-word; 
            min-width: 120px; 
            max-width: 250px; 
            line-height: 1.4;
            text-align: left;
        }}

        /* Responsive Child Row Styling (The "Details" view) */
        table.dataTable.dtr-inline.collapsed > tbody > tr > td.dtr-control:before {{
            background-color: #4a90e2 !important; /* Make the + button blue */
        }}
        table.dataTable > tbody > tr.child ul.dtr-details {{ width: 100%; background: #252525; }}
        table.dataTable > tbody > tr.child span.dtr-title {{ color: #4a90e2; font-weight: bold; }}

        @media (max-width: 600px) {{
            .container {{ padding: 10px; }}
            .dataTables_filter input {{ width: 150px !important; }}
            table.dataTable td {{ font-size: 0.75em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <nav>
            <a href="index.html">Leaderboard</a>
            <a href="matches.html" class="active">Match Archive</a>
            <a href="trends.html">Player Trends</a>
        </nav>
        
        <h1>Match Archive</h1>

        <table id="matchesTable" class="display nowrap responsive" style="width:100%">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>ELO</th>
                    <th>Date</th>
                    <th>Lineup (Winner First)</th>
                    <th>ID</th>
                </tr>
            </thead>
            <tbody>
                {match_rows}
            </tbody>
        </table>
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>
    <script>
    $(document).ready(function() {{
        $('#matchesTable').DataTable({{
            "order": [[1, "desc"]], 
            "responsive": {{
                details: {{
                    type: 'column',
                    target: 0 // Clicking the "Rank" column will now expand the details
                }}
            }},
            "pageLength": 25,
            "columnDefs": [
                {{ "className": "dtr-control", "targets": 0 }}, // Adds the plus icon to Rank
                {{ "width": "40px", "targets": [0, 1] }},      // Force Rank and ELO to stay small
                {{ "className": "lineup-cell", "targets": 3 }}, // Apply the wrapping fix to Lineup
                {{ "responsivePriority": 1, "targets": [1, 3] }}, // Always show ELO and Lineup
                {{ "responsivePriority": 2, "targets": 2 }},      // Date next
                {{ "responsivePriority": 3, "targets": 4 }}       // Game ID hides first
            ]
        }});
    }});
    </script>
</body>
</html>
"""
with open("matches.html", "w", encoding="utf-8") as f:
    f.write(matches_html_content)

# --- 11. Prepare Trends Data ---
import json
# Clean names and prepare JSON
clean_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}
history_json = json.dumps(clean_history)

# Create a list of player names for the autocomplete dropdown
player_names_list = sorted(list(clean_history.keys()))

# --- 12. Generate trends.html ---
trends_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Player Progression • Root League</title>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 20px; }}
        .container {{ width: 95%; max-width: 1000px; margin: auto; background: #1e1e1e; padding: 30px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }}
        
        /* Unified Navigation CSS */
        nav {{ 
            margin-bottom: 30px; 
            border-bottom: 1px solid #333; 
            padding-bottom: 15px; 
            display: flex; 
            justify-content: center; 
            gap: 10px;
            flex-wrap: wrap; 
        }}
        nav a {{ 
            color: #888; 
            text-decoration: none; 
            font-weight: bold; 
            text-transform: uppercase; 
            font-size: 0.85em; 
            padding: 8px 16px;
            border-radius: 6px;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }}
        nav a:hover {{ color: #4a90e2; background: rgba(74,144,226,0.05); }}
        nav a.active {{ color: #fff; background: #4a90e2; border: 1px solid #4a90e2; box-shadow: 0 4px 12px rgba(74,144,226,0.3); }}

        h1 {{ color: #4a90e2; margin-bottom: 10px; }}
        
        .search-box {{ margin: 20px 0; }}
        input {{ background: #252525; color: #fff; border: 1px solid #444; padding: 12px; border-radius: 6px; width: 350px; font-size: 1em; outline: none; }}
        input:focus {{ border-color: #4a90e2; }}
        
        .chart-container {{ position: relative; height: 500px; width: 100%; margin-top: 30px; background: #1a1a1a; padding: 15px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <nav>
            <a href="index.html">Leaderboard</a>
            <a href="matches.html">Match Archive</a>
            <a href="trends.html" class="active">Player Trends</a>
        </nav>

        <h1>Player Progression</h1>
        <p style="color: #888;">Select a player to visualize their ELO journey across dates.</p>
        
        <div class="search-box">
            <input list="playerList" id="playerName" placeholder="Search for a player..." oninput="updateChart()">
            <datalist id="playerList">
                {''.join([f'<option value="{name}">' for name in player_names_list])}
            </datalist>
        </div>
        
        <div class="chart-container">
            <canvas id="progressionChart"></canvas>
        </div>
    </div>

    <script>
        const allData = {history_json};
        let myChart;

        function updateChart() {{
            const name = document.getElementById('playerName').value;
            const ctx = document.getElementById('progressionChart').getContext('2d');
            
            if (allData[name]) {{
                const rawData = allData[name]; // Array of [Date, ELO]
                const labels = rawData.map(d => d[0]);
                const eloScores = rawData.map(d => d[1]);

                if (myChart) myChart.destroy();

                myChart = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: name + ' ELO Journey',
                            data: eloScores,
                            borderColor: '#4a90e2',
                            backgroundColor: 'rgba(74, 144, 226, 0.1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.2,
                            pointRadius: 3,
                            pointHoverRadius: 10,
                            pointHitRadius: 20
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {{ intersect: false, mode: 'index' }},
                        scales: {{
                            y: {{ 
                                grid: {{ color: '#333' }}, 
                                ticks: {{ color: '#aaa' }},
                                title: {{ display: true, text: 'ELO Rating', color: '#777' }}
                            }},
                            x: {{ 
                                grid: {{ display: false }}, 
                                ticks: {{ color: '#aaa', maxRotation: 45, minRotation: 45 }} 
                            }}
                        }},
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{
                                backgroundColor: '#252525',
                                titleColor: '#4a90e2',
                                bodyColor: '#fff',
                                borderColor: '#444',
                                borderWidth: 1,
                                displayColors: false
                            }}
                        }}
                    }}
                }});
            }}
        }}
    </script>
</body>
</html>
"""

with open("trends.html", "w", encoding="utf-8") as f:
    f.write(trends_html)
