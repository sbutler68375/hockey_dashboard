"""Read-only query functions for the NHL database.

These return pandas DataFrames so downstream code (feature engineering,
the dashboard) can work with results the same way it already works
with the raw CSVs.
"""

import pandas as pd

from src.database.db import get_connection


def get_team_games(team_abbrev: str, season: int | None = None) -> pd.DataFrame:
    """Return all games (home or away) for one team, most recent first."""
    query = """
        SELECT * FROM games
        WHERE (home_team = ? OR away_team = ?)
    """
    params: list = [team_abbrev, team_abbrev]
    if season is not None:
        query += " AND season = ?"
        params.append(season)
    query += " ORDER BY game_date DESC"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_standings(date: str | None = None) -> pd.DataFrame:
    """Return standings, optionally filtered to one snapshot date, joined
    with conference/division from teams (standings itself doesn't carry those).

    If no date is given, returns the most recent snapshot available.
    """
    with get_connection() as conn:
        if date is None:
            date_row = conn.execute("SELECT MAX(date) FROM standings").fetchone()
            date = date_row[0] if date_row else None
        query = """
            SELECT s.*, t.conference_name, t.division_name
            FROM standings s
            JOIN teams t ON s.team_abbrev = t.team_abbrev
            WHERE s.date = ?
            ORDER BY s.points DESC
        """
        return pd.read_sql_query(query, conn, params=[date])


def get_player_stats(season: int, player_type: str | None = None) -> pd.DataFrame:
    """Return player stats for one season, optionally filtered to skaters/goalies."""
    query = "SELECT * FROM players WHERE season = ?"
    params: list = [season]
    if player_type is not None:
        query += " AND player_type = ?"
        params.append(player_type)

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_team_season_stats(season: int) -> pd.DataFrame:
    """Return aggregated team totals for one season."""
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM team_season_stats WHERE season = ?", conn, params=[season]
        )


def get_completed_games(game_type: int | None = 2) -> pd.DataFrame:
    """Return finished games, ordered chronologically.

    Completed games use game_state "OFF" (regular season/playoffs) or
    "FINAL" (preseason) -- both are included here since either counts
    as finished; see collect_games.py for why the two values exist.

    Args:
        game_type: NHL gameType code to filter to (2 = regular season,
            the default and the only type currently used for feature
            engineering). Pass None to include all game types.
    """
    query = "SELECT * FROM games WHERE game_state IN ('OFF', 'FINAL')"
    params: list = []
    if game_type is not None:
        query += " AND game_type = ?"
        params.append(game_type)
    query += " ORDER BY game_date ASC"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)
