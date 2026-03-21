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

# --- 6. ELO Calculation Logic ---
# Initialize ratings at 1200 for all unique players found in the data
elo_ratings = {player: 1200 for player in df['Player'].unique()}

# Track statistics for each player to determine their K-Factor
player_stats = {player: {'games': 0, 'wins': 0.0} for player in df['Player'].unique()}

# Group data by GameID and process matches one by one (chronologically)
for game_id, group in df.groupby('GameID', sort=False):
    match_participants = group.to_dict('records')
    
    # Validation: Ensure we have exactly 4 participants for a standard game
    if len(match_participants) != 4:
        continue
    
    # Calculate the Total Q (sum of 10^(Rating/400)) for the table
    total_q = sum([10**(elo_ratings[p['Player']]/400) for p in match_participants])
    
    # Store temporary updates to apply them simultaneously after the match
    match_updates = {}
    
    for p in match_participants:
        name = p['Player']
        actual_score = p['Score']
        
        # Calculate expected score (Probability of winning)
        expected_score = (10**(elo_ratings[name]/400)) / total_q
        
        # Update player match count and win tally
        player_stats[name]['games'] += 1
        player_stats[name]['wins'] += actual_score
        
        # Dynamic K-Factor based on experience
        if player_stats[name]['games'] <= 10:
            k_factor = 80
        elif player_stats[name]['games'] <= 50:
            k_factor = 40
        else:
            k_factor = 20
            
        # Calculate new rating for this match
        match_updates[name] = elo_ratings[name] + k_factor * (actual_score - expected_score)
    
    # Apply all rating updates after the match calculation is complete
    for name, new_val in match_updates.items():
        elo_ratings[name] = new_val

# --- 7. Final Leaderboard Preparation ---

def get_tier_icon(rating, games):
    if games < 10: return ""
    if rating >= 1500: return "🦅"
    if rating >= 1400: return "🦊"
    if rating >= 1300: return "🐰"
    if rating >= 1200: return "🐭"
    return ""

leaderboard_results = []
for player_name, final_rating in elo_ratings.items():
    win_count = player_stats[player_name]['wins']
    total_games = player_stats[player_name]['games']
    
    # Qualification: 1+ win AND 10+ games
    if win_count > 0 and total_games >= 10:
        leaderboard_results.append({
            'Rank': 0,
            'Tier': get_tier_icon(final_rating, total_games),
            'Player': player_name,
            'Rating': round(final_rating),
            'Games': total_games,
            'Wins': round(win_count, 1),
            'Win Rate': f"{(win_count / total_games):.0%}"
        })

final_df = pd.DataFrame(leaderboard_results).sort_values(by='Rating', ascending=False)
final_df['Rank'] = range(1, len(final_df) + 1)
final_df = final_df[['Rank', 'Tier', 'Player', 'Rating', 'Games', 'Wins', 'Win Rate']]

# --- 8. HTML Webpage Generation with DataTables ---
html_table = final_df.to_html(index=False, classes='leaderboard-table display', table_id="leaderboard")

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Root League Leaderboard</title>
    
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">

    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #121212; color: #eee; text-align: center; padding: 40px 10px; }}
        .container {{ max-width: 900px; margin: auto; background: #1e1e1e; padding: 25px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); }}
        h1 {{ color: #4a90e2; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; }}
        h3 {{ color: #777; font-weight: 400; font-size: 0.9em; margin-bottom: 25px; }}

        /* Customizing DataTables for Dark Mode */
        .dataTables_wrapper .dataTables_length, .dataTables_wrapper .dataTables_filter, 
        .dataTables_wrapper .dataTables_info, .dataTables_wrapper .dataTables_processing, 
        .dataTables_wrapper .dataTables_paginate {{ color: #aaa !important; margin-bottom: 10px; }}
        
        input {{ background-color: #333 !important; color: white !important; border: 1px solid #444 !important; border-radius: 5px; padding: 5px; }}
        
        .leaderboard-table {{ width: 100% !important; border-collapse: collapse; margin-top: 20px; }}
        .leaderboard-table th {{ background-color: #252525 !important; color: #4a90e2 !important; cursor: pointer; }}
        .leaderboard-table td {{ border-bottom: 1px solid #2a2a2a; padding: 12px; text-align: center; }}
        
        .leaderboard-table td:nth-child(2) {{ font-size: 1.4em; }} /* Tier Icon size */
        
        .footer {{ margin-top: 30px; font-size: 0.75em; color: #555; line-height: 1.6; border-top: 1px solid #333; padding-top: 15px; }}
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
            Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>

    <script>
        $(document).ready(function() {{
            $('#leaderboard').DataTable({{
                "order": [[0, "asc"]], // Default sort by Rank
                "pageLength": 25,      // Number of players shown per page
                "lengthMenu": [10, 25, 50, 100],
                "responsive": true,
                "language": {{
                    "search": "Search Player:"
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

print("index.html successfully generated!")

