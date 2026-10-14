"""Shared machine-learning plumbing for the team and player ratings models.

Both models answer the same kind of question -- "given how a team/player
has played so far this season, what should we expect from them next?" --
so they share one recipe:

1. Snapshots: one row per team (or player) per point in a season, with
   season-to-date features (built only from games already played) and a
   target from the games that came *after* it. Features never see the
   future, so the model can't cheat (no leakage).
2. Candidates: every model is a scikit-learn Pipeline -- preprocessing
   (fill missing values, scale numbers, one-hot encode categories) and the
   estimator in one object, so exactly the same steps run in training and
   when scoring this season. Two baselines are always included: the
   league average, and "current results only". A model is only worth
   using if it beats them.
3. Evaluation: the most recent completed season is held out as the test
   set. Hyperparameters are tuned with cross-validation on the earlier
   seasons, one season per fold (rows from the same season are related,
   so they must never be split between training and validation). The
   winner is chosen by cross-validation score, never by the test score;
   the test score is reported as the honest estimate of real-world error.
4. Production: the winning pipeline is refit on every season with a known
   target and saved with joblib, then reused to score the current season.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GridSearchCV, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"

RANDOM_STATE = 455  # fixed so retraining on the same data gives the same model


@dataclass
class ModelSpec:
    """What one ratings model predicts, and from which columns."""
    name: str                       # file stem, e.g. "team_ratings"
    target: str                     # column holding the future outcome
    numeric_features: list[str]
    categorical_features: list[str] = field(default_factory=list)
    baseline_feature: str = ""      # the "current results only" baseline's one input

    @property
    def features(self) -> list[str]:
        return self.numeric_features + self.categorical_features


def _preprocessor(spec: ModelSpec) -> ColumnTransformer:
    """Fill missing numbers with the median (plus a was-missing flag, e.g.
    'no previous season'), scale them, and one-hot encode categories.

    keep_empty_features: the oldest season has no previous season collected,
    so a cross-validation fold trained on it alone sees that column entirely
    empty -- keep it (as zeros, flagged missing) rather than dropping it and
    changing the feature count between folds."""
    transformers = [(
        "numeric",
        Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
        ]),
        spec.numeric_features,
    )]
    if spec.categorical_features:
        transformers.append(
            ("categorical", OneHotEncoder(handle_unknown="ignore"), spec.categorical_features)
        )
    return ColumnTransformer(transformers)


def candidate_pipelines(spec: ModelSpec) -> dict[str, tuple[Pipeline, dict]]:
    """name -> (pipeline, hyperparameter grid to search)."""
    baseline_input = ColumnTransformer(
        [("current", SimpleImputer(strategy="median"), [spec.baseline_feature])]
    )
    return {
        "League average (baseline)": (
            Pipeline([("prep", _preprocessor(spec)), ("model", DummyRegressor())]), {},
        ),
        "Current results only (baseline)": (
            Pipeline([("prep", baseline_input), ("model", LinearRegression())]), {},
        ),
        "Ridge regression": (
            Pipeline([("prep", _preprocessor(spec)), ("model", Ridge())]),
            {"model__alpha": [0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0]},
        ),
        "Random forest": (
            Pipeline([("prep", _preprocessor(spec)), ("model", RandomForestRegressor(
                n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1))]),
            {"model__max_depth": [4, 8, None], "model__min_samples_leaf": [5, 20, 50]},
        ),
        "XGBoost": (
            Pipeline([("prep", _preprocessor(spec)), ("model", XGBRegressor(
                n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1, verbosity=0))]),
            {"model__max_depth": [2, 4], "model__learning_rate": [0.03, 0.1],
             "model__min_child_weight": [5, 20]},
        ),
    }


def _metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(root_mean_squared_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_and_evaluate(spec: ModelSpec, snapshots: pd.DataFrame,
                       test_season: int) -> tuple[Pipeline, dict]:
    """Tune and compare every candidate, pick the best by cross-validation,
    report its held-out test error, and refit it on all labeled data.

    Args:
        snapshots: one row per snapshot with spec.features, spec.target
            (NaN where the future isn't known yet) and a "season" column.
        test_season: the season held out for the final test.

    Returns:
        (production pipeline, evaluation report dict).
    """
    labeled = snapshots.dropna(subset=[spec.target])
    train = labeled[labeled["season"] < test_season]
    test = labeled[labeled["season"] == test_season]
    if train["season"].nunique() < 2 or test.empty:
        raise ValueError(
            f"{spec.name}: need 2+ training seasons and a labeled test season "
            f"({test_season}) -- have {sorted(labeled['season'].unique())}."
        )
    X_train, y_train = train[spec.features], train[spec.target]
    X_test, y_test = test[spec.features], test[spec.target]

    results = {}
    searches = {}
    for name, (pipeline, grid) in candidate_pipelines(spec).items():
        search = GridSearchCV(
            pipeline, grid or {}, cv=LeaveOneGroupOut(),
            scoring="neg_mean_absolute_error", n_jobs=1,
        )
        search.fit(X_train, y_train, groups=train["season"])
        searches[name] = search
        results[name] = {
            "cv_mae": float(-search.best_score_),
            "best_params": {k.removeprefix("model__"): v for k, v in search.best_params_.items()},
            "test": _metrics(y_test, search.predict(X_test)),
        }
        logger.info("%s -- %s: CV MAE %.4f, test MAE %.4f", spec.name, name,
                    results[name]["cv_mae"], results[name]["test"]["mae"])

    chosen = min(results, key=lambda n: results[n]["cv_mae"])
    logger.info("%s: chose %s (lowest cross-validation error).", spec.name, chosen)

    # What the chosen model leans on, measured on the test season: how much
    # worse its error gets when one feature's values are shuffled.
    importance = permutation_importance(
        searches[chosen].best_estimator_, X_test, y_test,
        scoring="neg_mean_absolute_error", n_repeats=5, random_state=RANDOM_STATE,
    )
    feature_importance = dict(sorted(
        zip(spec.features, (float(v) for v in importance.importances_mean)),
        key=lambda kv: -kv[1],
    ))

    production = clone(searches[chosen].best_estimator_)
    production.fit(labeled[spec.features], labeled[spec.target])

    report = {
        "model": spec.name,
        "target": spec.target,
        "features": spec.features,
        "train_seasons": sorted(int(s) for s in train["season"].unique()),
        "test_season": int(test_season),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "production_rows": int(len(labeled)),
        "candidates": results,
        "chosen": chosen,
        "feature_importance": feature_importance,
    }
    return production, report


def save_model(spec: ModelSpec, pipeline: Pipeline, report: dict) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODELS_DIR / f"{spec.name}.joblib")
    (MODELS_DIR / f"{spec.name}_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Saved %s model and evaluation report to %s", spec.name, MODELS_DIR)


def load_model(spec: ModelSpec) -> Pipeline | None:
    path = MODELS_DIR / f"{spec.name}.joblib"
    return joblib.load(path) if path.exists() else None


def load_report(name: str) -> dict | None:
    path = MODELS_DIR / f"{name}_report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
