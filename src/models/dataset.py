"""Loads data/processed/features.csv into a model-ready dataset.

Scope for Phase 4 v1: the classification target (target_home_win) only.
target_total_goals (regression) uses different metrics (MAE/RMSE, not
accuracy/log-loss/ROC-AUC) and is deliberately left for a follow-up
rather than folded into this first pass.
"""

from pathlib import Path

import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

FEATURES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "features.csv"

FEATURE_COLUMNS = [
    "home_games_played_prior", "home_win_pct_last_5", "home_win_pct_last_10", "home_win_pct_season_to_date",
    "home_goals_for_avg_last_5", "home_goals_for_avg_last_10",
    "home_goals_against_avg_last_5", "home_goals_against_avg_last_10",
    "home_rest_days", "home_back_to_back",
    "away_games_played_prior", "away_win_pct_last_5", "away_win_pct_last_10", "away_win_pct_season_to_date",
    "away_goals_for_avg_last_5", "away_goals_for_avg_last_10",
    "away_goals_against_avg_last_5", "away_goals_against_avg_last_10",
    "away_rest_days", "away_back_to_back",
    "win_pct_last10_diff", "goals_for_avg_last10_diff", "rest_days_diff",
]

TARGET_COLUMN = "target_home_win"


def load_model_dataset() -> pd.DataFrame:
    """Load features.csv, sorted chronologically, with incomplete rows dropped.

    Rows missing any feature value -- in practice, only each team's
    season-opener, which has no prior-season history to build rolling
    features from -- are dropped. The count dropped is logged so this
    is a visible, deliberate choice, not silent data loss.
    """
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"{FEATURES_PATH} not found -- run scripts/generate_features.py first.")

    df = pd.read_csv(FEATURES_PATH, parse_dates=["game_date"])
    df = df.sort_values("game_date").reset_index(drop=True)

    required = FEATURE_COLUMNS + [TARGET_COLUMN]
    before = len(df)
    df = df.dropna(subset=required).reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        logger.info(
            "Dropped %d/%d rows with missing features (season-opener games "
            "with no prior-season history yet) -- deliberate, not silent.",
            dropped, before,
        )

    for col in ["home_back_to_back", "away_back_to_back"]:
        df[col] = df[col].astype(int)

    return df
