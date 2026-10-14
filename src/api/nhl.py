"""Thin wrappers around specific NHL API endpoints.

Each function returns the raw parsed JSON (or the relevant sub-list)
for one endpoint, with no flattening or transformation. Turning these
into DataFrames/CSVs happens in the collectors/ scripts, so these stay
simple, reusable, and easy to re-verify against the live API.
"""

from typing import Any

from src.api.client import get_json
from src.utils.constants import NHL_API_BASE, NHL_STATS_API_BASE


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


def get_stats_api_teams() -> list[dict[str, Any]]:
    """Return every team the stats API knows (past franchises included),
    each with its numeric id and abbreviation (triCode)."""
    data = get_json(f"{NHL_STATS_API_BASE}/team")
    return data.get("data", [])


def get_team_summaries(season: str, game_type: int) -> list[dict[str, Any]]:
    """Return one season summary row per team from the stats API,
    including powerPlayPct and penaltyKillPct (fractions, e.g. 0.21)."""
    url = f"{NHL_STATS_API_BASE}/team/summary?cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}"
    data = get_json(url)
    return data.get("data", [])


def get_team_game_reports(report: str, season: str, game_type: int) -> list[dict[str, Any]]:
    """Return one row per team per game from a stats API team report.

    report is e.g. "powerplay" (ppGoalsFor, ppOpportunities), "penaltykill"
    (ppGoalsAgainst, timesShorthanded), "summary" (goalsFor/Against,
    shotsFor/AgainstPerGame -- for one game, just that game's shots --
    and points earned), "realtime" (totalShotAttempts) or "percentages"
    (satPct, shootingPct5v5, savePct5v5). Every row has teamId, gameId and
    gameDate (all verified live 2026-10-13).
    """
    url = (
        f"{NHL_STATS_API_BASE}/team/{report}?isAggregate=false&isGame=true&limit=-1"
        f"&cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}"
    )
    data = get_json(url)
    return data.get("data", [])


def get_skater_game_reports(report: str, season: str, game_type: int,
                            start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Return one row per skater per game from a stats API skater report, for
    games on start_date <= gameDate < end_date (YYYY-MM-DD).

    report is "summary" (goals, assists, points, shots, ppPoints) or
    "timeonice" (timeOnIce, ppTimeOnIce, shTimeOnIce, evTimeOnIce, shifts --
    seconds); every row has playerId, gameId, gameDate and teamAbbrev
    (verified live 2026-10-13). A full season is ~48,000 rows (~25 MB), so
    callers fetch it a date range at a time.
    """
    url = (
        f"{NHL_STATS_API_BASE}/skater/{report}?isAggregate=false&isGame=true&limit=-1"
        f"&cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}"
        f"%20and%20gameDate%3E=%22{start_date}%22%20and%20gameDate%3C%22{end_date}%22"
    )
    data = get_json(url, timeout=90)
    return data.get("data", [])
