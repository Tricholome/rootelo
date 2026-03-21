import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date, timezone

# --- 1. Configuration (Fetch secrets from GitHub Actions) ---
API_TOKEN = os.getenv('API_TOKEN')
HEADERS = {'Authorization': f'Token {API_TOKEN}'} if API_TOKEN else {}
TOURNAMENT_ID = 24

# --- 2. Dynamic Date Setup ---
# 'today' represents 00:00:00 of the current day
today = date.today()
# 'CUTOFF_DATE' is yesterday, used for the website display
CUTOFF_DATE = today - timedelta(days=1)

print(f"Update started. Filtering matches closed before: {today}")

# --- 3. Load Correction File (Excel) ---
excel_file_path = 'Root_Elo_LH01_Corrected_Dates.xlsx'

# Initialize an empty mapping first to avoid NameError
game_id_mapping = pd.Series(dtype='datetime64[ns]')

try:
    if os.path.exists(excel_file_path):
        df_updates = pd.read_excel(excel_file_path, engine='openpyxl')
        if not df_updates.empty and 'GameID' in df_updates.columns:
            # Populate the mapping if the file is valid
            game_id_mapping = df_updates.set_index('GameID')['New_Date']
            print(f"Loaded {len(game_id_mapping)} manual corrections from Excel.")
    else:
        print(f"Note: {excel_file_path} not found. Skipping manual corrections.")
except Exception as e:
    print(f"Warning: Could not process Excel file: {e}. Proceeding without corrections.")

# --- 4. Fetch Match Data from API ---
all_matches = []
# Initial URL for the tournament matches
next_page_url = f"https://rootleague.pliskin.dev/api/match/?format=json&limit=500&tournament={TOURNAMENT_ID}"

while next_page_url:
    try:
        response = requests.get(next_page_url, headers=HEADERS)
        response.raise_for_status()
        page_data = response.json()
        all_matches.extend(page_data.get('results', []))
        # API returns 'next' URL if more pages exist, else None
        next_page_url = page_data.get('next')
    except Exception as e:
        print(f"API Error occurred: {e}")
        break

# --- 5. Data Processing & Date Alignment (with Cutoff) ---
raw_data = []
for match in all_matches:
    participants = match.get('participants', [])
    # We only process standard 4-player games
    if len(participants) == 4:
        for p in participants:
            raw_data.append({
                'GameID': match['id'],
                'Player': p.get('player'),
                'Score': float(p.get('tournament_score', 0.0)),
                'Date_Closed': match.get('date_closed')
            })

df = pd.DataFrame(raw_data)

# Convert API dates to datetime (ISO8601)
df['Date_Closed'] = pd.to_datetime(df['Date_Closed'], format='ISO8601', utc=True)

# Apply manual date corrections from the Excel file
# (game_id_mapping is already defined in the configuration part)
mask = df['GameID'].isin(game_id_mapping.index)
if mask.any():
    df.loc[mask, 'Date_Closed'] = pd.to_datetime(df.loc[mask, 'GameID'].map(game_id_mapping), utc=True)

# We only keep matches where the Date_Closed is strictly before today (00:00:00 UTC)
# This ensures that games played today don't affect the leaderboard until tomorrow.
df = df[df['Date_Closed'].dt.date < today].copy()

# Sort the entire history by date to ensure ELO is calculated chronologically
df = df.sort_values(by='Date_Closed').reset_index(drop=True)

print(f"Final dataset: {len(df)//4} matches confirmed before {today}")

# --- 6. ELO Calculation Logic (Updated) ---
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
        
        # Calculate K-factor
        player_stats[name]['games'] += 1
        player_stats[name]['wins'] += actual
        if player_stats[name]['games'] <= 10: k = 80
        elif player_stats[name]['games'] <= 50: k = 40
        else: k = 20
            
        change = k * (actual - expected)
        elo_ratings[name] += change
        last_diff[name] = change # Keep track of the last delta
        
        # Update Peak ELO
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
        
        # Formatting Last Change: Add + or - sign
        diff = round(last_diff[p_name])
        str_diff = f"+{diff}" if diff > 0 else f"{diff}"
        if diff == 0: str_diff = "0"

        leaderboard_results.append({
            'Rank': 0,
            'Tier': get_tier_icon(rating, g),
            'Player': p_name,
            'ELO': round(rating),
            'Peak': round(peak_elo[p_name]),
            '+/-': str_diff,
            'Games': g,
            'Wins': formatted_wins,
            'Win Rate': f"{(w/g):.1%}", # 1 decimal
            'Qualified': is_qual
        })

# Sort by ELO and Assign Rank
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

# Drop 'Qualified' column so it doesn't show in HTML
final_df = final_df.drop(columns=['Qualified'])

# --- 8. HTML Webpage Generation with DataTables & Mobile Support ---
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
    .container {{ width: 95%; max-width: 1000px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); }}
    
    h1 {{ color: #4a90e2; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; font-size: 1.5em; }}
    h3 {{ color: #777; font-weight: 400; font-size: 0.85em; margin-bottom: 20px; }}

    /* Dark Mode DataTables */
    .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, 
    .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_paginate {{ color: #aaa !important; font-size: 0.8em; }}
    
    input {{ background-color: #333 !important; color: white !important; border: 1px solid #444 !important; border-radius: 4px; padding: 4px; }}
    
    .leaderboard-table {{ width: 100% !important; border-collapse: collapse; margin-top: 15px; background: #1e1e1e; }}
    .leaderboard-table th {{ background-color: #252525 !important; color: #4a90e2 !important; font-size: 0.75em; text-transform: uppercase; padding: 12px; }}
    .leaderboard-table td {{ border-bottom: 1px solid #2a2a2a; padding: 10px; font-size: 0.9em; text-align: center; }}
    
    /* Tier Icon Specifics */
    .leaderboard-table td:nth-child(2) {{ font-size: 1.3em; width: 40px; }}

   /* Use double curly braces for CSS inside a Python f-string */
    .tier-eagle {{ background-color: rgba(255, 215, 0, 0.15) !important; border-left: 5px solid #ffd700 !important; }}
    .tier-fox   {{ background-color: rgba(255, 102, 0, 0.15) !important; border-left: 5px solid #ff6600 !important; }}
    .tier-bunny {{ background-color: rgba(205, 127, 50, 0.15) !important; border-left: 5px solid #cd7f32 !important; }}
    .tier-mouse {{ background-color: rgba(74, 144, 226, 0.15) !important; border-left: 5px solid #4a90e2 !important; }}
    
    /* Text Coloring for Player and ELO columns */
    .tier-eagle td:nth-child(3), .tier-eagle td:nth-child(4) {{ color: #ffd700; font-weight: bold; }}
    .tier-fox   td:nth-child(3), .tier-fox   td:nth-child(4) {{ color: #ff8533; font-weight: bold; }}
    .tier-bunny td:nth-child(3), .tier-bunny td:nth-child(4) {{ color: #dfa679; font-weight: bold; }}
    .tier-mouse td:nth-child(3), .tier-mouse td:nth-child(4) {{ color: #7db3f2; font-weight: bold; }}

    .unranked {{ opacity: 0.5; font-style: italic; }}
    .unranked td {{ color: #888 !important; }}
    
    /* Mobile specific adjustments */
    @media (max-width: 600px) {{
        h1 {{ font-size: 1.2em; }}
        .container {{ padding: 10px; }}
        /* Make borders slightly thinner on mobile */
        .tier-eagle, .tier-fox, .tier-bunny, .tier-mouse {{ border-left-width: 3px !important; }}
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
            <strong>Qualification:</strong> 10+ games & 1+ win.<br>
            <strong>Tiers:</strong> 1500+ 🦅 | 1400+ 🦊 | 1300+ 🐰 | 1200+ 🐭<br>
            Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"></script>

   <script>
    $(document).ready(function() {{
        // Custom sorting logic for Rank
        $.extend($.fn.dataTable.ext.type.order, {{
            "rank-pre": function (d) {{
                // If the value is "-", return a very high number (9999)
                // Otherwise, return the actual rank number
                return d === "-" ? 9999 : parseInt(d);
            }}
        }});

        $('#leaderboard').DataTable({{
            "order": [[3, "asc"]],
            "responsive": true,
            "pageLength": 50,
            "columnDefs": [
                {{ "type": "rank", "targets": 0 }}, // Use our custom 'rank' sorter
                {{ "responsivePriority": 1, "targets": [0, 2, 3] }},
                {{ "responsivePriority": 10, "targets": 1 }},
                {{ "className": "all", "targets": [0, 2, 3] }}
            ],
            "createdRow": function(row, data, dataIndex) {{
                var rank = data[0];         
                var elo = parseInt(data[3]); 
                
                if (rank === "-") {{
                    $(row).addClass('unranked');
                }} else {{
                    if (elo >= 1500) $(row).addClass('tier-eagle');
                    else if (elo >= 1400) $(row).addClass('tier-fox');
                    else if (elo >= 1300) $(row).addClass('tier-bunny');
                    else if (elo >= 1200) $(row).addClass('tier-mouse');
                }}
            }}
        }});
    }});
</script>
</body>
</html>
"""

# --- 9. Save to File ---
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("index.html successfully generated with Responsive support!")

