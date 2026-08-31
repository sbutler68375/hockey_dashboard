"""Time-aware train/validation/test splitting.

Hockey outcomes are serially correlated (hot streaks, injuries, trade
deadlines) -- a random shuffle split would let the model train on games
chronologically *after* ones it's tested on, which is a leakage risk in
spirit even if no single feature is literally from the future. Splits
here are always a straight chronological cut.

Caveat, stated plainly: with only one season of games collected so far,
this cut happens *within* that season (e.g. first 70% of games by date
vs. the last 15%), not across separate seasons. That's weaker than a
true out-of-season holdout. Once a second season is collected, this
same function naturally supports splitting across season boundaries
too -- no code change needed, just more chronological data to cut.
"""

import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def time_aware_split(
    df: pd.DataFrame,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    date_column: str = "game_date",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a chronologically-sortable DataFrame into train/val/test by date cut.

    Args:
        df: Data to split. Assumed already sorted (or sortable) by date_column.
        train_frac: Fraction of rows (by date order) assigned to training.
        val_frac: Fraction assigned to validation. Remainder goes to test.
        date_column: Column used to establish chronological order.

    Returns:
        (train_df, val_df, test_df), each a contiguous chronological slice.
    """
    if train_frac + val_frac >= 1.0:
        raise ValueError("train_frac + val_frac must leave a nonzero test fraction.")

    df = df.sort_values(date_column).reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_frac)
    val_end = train_end + int(n * val_frac)

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    logger.info(
        "Time-aware split: train=%d (%s to %s), val=%d (%s to %s), test=%d (%s to %s)",
        len(train_df), train_df[date_column].min().date(), train_df[date_column].max().date(),
        len(val_df), val_df[date_column].min().date(), val_df[date_column].max().date(),
        len(test_df), test_df[date_column].min().date(), test_df[date_column].max().date(),
    )
    return train_df, val_df, test_df
