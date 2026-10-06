"""Collect team-level data: standings and per-team season totals.

Produces, per season:
    data/raw/standings_<season>.csv   -- one row per team: today's standings for the
                                         current season, final standings for a past one
    data/raw/team_stats_<season>.csv  -- one row per team, aggregated skater/goalie totals

Historical seasons are only fetched once (they're complete and never
change) -- see src/utils/raw_data.py. Each refresh re-fetches the
current season only.

Run from the project root:
    venv\\Scripts\\python.exe collectors\\collect_teams.py

Note on team_stats: the NHL's club-stats endpoint returns per-player
totals, not team-level special-teams data, so true power-play% and
penalty-kill% (opportunities, not just goals) are NOT available from
this endpoint. This collector aggregates what IS available (goals,
assists, shots, powerplay/shorthanded goals, goaltending totals) into
team-level sums. If precise PP%/PK% turn out to be needed for feature
engineering later, that will require investigating a different NHL
stats endpoint at that time -- it is not silently faked here.
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.client import NHLApiError
from src.api.nhl import (
    get_season_standings_end_dates,
    get_standings_now,
    get_standings_on,
    get_team_stats,
)
from src.utils.constants import CURRENT_SEASON, GAME_TYPE_REGULAR_SEASON, TEAM_ABBREVIATIONS
from src.utils.logging_config import get_logger
from src.utils.raw_data import save_season_csv, seasons_to_collect

logger = get_logger(__name__)

REQUEST_DELAY_SECONDS = 0.2  # be polite to an unofficial, unauthenticated API


def collect_standings(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """Fetch one season's standings, flattened into a DataFrame (one row per
    team): today's standings for the current season, final standings for a
    completed one."""
    if season == CURRENT_SEASON:
        logger.info("Fetching current standings...")
        standings = get_standings_now()
    else:
        end_date = get_season_standings_end_dates().get(season)
        if end_date is None:
            raise ValueError(f"No standings end date listed for season {season}.")
        logger.info("Fetching final standings for %s (as of %s)...", season, end_date)
        standings = get_standings_on(end_date)
    if not standings:
        raise ValueError(f"Standings response for {season} was empty -- API may have changed.")
    df = pd.json_normalize(standings)
    logger.info("Got standings for %d teams.", len(df))
    return df


def _aggregate_team_stats(team_abbrev: str, season: str) -> dict:
    """Fetch one team's season stats and roll skaters/goalies into team totals."""
    stats = get_team_stats(team_abbrev, season, GAME_TYPE_REGULAR_SEASON)
    skaters = pd.json_normalize(stats.get("skaters", []))
    goalies = pd.json_normalize(stats.get("goalies", []))

    row = {"team_abbrev": team_abbrev, "season": season}

    if not skaters.empty:
        row["total_goals"] = skaters["goals"].sum()
        row["total_assists"] = skaters["assists"].sum()
        row["total_points"] = skaters["points"].sum()
        row["total_shots"] = skaters["shots"].sum()
        row["total_powerplay_goals"] = skaters["powerPlayGoals"].sum()
        row["total_shorthanded_goals"] = skaters["shorthandedGoals"].sum()
    else:
        logger.warning("No skater stats found for %s/%s.", team_abbrev, season)

    if not goalies.empty:
        total_shots_against = goalies["shotsAgainst"].sum()
        total_saves = goalies["saves"].sum()
        row["total_shots_against"] = total_shots_against
        row["total_saves"] = total_saves
        row["team_save_pct"] = (
            total_saves / total_shots_against if total_shots_against else None
        )
        row["total_goals_against"] = goalies["goalsAgainst"].sum()
        row["total_shutouts"] = goalies["shutouts"].sum()
    else:
        logger.warning("No goalie stats found for %s/%s.", team_abbrev, season)

    return row


def collect_team_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """Fetch and aggregate season stat totals for every team."""
    rows = []
    for i, team in enumerate(TEAM_ABBREVIATIONS, start=1):
        logger.info("[%d/%d] Fetching team stats for %s...", i, len(TEAM_ABBREVIATIONS), team)
        try:
            rows.append(_aggregate_team_stats(team, season))
        except NHLApiError as exc:
            logger.error("Skipping %s due to repeated API failures: %s", team, exc)
        time.sleep(REQUEST_DELAY_SECONDS)

    if not rows:
        raise ValueError("Failed to collect team stats for every team -- aborting.")

    df = pd.DataFrame(rows)
    logger.info("Collected team stats for %d/%d teams.", len(df), len(TEAM_ABBREVIATIONS))
    return df


def main() -> None:
    for season in seasons_to_collect("standings"):
        save_season_csv(collect_standings(season), "standings", season)

    for season in seasons_to_collect("team_stats"):
        save_season_csv(collect_team_stats(season), "team_stats", season)


if __name__ == "__main__":
    main()
