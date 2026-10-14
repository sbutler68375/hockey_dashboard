"""Train (if needed) and run the team and player ratings models, saving the
results to the database for the dashboard.

Run from the project root, after build_database.py:
    venv\\Scripts\\python.exe scripts\\build_ratings.py            # score with saved models
    venv\\Scripts\\python.exe scripts\\build_ratings.py --retrain  # retrain first

Without --retrain, saved models in models/ are reused and only the scoring
runs (fast -- what the dashboard's Refresh button does). A model is trained
when it has no saved file yet. Retrain after adding a season (each fall,
once CURRENT_SEASON moves on) or whenever you change a model's features.

Training holds out the most recent completed season as the test set; see
src/models/pipelines.py. Evaluation reports land next to the models as
models/<name>_report.json.

Writes these tables (fully replaced each run -- they're derived, not raw data):
    team_ratings        -- one row per team per season, as of its latest game
    team_rating_history -- expected vs actual points % after every game
    player_ratings      -- one row per skater per season, as of his latest game
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.db import get_connection
from src.database.queries import get_all_player_games, get_all_team_games
from src.models import player_ratings, team_ratings
from src.models.pipelines import load_model, save_model, train_and_evaluate
from src.utils.constants import HISTORICAL_SEASONS
from src.utils.logging_config import get_logger

import pandas as pd

logger = get_logger(__name__)

TEST_SEASON = int(HISTORICAL_SEASONS[-1])  # most recent completed season


def _model(module, snapshots: pd.DataFrame, retrain: bool):
    """The module's saved model, training and saving one first if asked or missing."""
    model = None if retrain else load_model(module.SPEC)
    if model is None:
        logger.info("Training %s...", module.SPEC.name)
        model, report = train_and_evaluate(module.SPEC, snapshots, TEST_SEASON)
        save_model(module.SPEC, model, report)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--retrain", action="store_true", help="retrain both models before scoring")
    args = parser.parse_args()

    with get_connection() as conn:
        special_teams = pd.read_sql_query("SELECT * FROM team_game_special_teams", conn)
    team_snapshots = team_ratings.build_snapshots(get_all_team_games(), special_teams)
    team_model = _model(team_ratings, team_snapshots, args.retrain)
    ratings, history = team_ratings.score(team_model, team_snapshots)

    player_snapshots = player_ratings.build_snapshots(get_all_player_games())
    player_model = _model(
        player_ratings, player_ratings.training_rows(player_snapshots), args.retrain
    )
    players = player_ratings.score(player_model, player_snapshots)

    with get_connection() as conn:
        ratings.to_sql("team_ratings", conn, if_exists="replace", index=False)
        history.to_sql("team_rating_history", conn, if_exists="replace", index=False)
        players.to_sql("player_ratings", conn, if_exists="replace", index=False)
    logger.info("Saved ratings: %d team-seasons, %d skater-seasons.", len(ratings), len(players))


if __name__ == "__main__":
    main()
