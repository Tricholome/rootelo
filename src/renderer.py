import json
import os
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader
import pandas as pd

from engine import Logger, PlayerRegistry, get_match_url, get_tier_name, save_json


# =========================================================================
# --- 1. NAVIGATION & JINJA2 SETUP ---
# =========================================================================

NAV_ITEMS = [
    {'id': 'index', 'url': 'index.html', 'label': 'Leaderboard'},
    {'id': 'matches', 'url': 'matches.html', 'label': 'Top Tables'},
    {'id': 'trends', 'url': 'trends.html', 'label': "Player's Journey"},
    {'id': 'about', 'url': 'about.html', 'label': 'Codex'}
]


def setup_jinja_env(config):
    env = Environment(loader=FileSystemLoader(['templates', '.']))
    env.globals['config'] = config

    def smart_date_filter(d1, d2=None):
        if not d1:
            return ""
        try:
            dt1 = datetime.strptime(str(d1), '%Y-%m-%d')
            if not d2 or d1 == d2:
                return dt1.strftime('%b %d, %Y')

            dt2 = datetime.strptime(str(d2), '%Y-%m-%d')
            if dt1.year != dt2.year:
                return f"{dt1.strftime('%b %d, %Y')} — {dt2.strftime('%b %d, %Y')}"
            return f"{dt1.strftime('%b %d')} — {dt2.strftime('%b %d, %Y')}"
        except ValueError:
            return str(d1)

    env.filters['smart_date'] = smart_date_filter
    return env


# =========================================================================
# --- 2. FRONTEND DATA FORMATTERS ---
# =========================================================================

def format_match_timing(turn_timing, created_at, closed_at):
    if not turn_timing or str(turn_timing).lower() == 'live':
        return 0, "Live", None

    if not created_at or not closed_at or created_at == closed_at:
        return 99999999, "Async", None

    delta = pd.to_datetime(closed_at) - pd.to_datetime(created_at)
    seconds = max(1, int(delta.total_seconds()))
    days = delta.days

    if days == 0:
        hours = max(1, seconds // 3600)
        duration = f"{hours} hour" if hours == 1 else f"{hours} hours"
    else:
        duration = f"{days} day" if days == 1 else f"{days} days"

    return seconds, "Async", duration


def format_relations_data(raw_relations, player_registry):
    prepared = {}
    for pid, data in raw_relations.items():
        p_clean = player_registry.get_clean_name(pid)
        t_id = data["trophy"].get("id") or data["trophy"].get("name")
        t_elo = data["trophy"]["elo"]
        b_id = data["bane"].get("id") or data["bane"].get("name")
        b_elo = data["bane"]["elo"]

        prepared[p_clean] = {
            "unique_opponents": data.get("unique_opponents", 0),
            "trophy": {
                "name": player_registry.get_clean_name(t_id) if t_id else None,
                "elo": t_elo,
                "tier": get_tier_name(t_elo, 10) if t_elo != -1 else "unassigned"
            },
            "bane": {
                "name": player_registry.get_clean_name(b_id) if b_id else None,
                "elo": b_elo,
                "tier": get_tier_name(b_elo, 10) if b_elo != 99999 else "unassigned"
            }
        }
    return prepared


def format_homelands_snapshots(snapshots: dict, registry: PlayerRegistry) -> dict:
    cleaned = {}
    for date_key, snapshot in snapshots.items():
        cleaned_snapshot = {}
        for tribe_name, members in snapshot.items():
            cleaned_members = []
            for member_row in members:
                if isinstance(member_row, list) and len(member_row) >= 3:
                    p_clean = registry.get_clean_name(member_row[0])
                    cleaned_members.append([p_clean, member_row[1], member_row[2]])
                else:
                    cleaned_members.append(member_row)
            cleaned_snapshot[tribe_name] = cleaned_members
        cleaned[date_key] = cleaned_snapshot
    return cleaned


def format_constellations(constellations: dict, registry: PlayerRegistry) -> dict:
    if not constellations or "players" not in constellations:
        return constellations
    cleaned_players = {}
    for pid, p_data in constellations["players"].items():
        clean_p = registry.get_clean_name(pid)
        cleaned_partners = [
            [registry.get_clean_name(partner_id), weight]
            for partner_id, weight in p_data.get("partners", [])
        ]
        cleaned_players[clean_p] = {
            "tribe": p_data.get("tribe"),
            "games": p_data.get("games"),
            "partners": cleaned_partners
        }
    return {
        "date": constellations.get("date"),
        "players": cleaned_players
    }


def format_champ_match(champ_data, player_registry):
    if not champ_data:
        return None
    formatted = champ_data.copy()
    for key in ('champion', 'player2', 'player3', 'player4'):
        if formatted.get(key):
            formatted[key] = player_registry.get_clean_name(formatted[key])
    return formatted


def extract_latest_leaders(snapshots: dict) -> dict:
    if not snapshots:
        return {}
    latest_date = max(snapshots.keys())
    latest_snapshot = snapshots[latest_date]

    leaders = {}
    for tribe_name, members in latest_snapshot.items():
        if members:
            leader_name = members[0][0] if isinstance(members[0], list) else members[0]
            leaders[leader_name] = tribe_name.lower()
    return leaders


def prepare_leaderboard_data(df, player_registry, champion_ref=None, is_archive=False):
    if df.empty:
        return []

    data = []
    id_col = 'PlayerID' if 'PlayerID' in df.columns else 'Player'
    clean_champ = player_registry.get_clean_name(champion_ref) if champion_ref else None
    champ_str = str(champion_ref) if champion_ref is not None else None

    for _, row in df.iterrows():
        pid = str(row[id_col])
        clean_name = player_registry.get_clean_name(pid)
        is_champ = (champ_str is not None and (pid == champ_str or clean_name == clean_champ))
        rank_display = "♔" if (is_champ and is_archive) else row['Rank']
        tier = "bear" if is_champ else get_tier_name(row['ELO'], row['Games'])

        data.append({
            'Rank': rank_display,
            'tier': tier,
            'is_champion': is_champ,
            'player_id': pid,
            'display_name': clean_name,
            'ELO': int(round(row['ELO'])),
            'Games': row['Games'],
            'Wins': row['Wins'],
            'Win_Rate': row['Win Rate'],
            'Peak': row['Peak'],
            'Last': row['Last']
        })

    if clean_champ and is_archive:
        data.sort(key=lambda x: not x['is_champion'])

    return data


def prepare_matches_data(matches_list, player_registry, league_config):
    formatted = []
    for m in matches_list:
        order, timing_type, duration = format_match_timing(
            m.get('Turn_Timing'),
            m.get('Date_Created'),
            m.get('Date_Closed'),
        )
        formatted.append({
            'rank': m.get('Rank'),
            'elo_sum': m.get('ELO_Sum'),
            'date': m.get('Date'),
            'timing_order': order,
            'timing_type': timing_type,
            'timing_duration': duration,
            'players': sorted(
                [
                    {
                        'name': player_registry.get_clean_name(p.get('id') or p.get('name')),
                        'delta': p['delta'],
                        'is_winner': p['is_winner'],
                    }
                    for p in m.get('players', [])
                ],
                key=lambda x: x['is_winner'],
                reverse=True,
            ),
            'match_id': m.get('MatchID'),
            'match_url': get_match_url(m.get('MatchID'), league_config),
        })
    return formatted


def prepare_trends_data(history_dict, player_registry, league_config):
    if not history_dict:
        return {"history_json": "{}", "player_names": []}

    enriched_history = {}
    for pid, rows in history_dict.items():
        clean_rows = []
        for row in rows:
            match_id = row[2] if len(row) > 2 else None
            url = get_match_url(match_id, league_config)
            clean_rows.append([row[0], row[1], match_id, url])

        enriched_history[player_registry.get_clean_name(pid)] = clean_rows

    player_names = sorted(list(enriched_history.keys()), key=lambda x: x.lower())
    return {
        "history_json": json.dumps(enriched_history),
        "player_names": player_names
    }


# =========================================================================
# --- 3. HTML RENDERER & JSON API EXPORTER ---
# =========================================================================

class SiteRenderer:
    def __init__(
        self,
        config,
        pages_content,
        league_config,
        all_leagues_list,
        archive_seasons,
        global_players_list,
        player_profile_map,
        player_data_map_json,
        homelands_enabled,
    ):
        self.env = setup_jinja_env(config)
        self.pages_content = pages_content
        self.league_config = league_config
        self.all_leagues_list = all_leagues_list
        self.archive_seasons = archive_seasons
        self.global_players_list = global_players_list
        self.player_profile_map_json = json.dumps(player_profile_map)
        self.player_data_map_json = player_data_map_json
        self.homelands_enabled = homelands_enabled

        self.slug = league_config['slug']
        self.output_dir = league_config['output_dir']
        self.current_season_tag = league_config['current_season_tag']
        self.profile_base_url = league_config['profile_base_url']

    def render_page(self, template_name, output_name, **kwargs):
        template = self.env.get_template(template_name)
        prefix = "../" if (self.output_dir and self.output_dir not in ('.', '')) else ""
        page_id = kwargs.get("page_id")
        section_id = kwargs.get("section_id", page_id)

        full_vars = {
            "nav_items": NAV_ITEMS,
            "section_id": section_id,
            "generation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            "global_players": self.global_players_list,
            "player_profile_map_json": self.player_profile_map_json,
            "player_data_map_json": self.player_data_map_json,
            "profile_base_url": self.profile_base_url,
            "current_league": self.slug,
            "league_config": self.league_config,
            "homelands_enabled": self.homelands_enabled,
            "all_leagues": self.all_leagues_list,
            "path_prefix": prefix,
            "is_static": False,
            **kwargs
        }

        target_path = (
            os.path.join(self.output_dir, output_name)
            if self.output_dir not in ('.', '')
            else output_name
        )
        if self.output_dir not in ('.', '') and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(template.render(**full_vars))
        Logger.step(f"Page generated: {target_path}")

    def render_season_pages(
        self,
        tag,
        is_archive,
        lb_data,
        match_data,
        trends_data,
        meta,
        snapshots_data,
        constellations_data=None,
        relations_data=None,
        champ_match=None,
        suffix="",
    ):
        season_context = {
            "is_archive": is_archive,
            "has_seasons": bool(self.archive_seasons),
            "season_tag": tag,
            "archive_seasons": self.archive_seasons,
            "current_season_tag": self.current_season_tag,
            "cutoff_date": meta.get('cutoff_date', 'N/A'),
        }

        if self.homelands_enabled:
            leaders_map = extract_latest_leaders(snapshots_data)
            for player in lb_data:
                player['homeland_leader'] = leaders_map.get(player['display_name'])

        self.render_page(
            "index.html", f"index{suffix}.html",
            page_id="index",
            players=lb_data,
            champ_match=champ_match,
            match_count=meta.get('match_count', 0),
            **self.pages_content.get("index", {}),
            **season_context
        )

        self.render_page(
            "matches.html", f"matches{suffix}.html",
            page_id="matches",
            matches=match_data,
            match_count=meta.get('match_count', 0),
            **self.pages_content.get("matches", {}),
            **season_context
        )

        self.render_page(
            "trends.html", f"trends{suffix}.html",
            page_id="trends",
            history_json=trends_data['history_json'],
            player_names=trends_data['player_names'],
            relations_json=json.dumps(relations_data or {}),
            **self.pages_content.get("trends", {}),
            **season_context
        )

        if self.homelands_enabled and snapshots_data:
            self.render_page(
                "network.html", f"network{suffix}.html",
                page_id="network",
                section_id="network",
                dates_json=json.dumps(sorted(list(snapshots_data.keys()))),
                snapshots_json=json.dumps(snapshots_data),
                constellations_json=json.dumps(constellations_data or {}),
                **self.pages_content.get("network", {}),
                **season_context
            )

    def render_static_pages(self, hall_of_fame_data):
        static_pages = [
            ("about", "about.html", "codex"),
            ("league", "league.html", "codex"),
            ("simulator", "simulator.html", "codex"),
            ("cache", "cache.html", "cache")
        ]
        if self.homelands_enabled:
            static_pages.insert(3, ("homelands", "homelands.html", "network"))

        for page_id, tmpl, section_id in static_pages:
            p_info = self.pages_content.get(section_id, {})
            extra = {"hall_of_fame": hall_of_fame_data} if page_id == "cache" else {}

            self.render_page(
                tmpl, f"{page_id}.html",
                page_id=page_id,
                section_id=section_id,
                is_archive=False,
                has_seasons=False,
                is_static=True,
                is_law=(page_id in ["about", "league", "simulator", "homelands"]),
                **p_info,
                **extra
            )


def export_league_api(current_final_df, player_registry, reigning_champ, config, league_config):
    slug = league_config['slug']
    api_output_path = f"api/{slug}/elo.json"
    format_replace_chars = league_config.get('profile_format_replace_chars', False)

    site_base_url = config.get('site_base_url', '').rstrip('/')
    tier_colors = config.get('colors', {}).get('tiers', {})
    tier_icons = config.get('assets', {}).get('icons', {})

    api_data = {
        "updated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "players": {}
    }

    full_api_leaderboard = prepare_leaderboard_data(
        current_final_df, player_registry, champion_ref=reigning_champ
    ) if not current_final_df.empty else []

    for item in full_api_leaderboard:
        pid = item['player_id']
        raw_identifier = player_registry.get_profile_slug(pid, format_replace_chars)
        player_key = str(raw_identifier).lower().strip()

        tier = item['tier']
        color = tier_colors.get(tier)
        icon_path = tier_icons.get(tier)

        api_data["players"][player_key] = {
            "player_id": pid,
            "elo": item['ELO'],
            "rank": item['Rank'],
            "tier": tier,
            "bg_color": color,
            "icon_url": f"{site_base_url}/{icon_path.lstrip('/')}" if icon_path else None,
            "games": item['Games'],
            "wins": item['Wins'],
            "win_rate": item['Win_Rate']
        }

    save_json(api_output_path, api_data)
    Logger.success(f"API endpoint exported: {api_output_path} ({len(api_data['players'])} player records)")
