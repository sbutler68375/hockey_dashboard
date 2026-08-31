"""Predict a home-team win probability for a matchup.

Usage:
    venv\\Scripts\\python.exe scripts\\predict_game.py --home TOR --away MTL --date 2026-04-20

See src/models/predict.py for the important caveat: since only the
already-completed 2025-26 season is collected, this predicts a
hypothetical matchup using each team's most recent known form, not a
real scheduled game.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.predict import DEFAULT_MODEL, predict_matchup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, help="Home team abbreviation, e.g. TOR")
    parser.add_argument("--away", required=True, help="Away team abbreviation, e.g. MTL")
    parser.add_argument("--date", required=True, help="Hypothetical game date, YYYY-MM-DD")
    parser.add_argument("--season", type=int, default=20252026)
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=["logistic_regression", "random_forest", "xgboost"])
    args = parser.parse_args()

    result = predict_matchup(args.home, args.away, args.date, args.season, args.model)

    print(f"\n{result['away_team']} @ {result['home_team']} on {result['game_date']} ({result['model']})")
    print(f"Home win probability: {result['home_win_probability']:.1%}")


if __name__ == "__main__":
    main()
