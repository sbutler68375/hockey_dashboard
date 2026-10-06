"""Collect games (played and upcoming) for every season in COLLECTED_SEASONS.

Historical seasons double as model training history.

Produces, per season:
    data/raw/games_<season>.csv

Historical seasons are only fetched once (they're complete and never
change) -- see src/utils/raw_data.py. Each refresh re-fetches the
current season only.

Run from the project root:
    venv\\Scripts\\python.exe collectors\\collect_games.py

Each game is pulled once per team's season schedule, so every game
appears twice in the raw results (once from the home team's schedule,
once from the away team's) -- this collector dedupes on the NHL's game
id before saving.

Deliberately NOT included here: any "home team won" / target-style
column. This file is raw box-score data only (final score, teams,
date, game state). Deriving prediction targets from it is Phase 3's
job, kept separate so it's obvious where raw data ends and
feature/label engineering begins.

Verified quirk in game_state (2026-08-26): completed games use TWO
different values depending on game_type -- preseason games (game_type
1) report game_state "FINAL", while regular season (2) and playoff (3)
games report "OFF". Both mean "completed". Anything that filters for
finished games later must check for both values, not just one.

last_period_type ('REG', 'OT' or 'SO') says whether a finished game was
decided in regulation, overtime or a shootout -- empty for unplayed games.
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.client import NHLApiError
from src.api.nhl import get_team_season_schedule
from src.utils.constants import CURRENT_SEASON, TEAM_ABBREVIATIONS
from src.utils.logging_config import get_logger
from src.utils.raw_data import save_season_csv, seasons_to_collect

logger = get_logger(__name__)

REQUEST_DELAY_SECONDS = 0.2

GAME_COLUMNS = {
    "id": "game_id",
    "season": "season",
    "gameType": "game_type",
    "gameDate": "game_date",
    "startTimeUTC": "start_time_utc",
    "gameState": "game_state",
    "venue.default": "venue",
    "awayTeam.abbrev": "away_team",
    "awayTeam.score": "away_score",
    "homeTeam.abbrev": "home_team",
    "homeTeam.score": "home_score",
    "gameOutcome.lastPeriodType": "last_period_type",
}


def collect_games(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """Fetch every team's season schedule and dedupe into one games table."""
    frames = []
    for i, team in enumerate(TEAM_ABBREVIATIONS, start=1):
        logger.info("[%d/%d] Fetching schedule for %s...", i, len(TEAM_ABBREVIATIONS), team)
        try:
            games = get_team_season_schedule(team, season)
        except NHLApiError as exc:
            logger.error("Skipping %s due to repeated API failures: %s", team, exc)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if not games:
            logger.warning("No games returned for %s/%s.", team, season)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        frame = pd.json_normalize(games)
        frames.append(frame)
        time.sleep(REQUEST_DELAY_SECONDS)

    if not frames:
        raise ValueError("Failed to collect games for every team -- aborting.")

    combined = pd.concat(frames, ignore_index=True, sort=False)

    missing_cols = [c for c in GAME_COLUMNS if c not in combined.columns]
    if missing_cols:
        logger.warning(
            "Expected columns missing from schedule response (API may "
            "have changed): %s -- these will be absent from the output.",
            missing_cols,
        )

    available_cols = {k: v for k, v in GAME_COLUMNS.items() if k in combined.columns}
    trimmed = combined[list(available_cols.keys())].rename(columns=available_cols)

    before = len(trimmed)
    deduped = trimmed.drop_duplicates(subset="game_id").reset_index(drop=True)
    logger.info(
        "Deduped %d raw rows (2 per game expected) down to %d unique games.",
        before, len(deduped),
    )

    return deduped


def main() -> None:
    for season in seasons_to_collect("games"):
        logger.info("Collecting games for season %s...", season)
        save_season_csv(collect_games(season), "games", season)


if __name__ == "__main__":
    main()
