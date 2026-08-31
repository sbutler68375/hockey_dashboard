"""Predict a home-team win probability for a matchup using each team's
current form.

Important limitation, stated plainly: we've only collected the
2025-26 season, which is fully completed (see src/utils/constants.py).
There is no real *upcoming* game to predict against yet -- that would
require collecting the 2026-27 schedule once it has enough games
played to build meaningful rolling form (a brand-new season's opener
has no current-season history, by the same leakage-safe design used in
training -- see src/features/team_form.py). Until then, this treats a
user-supplied game_date as a hypothetical "what if these two teams
played on this date" query using their most recent known form.
"""

from pathlib import Path

import joblib
import pandas as pd

from src.database.queries import get_completed_games
from src.features.team_form import build_team_game_log
from src.models.dataset import FEATURE_COLUMNS
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
DEFAULT_MODEL = "random_forest"


def _current_team_form(team_log: pd.DataFrame, team_abbrev: str, season: int) -> dict:
    """Actual (non-shifted) rolling form for a team, as of after all its
    games played so far this season -- i.e. "current form heading into
    a hypothetical next game," not a training-time leakage-safe feature."""
    team_games = team_log[
        (team_log["team_abbrev"] == team_abbrev) & (team_log["season"] == season)
    ].sort_values("game_date")

    if team_games.empty:
        raise ValueError(f"No games found for {team_abbrev} in season {season}.")

    last_5, last_10 = team_games.tail(5), team_games.tail(10)
    return {
        "games_played_prior": len(team_games),
        "win_pct_last_5": last_5["win"].mean(),
        "win_pct_last_10": last_10["win"].mean(),
        "win_pct_season_to_date": team_games["win"].mean(),
        "goals_for_avg_last_5": last_5["goals_for"].mean(),
        "goals_for_avg_last_10": last_10["goals_for"].mean(),
        "goals_against_avg_last_5": last_5["goals_against"].mean(),
        "goals_against_avg_last_10": last_10["goals_against"].mean(),
        "last_game_date": team_games["game_date"].iloc[-1],
    }


def predict_matchup(
    home_team: str,
    away_team: str,
    game_date: str,
    season: int = 20252026,
    model_name: str = DEFAULT_MODEL,
) -> dict:
    """Predict a home-team win probability for a hypothetical matchup.

    Args:
        home_team, away_team: Team abbreviations (e.g. "TOR", "MTL").
        game_date: Hypothetical game date, "YYYY-MM-DD". Used only to
            compute rest_days relative to each team's last known game.
        season: Season to pull current form from.
        model_name: Which saved model to use (see models/*.joblib).

    Returns:
        Dict with home_win_probability and the feature vector used,
        so predictions are auditable, not a black box.
    """
    game_date = pd.Timestamp(game_date)
    games = get_completed_games(game_type=2)
    team_log = build_team_game_log(games)

    home_form = _current_team_form(team_log, home_team, season)
    away_form = _current_team_form(team_log, away_team, season)

    home_rest = (game_date - home_form.pop("last_game_date")).days
    away_rest = (game_date - away_form.pop("last_game_date")).days
    for label, rest in [("home", home_rest), ("away", away_rest)]:
        if rest > 10:
            logger.warning(
                "%s team's last known game was %d days before %s -- likely "
                "spans an offseason gap, so rest_days/back_to_back for this "
                "side are not meaningful.", label, rest, game_date.date(),
            )

    features = {f"home_{k}": v for k, v in home_form.items()}
    features.update({f"away_{k}": v for k, v in away_form.items()})
    features["home_rest_days"] = home_rest
    features["away_rest_days"] = away_rest
    features["home_back_to_back"] = int(home_rest <= 1)
    features["away_back_to_back"] = int(away_rest <= 1)
    features["win_pct_last10_diff"] = features["home_win_pct_last_10"] - features["away_win_pct_last_10"]
    features["goals_for_avg_last10_diff"] = (
        features["home_goals_for_avg_last_10"] - features["away_goals_for_avg_last_10"]
    )
    features["rest_days_diff"] = home_rest - away_rest

    X = pd.DataFrame([features])[FEATURE_COLUMNS]

    model_path = MODELS_DIR / f"home_win_{model_name}_v1.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"{model_path} not found -- run scripts/train_models.py first.")
    model = joblib.load(model_path)

    probability = model.predict_proba(X)[0, 1]
    return {
        "home_team": home_team,
        "away_team": away_team,
        "game_date": str(game_date.date()),
        "model": model_name,
        "home_win_probability": float(probability),
        "features_used": features,
    }
