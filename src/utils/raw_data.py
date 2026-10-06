"""Per-season raw CSV files in data/raw/, shared by the collectors and importers.

Each collector writes one file per dataset per season, e.g.
data/raw/games_20252026.csv. A completed season's data never changes,
so collectors only fetch a historical season when its file doesn't
exist yet -- after the first pull, a refresh only re-fetches the
current season. To force a historical season to be re-fetched (e.g. a
column was added to a collector), delete its file and rerun.
"""

from pathlib import Path

import pandas as pd

from src.utils.constants import COLLECTED_SEASONS, CURRENT_SEASON
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def season_csv_path(dataset: str, season: str) -> Path:
    """data/raw/<dataset>_<season>.csv, e.g. games_20262027.csv."""
    return RAW_DIR / f"{dataset}_{season}.csv"


def seasons_to_collect(dataset: str) -> list[str]:
    """The current season always, plus any historical season whose file
    hasn't been collected yet."""
    seasons = []
    for season in COLLECTED_SEASONS:
        if season != CURRENT_SEASON and season_csv_path(dataset, season).exists():
            logger.info("%s for %s already collected -- skipping (season is complete).", dataset, season)
            continue
        seasons.append(season)
    return seasons


def save_season_csv(df: pd.DataFrame, dataset: str, season: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = season_csv_path(dataset, season)
    df.to_csv(path, index=False)
    logger.info("Saved %s (%d rows)", path, len(df))


def read_all_seasons(dataset: str) -> pd.DataFrame:
    """Every collected season's file for a dataset, stacked oldest season first.

    Raises:
        FileNotFoundError: if any collected season's file is missing.
    """
    frames = []
    for season in COLLECTED_SEASONS:
        path = season_csv_path(dataset, season)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found -- run the matching collector in collectors/ first."
            )
        frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True, sort=False)
