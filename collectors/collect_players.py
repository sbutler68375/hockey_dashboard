"""Collect player-level season stats, enriched with bio info where possible.

Produces:
    data/raw/player_stats.csv

Run from the project root:
    venv\\Scripts\\python.exe collectors\\collect_players.py

Important timing caveat (documented, not silently papered over): a
player's season stats (club-stats) and a team's *current* roster
(roster/current) are two different snapshots in time. A player who was
traded, waived, or retired since DEFAULT_SEASON ended won't appear on
their old team's current roster anymore, so bio fields (birth date,
height, shoots/catches, etc.) for that player will be missing (NaN)
in the output. Stats themselves are unaffected -- they come entirely
from club-stats, which is already correctly tied to the season
requested. The number of unmatched players is logged so this is
visible, not hidden.
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.client import NHLApiError
from src.api.nhl import get_team_roster, get_team_stats
from src.utils.constants import DEFAULT_SEASON, GAME_TYPE_REGULAR_SEASON, TEAM_ABBREVIATIONS
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
REQUEST_DELAY_SECONDS = 0.2

BIO_COLUMNS = [
    "heightInCentimeters",
    "weightInKilograms",
    "birthDate",
    "birthCountry",
    "shootsCatches",
]


def _roster_bio_frame(team_abbrev: str) -> pd.DataFrame:
    """Fetch a team's current roster and flatten forwards/defensemen/goalies
    into one bio DataFrame keyed by playerId."""
    roster = get_team_roster(team_abbrev)
    players = roster.get("forwards", []) + roster.get("defensemen", []) + roster.get("goalies", [])
    if not players:
        return pd.DataFrame(columns=["playerId", *BIO_COLUMNS])
    df = pd.json_normalize(players)
    keep = ["id", *[c for c in BIO_COLUMNS if c in df.columns]]
    df = df[keep].rename(columns={"id": "playerId"})
    return df


def _team_player_stats(team_abbrev: str, season: str) -> pd.DataFrame:
    """Fetch and flatten a team's skater + goalie season stats, merged with
    current-roster bio fields where a playerId match exists."""
    stats = get_team_stats(team_abbrev, season, GAME_TYPE_REGULAR_SEASON)

    skaters = pd.json_normalize(stats.get("skaters", []))
    if not skaters.empty:
        skaters["player_type"] = "skater"

    goalies = pd.json_normalize(stats.get("goalies", []))
    if not goalies.empty:
        goalies["player_type"] = "goalie"

    combined = pd.concat([skaters, goalies], ignore_index=True, sort=False)
    if combined.empty:
        logger.warning("No player stats found for %s/%s.", team_abbrev, season)
        return combined

    combined["team_abbrev"] = team_abbrev
    combined["season"] = season

    bio = _roster_bio_frame(team_abbrev)
    merged = combined.merge(bio, on="playerId", how="left")

    unmatched = merged["heightInCentimeters"].isna().sum() if "heightInCentimeters" in merged else len(merged)
    if unmatched:
        logger.info(
            "%s: %d/%d players have no current-roster bio match "
            "(likely traded/waived/retired since %s).",
            team_abbrev, unmatched, len(merged), season,
        )

    return merged


def collect_player_stats(season: str = DEFAULT_SEASON) -> pd.DataFrame:
    """Fetch and combine player season stats for every team."""
    frames = []
    for i, team in enumerate(TEAM_ABBREVIATIONS, start=1):
        logger.info("[%d/%d] Fetching player stats for %s...", i, len(TEAM_ABBREVIATIONS), team)
        try:
            frame = _team_player_stats(team, season)
            if not frame.empty:
                frames.append(frame)
        except NHLApiError as exc:
            logger.error("Skipping %s due to repeated API failures: %s", team, exc)
        time.sleep(REQUEST_DELAY_SECONDS)

    if not frames:
        raise ValueError("Failed to collect player stats for every team -- aborting.")

    df = pd.concat(frames, ignore_index=True, sort=False)
    logger.info("Collected stats for %d players across %d teams.", len(df), len(frames))
    return df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = collect_player_stats()
    output_path = OUTPUT_DIR / "player_stats.csv"
    df.to_csv(output_path, index=False)
    logger.info("Saved %s (%d rows)", output_path, len(df))


if __name__ == "__main__":
    main()
