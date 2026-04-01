# =========================================================================
# --- 7. FINAL LEADERBOARD GENERATION ---
# =========================================================================
leaderboard_list = []
for p_name, rating in elo_ratings.items():
    s = player_stats.get(p_name, {'wins': 0, 'games': 0})
    display_elo = round(rating)
    diff = round(last_diff.get(p_name, 0))
    is_qual = (s['games'] >= 10 and display_elo >= 1200)
    
    leaderboard_list.append({
        'Rank': 0, 'Player': p_name, 'ELO': display_elo, 'Games': s['games'],
        'Wins': s['wins'], 'Win Rate': f"{(s['wins']/s['games']):.1%}" if s['games'] > 0 else "0.0%",
        'Peak': round(peak_elo.get(p_name, rating)), 
        'Last': f"+{diff}" if diff > 0 else str(diff),
        'Qualified': is_qual
    })

if leaderboard_list:
    current_final_df = pd.DataFrame(leaderboard_list).sort_values(by='ELO', ascending=False)
    
    rank_counter = 1
    ranks = []
    for _, row in current_final_df.iterrows():
        if row['Qualified']:
            ranks.append(rank_counter)
            rank_counter += 1
        else: 
            ranks.append("-")
    current_final_df['Rank'] = ranks
else:
    current_final_df = pd.DataFrame(columns=['Rank', 'Player', 'ELO', 'Games', 'Wins', 'Win Rate', 'Peak', 'Last', 'Qualified'])

current_history = {k.split('+')[0].split('#')[0]: v for k, v in player_history.items()}
