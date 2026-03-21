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

# --- 4. Fetch Match Data from API ---
all_matches = []
next_page_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

while next_page_url:
    try:
        response = requests.get(next_page_url, headers=HEADERS)
        response.raise_for_status()
        page_data = response.json()
        all_matches.extend(page_data.get('results', []))
        next_page_url = page_data.get('next')
    except Exception as e:
        print(f"API Error: {e}")
        break

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
            print(f"Corrected {mask.sum() // 4} games while preserving original times.")
except Exception as e:
    print(f"Date mapping note: {e}")

df = df[df['Date_Closed'].dt.date < today].copy()
df = df.sort_values(by='Date_Closed').reset_index(drop=True)

# --- 6. ELO Calculation Logic ---
elo_ratings = {player: 1200 for player in df['Player'].unique()}
peak_elo = {player: 1200 for player in df['Player'].unique()}
last_diff = {player: 0 for player in df['Player'].unique()}
player_stats = {player: {'games': 0, 'wins': 0.0} for player in df['Player'].unique()}

for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    if len(match_participants) != 4: continue
    
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

# --- 7. Final Leaderboard Preparation ---
def get_tier_icon(rating, games):
    if games < 10: return ""
    if rating >= 1500: return "🦅"
    if rating >= 1400: return "🦊"
    if rating >= 1300: return "🐰"
    if rating >= 1200: return "🐭"
    return ""

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
            '+/-': str_diff,
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
final_df = final_df[['Rank', 'Tier', 'Player', 'ELO', 'Games', 'Wins', 'Win Rate', 'Peak', '+/-']]

# --- 8. HTML Webpage Generation ---
html_table = final_df.to_html(index=False, classes='leaderboard-table display nowrap', table_id="leaderboard")

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

        /* DataTables Styling */
        .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, 
        .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_paginate {{ color: #aaa !important; font-size: 0.8em; }}
        input {{ background-color: #333 !important; color: white !important; border: 1px solid #444 !important; border-radius: 4px; padding: 4px; }}
        .leaderboard-table {{ width: 100% !important; border-collapse: collapse; margin-top: 15px; background: #1e1e1e; }}
        .leaderboard-table th {{ background-color: #252525 !important; color: #4a90e2 !important; font-size: 0.75em; text-transform: uppercase; padding: 12px; }}
        .leaderboard-table td {{ border-bottom: 1px solid #2a2a2a; padding: 10px; font-size: 0.9em; text-align: center; }}

        /* Tier Styling */
        .bird   {{ background-color: rgba(255, 215, 0, 0.15) !important; border-left: 5px solid #ffd700 !important; }}
        .tier-fox   {{ background-color: rgba(255, 102, 0, 0.15) !important; border-left: 5px solid #ff6600 !important; }}
        .rabbit  {{ background-color: rgba(205, 127, 50, 0.15) !important; border-left: 5px solid #cd7f32 !important; }}
        .tier-mouse {{ background-color: rgba(74, 144, 226, 0.15) !important; border-left: 5px solid #4a90e2 !important; }}
        
        /* Colored Text for Rank 3/4 (Player/ELO) */
        .bird td:nth-child(3), .bird td:nth-child(4)   {{ color: #ffd700; font-weight: bold; }}
        .tier-fox td:nth-child(3), .tier-fox td:nth-child(4)   {{ color: #ff8533; font-weight: bold; }}
        .rabbit td:nth-child(3), .rabbit td:nth-child(4) {{ color: #dfa679; font-weight: bold; }}
        .tier-mouse td:nth-child(3), .tier-mouse td:nth-child(4) {{ color: #7db3f2; font-weight: bold; }}

        /* Secondary columns styling (Peak & +/-) */
        .leaderboard-table td:nth-child(8), .leaderboard-table td:nth-child(9) {{ color: #888; font-size: 0.85em; }}

        .unranked {{ opacity: 0.5; font-style: italic; }}
        .unranked td {{ color: #888 !important; }}

        @media (max-width: 600px) {{
            h1 {{ font-size: 1.2em; }}
            .container {{ padding: 10px; }}
        }}
        .footer {{ margin-top: 30px; font-size: 0.7em; color: #555; line-height: 1.5; border-top: 1px solid #333; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Root Digital League</h1>
        <h3>Official Rankings • Data until {CUTOFF_DATE}</h3>
        {html_table}
        <div class="footer">
            <strong>Qualification:</strong> 10+ games & 1200+ Elo.<br>
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
                {{ "type": "rank", "targets": 0 }},
                {{ "responsivePriority": 1, "targets": [0, 2, 3] }},
                {{ "responsivePriority": 10, "targets": [1, 4, 5, 6, 7, 8] }},
                {{ "className": "all", "targets": [0, 2, 3] }}
            ],
            "createdRow": function(row, data, dataIndex) {{
                var rank = data[0];         
                var elo = parseInt(data[3]); 
                if (rank === "-") {{
                    $(row).addClass('unranked');
                }} else {{
                    if (elo >= 1500) $(row).addClass('bird');
                    else if (elo >= 1400) $(row).addClass('tier-fox');
                    else if (elo >= 1300) $(row).addClass('rabbit');
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
print("index.html generated successfully!")
