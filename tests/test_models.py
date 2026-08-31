"""Tests for the ML pipeline's supporting logic: the time-aware split
(easy to accidentally shuffle) and the baseline (easy to accidentally
peek at eval data when deciding which class to always predict)."""

import numpy as np
import pandas as pd
import pytest

from src.models.evaluate import majority_class_baseline
from src.models.predict import _current_team_form
from src.models.split import time_aware_split


def test_time_aware_split_preserves_chronological_order():
    df = pd.DataFrame({
        "game_date": pd.date_range("2025-10-01", periods=100, freq="D"),
        "value": range(100),
    })
    train, val, test = time_aware_split(df, train_frac=0.7, val_frac=0.15)

    assert train["game_date"].max() <= val["game_date"].min()
    assert val["game_date"].max() <= test["game_date"].min()
    assert len(train) + len(val) + len(test) == len(df)


def test_time_aware_split_rejects_invalid_fractions():
    df = pd.DataFrame({"game_date": pd.date_range("2025-10-01", periods=10), "value": range(10)})
    with pytest.raises(ValueError):
        time_aware_split(df, train_frac=0.7, val_frac=0.4)


def test_majority_class_baseline_uses_train_majority_not_eval():
    """The baseline must decide which class to always predict from
    y_train, never from y_eval -- otherwise it's cheating by looking
    at the answers it's being scored against."""
    y_train = pd.Series([1, 1, 1, 1, 0])   # majority class = 1 (win)
    y_eval = pd.Series([0, 0, 0, 1])       # majority class here is 0

    result = majority_class_baseline(y_train, y_eval)

    # Always predicting 1 (train's majority) against y_eval gets 1/4 right.
    assert result["accuracy"] == pytest.approx(0.25)


def test_current_team_form_uses_only_that_teams_games_this_season():
    team_log = pd.DataFrame([
        {"team_abbrev": "TOR", "season": 2025, "game_date": pd.Timestamp("2025-10-08"), "win": 1, "goals_for": 5, "goals_against": 2},
        {"team_abbrev": "TOR", "season": 2025, "game_date": pd.Timestamp("2025-10-10"), "win": 0, "goals_for": 2, "goals_against": 4},
        {"team_abbrev": "MTL", "season": 2025, "game_date": pd.Timestamp("2025-10-09"), "win": 1, "goals_for": 3, "goals_against": 1},
    ])

    form = _current_team_form(team_log, "TOR", 2025)

    assert form["games_played_prior"] == 2
    assert form["win_pct_season_to_date"] == pytest.approx(0.5)
    assert form["last_game_date"] == pd.Timestamp("2025-10-10")


def test_current_team_form_raises_for_unknown_team():
    team_log = pd.DataFrame({
        "team_abbrev": ["TOR"], "season": [2025], "game_date": [pd.Timestamp("2025-10-08")],
        "win": [1], "goals_for": [5], "goals_against": [2],
    })
    with pytest.raises(ValueError, match="No games found"):
        _current_team_form(team_log, "MTL", 2025)
