"""Collect per-game skater stats: one row per skater per regular-season game.

Produces, per season:
    data/raw/player_games_<season>.csv

These game logs feed the player ratings model (src/models/player_ratings.py):
season-to-date scoring, shots and ice time at any point in a season, and
how a player has played lately. Goalies aren't included.

Historical seasons are only fetched once (they're complete and never
change) -- see src/utils/raw_data.py. Each refresh re-fetches the
current season only.

Run from the project root:
    venv\\Scripts\\python.exe collectors\\collect_player_games.py

Source: the NHL stats API's skater "summary" (goals, assists, points,
shots, power-play points) and "timeonice" (ice time by situation, shifts)
reports, joined on player and game. A season is ~48,000 rows per report,
so each is fetched a month at a time.
"""

import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.nhl import get_skater_game_reports
from src.utils.constants import CURRENT_SEASON, GAME_TYPE_REGULAR_SEASON
from src.utils.logging_config import get_logger
from src.utils.raw_data import save_season_csv, seasons_to_collect

logger = get_logger(__name__)

REQUEST_DELAY_SECONDS = 0.2

PLAYER_GAME_COLUMNS = [
    "player_id", "game_id", "season", "game_date", "team_abbrev", "opponent_abbrev",
    "player_name", "position_code", "goals", "assists", "points", "pp_points", "shots",
    "toi_seconds", "ev_toi_seconds", "pp_toi_seconds", "sh_toi_seconds", "shifts",
]


def _month_starts(season: str) -> list[str]:
    """First day of each month a regular season can span (September through
    June), plus July 1 to close the last range."""
    start_year, end_year = int(season[:4]), int(season[4:])
    months = [(start_year, m) for m in range(9, 13)] + [(end_year, m) for m in range(1, 8)]
    return [f"{y}-{m:02d}-01" for y, m in months]


def collect_player_games(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """Fetch every skater's game-by-game stats for one season, a month at a time."""
    starts = _month_starts(season)
    today = date.today().isoformat()
    summary_frames, toi_frames = [], []
    for start, end in zip(starts, starts[1:]):
        if start > today:
            break
        logger.info("Fetching skater games for %s, %s to %s...", season, start, end)
        summary_frames.append(pd.DataFrame(
            get_skater_game_reports("summary", season, GAME_TYPE_REGULAR_SEASON, start, end)))
        time.sleep(REQUEST_DELAY_SECONDS)
        toi_frames.append(pd.DataFrame(
            get_skater_game_reports("timeonice", season, GAME_TYPE_REGULAR_SEASON, start, end)))
        time.sleep(REQUEST_DELAY_SECONDS)

    summary = pd.concat(summary_frames, ignore_index=True)
    toi = pd.concat(toi_frames, ignore_index=True)
    if summary.empty:
        logger.warning("No skater game stats yet for %s.", season)
        return pd.DataFrame(columns=PLAYER_GAME_COLUMNS)

    keys = ["playerId", "gameId"]
    df = summary[keys + ["gameDate", "teamAbbrev", "opponentTeamAbbrev", "skaterFullName",
                         "positionCode", "goals", "assists", "points", "ppPoints", "shots"]].merge(
        toi[keys + ["timeOnIce", "evTimeOnIce", "ppTimeOnIce", "shTimeOnIce", "shifts"]],
        on=keys, how="left",
    )
    df["season"] = int(season)
    df = df.rename(columns={
        "playerId": "player_id", "gameId": "game_id", "gameDate": "game_date",
        "teamAbbrev": "team_abbrev", "opponentTeamAbbrev": "opponent_abbrev",
        "skaterFullName": "player_name", "positionCode": "position_code", "ppPoints": "pp_points",
        "timeOnIce": "toi_seconds", "evTimeOnIce": "ev_toi_seconds",
        "ppTimeOnIce": "pp_toi_seconds", "shTimeOnIce": "sh_toi_seconds",
    })
    before = len(df)
    df = df.drop_duplicates(subset=["player_id", "game_id"])
    if len(df) < before:
        logger.warning("Dropped %d duplicate skater-game rows.", before - len(df))
    logger.info("Got %d skater-games for %s.", len(df), season)
    return df[PLAYER_GAME_COLUMNS].sort_values(["game_date", "game_id", "player_id"]).reset_index(drop=True)


def main() -> None:
    for season in seasons_to_collect("player_games"):
        save_season_csv(collect_player_games(season), "player_games", season)


if __name__ == "__main__":
    main()
