"""Load collected per-season CSVs (data/raw/<dataset>_<season>.csv) into
the SQLite database.

Column renames below map the NHL API's raw field names (as they land
in our CSVs via pd.json_normalize) to the schema's snake_case columns.
Every source column name here was verified against real CSV output
(see collectors/), not guessed.
"""

from src.database.db import get_connection, upsert_dataframe
from src.utils.logging_config import get_logger
from src.utils.raw_data import read_all_seasons

logger = get_logger(__name__)


def load_teams() -> int:
    """Derive the teams dimension table from the standings files (one row/team).

    Files are stacked oldest season first, so keep="last" takes each team's
    names/division from the current season if they've changed."""
    df = read_all_seasons("standings")
    rename = {
        "teamAbbrev.default": "team_abbrev",
        "teamName.default": "team_name",
        "teamCommonName.default": "common_name",
        "placeName.default": "place_name",
        "conferenceName": "conference_name",
        "divisionName": "division_name",
    }
    teams = df.rename(columns=rename)[list(rename.values())].drop_duplicates(subset="team_abbrev", keep="last")

    with get_connection() as conn:
        return upsert_dataframe(conn, "teams", teams, pk_columns=["team_abbrev"])


def load_standings() -> int:
    """Load the standings files into the standings table."""
    df = read_all_seasons("standings")
    rename = {
        "teamAbbrev.default": "team_abbrev",
        "date": "date",
        "seasonId": "season_id",
        "gamesPlayed": "games_played",
        "wins": "wins",
        "losses": "losses",
        "otLosses": "ot_losses",
        "ties": "ties",
        "points": "points",
        "pointPctg": "point_pctg",
        "goalFor": "goal_for",
        "goalAgainst": "goal_against",
        "goalDifferential": "goal_differential",
        "homeWins": "home_wins",
        "homeLosses": "home_losses",
        "homeOtLosses": "home_ot_losses",
        "homePoints": "home_points",
        "roadWins": "road_wins",
        "roadLosses": "road_losses",
        "roadOtLosses": "road_ot_losses",
        "roadPoints": "road_points",
        "l10Wins": "l10_wins",
        "l10Losses": "l10_losses",
        "l10OtLosses": "l10_ot_losses",
        "l10Points": "l10_points",
        "streakCode": "streak_code",
        "streakCount": "streak_count",
    }
    standings = df.rename(columns=rename)[list(rename.values())]

    with get_connection() as conn:
        return upsert_dataframe(conn, "standings", standings, pk_columns=["team_abbrev", "date"])


def load_team_season_stats() -> int:
    """Load the team_stats files into the team_season_stats table."""
    df = read_all_seasons("team_stats")  # already snake_case, matches schema directly
    with get_connection() as conn:
        return upsert_dataframe(conn, "team_season_stats", df, pk_columns=["team_abbrev", "season"])


def load_games() -> int:
    """Load the games files into the games table."""
    df = read_all_seasons("games")  # already snake_case, matches schema directly
    with get_connection() as conn:
        return upsert_dataframe(conn, "games", df, pk_columns=["game_id"])


def load_players() -> int:
    """Load the player_stats files into the players table."""
    df = read_all_seasons("player_stats")
    rename = {
        "playerId": "player_id",
        "team_abbrev": "team_abbrev",
        "season": "season",
        "player_type": "player_type",
        "firstName.default": "first_name",
        "lastName.default": "last_name",
        "positionCode": "position_code",
        "gamesPlayed": "games_played",
        "goals": "goals",
        "assists": "assists",
        "points": "points",
        "plusMinus": "plus_minus",
        "penaltyMinutes": "penalty_minutes",
        "powerPlayGoals": "power_play_goals",
        "shorthandedGoals": "shorthanded_goals",
        "gameWinningGoals": "game_winning_goals",
        "overtimeGoals": "overtime_goals",
        "shots": "shots",
        "shootingPctg": "shooting_pctg",
        "avgTimeOnIcePerGame": "avg_time_on_ice_per_game",
        "avgShiftsPerGame": "avg_shifts_per_game",
        "faceoffWinPctg": "faceoff_win_pctg",
        "gamesStarted": "games_started",
        "wins": "wins",
        "losses": "losses",
        "overtimeLosses": "overtime_losses",
        "savePercentage": "save_pctg",
        "goalsAgainstAverage": "goals_against_average",
        "shotsAgainst": "shots_against",
        "saves": "saves",
        "goalsAgainst": "goals_against",
        "shutouts": "shutouts",
        "timeOnIce": "goalie_time_on_ice_seconds",
        "heightInCentimeters": "height_cm",
        "weightInKilograms": "weight_kg",
        "birthDate": "birth_date",
        "birthCountry": "birth_country",
        "shootsCatches": "shoots_catches",
    }
    available = {k: v for k, v in rename.items() if k in df.columns}
    missing = set(rename) - set(available)
    if missing:
        logger.warning("player_stats files missing expected columns: %s", missing)

    players = df.rename(columns=available)[list(available.values())]

    with get_connection() as conn:
        return upsert_dataframe(
            conn, "players", players, pk_columns=["player_id", "team_abbrev", "season"]
        )


def load_special_teams_games() -> int:
    """Load the special_teams_games files into the team_game_special_teams table."""
    df = read_all_seasons("special_teams_games")  # already snake_case, matches schema directly
    with get_connection() as conn:
        return upsert_dataframe(conn, "team_game_special_teams", df, pk_columns=["game_id", "team_abbrev"])


def load_all() -> dict[str, int]:
    """Run every importer in dependency order (teams before anything referencing them)."""
    results = {}
    results["teams"] = load_teams()
    results["standings"] = load_standings()
    results["team_season_stats"] = load_team_season_stats()
    results["games"] = load_games()
    results["players"] = load_players()
    results["team_game_special_teams"] = load_special_teams_games()
    return results
