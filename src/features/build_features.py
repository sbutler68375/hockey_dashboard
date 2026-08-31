"""Build the ML-ready features table from completed regular-season games.

Scope decisions (see Phase 3 discussion -- documented here, not silent):
- Regular season games only (game_type=2). Playoffs are structurally
  different (elimination context) and preseason isn't representative;
  both excluded from training data for now.
- Targets are prefixed `target_` so it's unambiguous which columns are
  labels vs. features -- nothing here should ever be fed to a model as
  an input feature.
- No goalie-specific features yet (no starting-goalie data collected)
  and no player-points target (no per-game player logs collected) --
  both would require new collectors, not built in this pass.
"""

from pathlib import Path

import pandas as pd

from src.database.queries import get_completed_games
from src.features.team_form import add_rolling_form_features, build_team_game_log
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"

# Base (pre-prefix) rolling-feature names, as produced by team_form.py --
# NOT the same thing as src.models.dataset.FEATURE_COLUMNS, which is the
# final list of home_/away_-prefixed columns actually fed to a model.
ROLLING_FEATURE_NAMES = [
    "games_played_prior", "win_pct_last_5", "win_pct_last_10", "win_pct_season_to_date",
    "goals_for_avg_last_5", "goals_for_avg_last_10",
    "goals_against_avg_last_5", "goals_against_avg_last_10",
    "rest_days", "back_to_back",
]


def _team_features_for_merge(team_features: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Select this team's per-game features and rename with a home_/away_ prefix
    so they can be merged onto the wide games table without name collisions."""
    cols = ["game_id", "team_abbrev"] + ROLLING_FEATURE_NAMES
    subset = team_features[cols].copy()
    rename = {c: f"{prefix}_{c}" for c in ROLLING_FEATURE_NAMES}
    rename["team_abbrev"] = f"{prefix}_team_check"  # sanity check column, dropped after merge
    return subset.rename(columns=rename)


def build_features() -> pd.DataFrame:
    """Run the full feature pipeline and return the resulting DataFrame."""
    games = get_completed_games(game_type=2)
    if games.empty:
        raise ValueError("No completed regular-season games found -- run scripts/build_database.py first.")
    logger.info("Loaded %d completed regular-season games.", len(games))

    team_log = build_team_game_log(games)
    team_features = add_rolling_form_features(team_log)

    # team_features has two rows per game_id (one per team's perspective) --
    # filter to the matching side *before* merging on game_id, otherwise
    # the merge duplicates/misaligns rows.
    home_features = _team_features_for_merge(team_features[team_features["is_home"] == 1], "home")
    away_features = _team_features_for_merge(team_features[team_features["is_home"] == 0], "away")

    features = games.copy()
    features = features.merge(home_features, on="game_id", how="left")
    features = features.merge(away_features, on="game_id", how="left")

    # Sanity check: confirm the merge matched the correct team's rows
    # (catches a join-key bug immediately instead of silently mixing
    # home/away features).
    mismatched_home = (features["home_team"] != features["home_team_check"]).sum()
    mismatched_away = (features["away_team"] != features["away_team_check"]).sum()
    if mismatched_home or mismatched_away:
        raise ValueError(
            f"Feature merge mismatch: {mismatched_home} home rows, "
            f"{mismatched_away} away rows joined to the wrong team's features."
        )
    features = features.drop(columns=["home_team_check", "away_team_check"])

    # Targets -- clearly separated and prefixed, never to be used as inputs.
    features["target_home_win"] = (features["home_score"] > features["away_score"]).astype(int)
    features["target_total_goals"] = features["home_score"] + features["away_score"]

    # A few cheap differential features -- often useful signal, derived
    # purely from already-leakage-safe columns.
    features["win_pct_last10_diff"] = features["home_win_pct_last_10"] - features["away_win_pct_last_10"]
    features["goals_for_avg_last10_diff"] = (
        features["home_goals_for_avg_last_10"] - features["away_goals_for_avg_last_10"]
    )
    features["rest_days_diff"] = features["home_rest_days"] - features["away_rest_days"]

    return features


def main() -> None:
    features = build_features()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "features.csv"
    features.to_csv(output_path, index=False)
    logger.info("Saved %s (%d rows, %d columns)", output_path, *features.shape)

    early_season_rows = (features["home_games_played_prior"] < 5).sum()
    logger.info(
        "%d/%d rows have <5 prior home-team games this season "
        "(rolling features are based on partial history for these).",
        early_season_rows, len(features),
    )
    null_counts = features[[c for c in features.columns if c.startswith(("home_", "away_"))]].isna().sum()
    logger.info("Null counts per feature column:\n%s", null_counts[null_counts > 0])


if __name__ == "__main__":
    main()
