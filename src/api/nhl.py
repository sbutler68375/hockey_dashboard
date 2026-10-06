"""Thin wrappers around specific NHL API endpoints.

Each function returns the raw parsed JSON (or the relevant sub-list)
for one endpoint, with no flattening or transformation. Turning these
into DataFrames/CSVs happens in the collectors/ scripts, so these stay
simple, reusable, and easy to re-verify against the live API.
"""

from typing import Any

from src.api.client import get_json
from src.utils.constants import NHL_API_BASE


def get_standings_now() -> list[dict[str, Any]]:
    """Return current league standings, one entry per team.

    During the offseason this reflects the final standings of the most
    recently completed season.
    """
    data = get_json(f"{NHL_API_BASE}/standings/now")
    return data.get("standings", [])


def get_standings_on(date: str) -> list[dict[str, Any]]:
    """Return league standings as of one date (YYYY-MM-DD), one entry per team."""
    data = get_json(f"{NHL_API_BASE}/standings/{date}")
    return data.get("standings", [])


def get_season_standings_end_dates() -> dict[str, str]:
    """Return {season id: last date standings were recorded} for every season,
    e.g. {"20252026": "2026-04-17"} -- used to fetch a past season's final standings."""
    data = get_json(f"{NHL_API_BASE}/standings-season")
    return {str(s["id"]): s["standingsEnd"] for s in data.get("seasons", [])}


def get_team_roster(team_abbrev: str) -> dict[str, list[dict[str, Any]]]:
    """Return a team's *current* roster, split into forwards/defensemen/goalies.

    Note: this reflects today's roster, not necessarily the roster for
    any particular past season -- see collect_players.py for how this
    is reconciled with season stats.
    """
    return get_json(f"{NHL_API_BASE}/roster/{team_abbrev}/current")


def get_team_stats(team_abbrev: str, season: str, game_type: int) -> dict[str, Any]:
    """Return a team's skater and goalie stat totals for one season."""
    url = f"{NHL_API_BASE}/club-stats/{team_abbrev}/{season}/{game_type}"
    return get_json(url)


def get_team_season_schedule(team_abbrev: str, season: str) -> list[dict[str, Any]]:
    """Return every game (played and upcoming) for a team in one season.

    Each game appears in two teams' schedules (once as home, once as
    away) -- callers collecting league-wide games must dedupe by game id.
    """
    url = f"{NHL_API_BASE}/club-schedule-season/{team_abbrev}/{season}"
    data = get_json(url)
    return data.get("games", [])
