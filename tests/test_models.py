"""Tests for the ML pipeline's supporting logic: the time-aware split
(easy to accidentally shuffle), the baseline (easy to accidentally
peek at eval data when deciding which class to always predict)."""

import pandas as pd
import pytest

from src.models.evaluate import majority_class_baseline
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
