"""Tests for feature engineering. Correctness of the leakage-safe rolling
logic is the single most important thing tested in this project -- a bug
here would silently make every downstream model look better than it is."""

import pandas as pd

from src.features.team_form import add_rolling_form_features, build_team_game_log


def _games(rows: list[tuple]) -> pd.DataFrame:
    """rows: (game_id, season, date, home, home_score, away, away_score)."""
    return pd.DataFrame(rows, columns=[
        "game_id", "season", "game_date", "home_team", "home_score", "away_team", "away_score",
    ])


def test_first_game_of_season_has_no_rolling_history():
    games = _games([(1, 2025, "2025-10-08", "TOR", 5, "MTL", 2)])
    features = add_rolling_form_features(build_team_game_log(games))

    assert (features["games_played_prior"] == 0).all()
    assert features["win_pct_last_5"].isna().all()
    assert features["rest_days"].isna().all()


def test_rolling_win_pct_excludes_the_current_game():
    """TOR wins game 1, loses games 2 and 3. Going into game 2, win_pct
    must reflect game 1 alone (1.0) -- NOT include game 2's own result,
    which would mean a game's outcome leaked into its own feature."""
    games = _games([
        (1, 2025, "2025-10-08", "TOR", 5, "MTL", 2),  # TOR wins
        (2, 2025, "2025-10-11", "DET", 6, "TOR", 3),  # TOR loses
        (3, 2025, "2025-10-13", "TOR", 2, "DET", 3),  # TOR loses
    ])
    features = add_rolling_form_features(build_team_game_log(games))
    tor = features[features["team_abbrev"] == "TOR"].sort_values("game_date").reset_index(drop=True)

    assert pd.isna(tor.loc[0, "win_pct_last_5"])
    assert tor.loc[1, "win_pct_last_5"] == 1.0
    assert tor.loc[2, "win_pct_last_5"] == 0.5


def test_rest_days_and_back_to_back():
    games = _games([
        (1, 2025, "2025-10-08", "TOR", 5, "MTL", 2),
        (2, 2025, "2025-10-09", "DET", 6, "TOR", 3),  # 1 day later -> back-to-back
        (3, 2025, "2025-10-13", "TOR", 2, "DET", 3),  # 4 days later -> not back-to-back
    ])
    features = add_rolling_form_features(build_team_game_log(games))
    tor = features[features["team_abbrev"] == "TOR"].sort_values("game_date").reset_index(drop=True)

    assert pd.isna(tor.loc[0, "rest_days"])
    assert tor.loc[1, "rest_days"] == 1
    assert tor.loc[1, "back_to_back"] == True
    assert tor.loc[2, "rest_days"] == 4
    assert tor.loc[2, "back_to_back"] == False


def test_new_season_does_not_inherit_previous_season_history():
    """A team's first game of a new season must not carry over form or
    rest-day figures from the end of the previous season."""
    games = _games([
        (1, 2025, "2026-04-01", "TOR", 5, "MTL", 2),  # last game of 2025 season
        (2, 2026, "2026-10-08", "TOR", 1, "MTL", 0),  # first game of 2026 season
    ])
    features = add_rolling_form_features(build_team_game_log(games))
    opener = features[(features["team_abbrev"] == "TOR") & (features["season"] == 2026)].iloc[0]

    assert opener["games_played_prior"] == 0
    assert pd.isna(opener["win_pct_last_5"])
    assert pd.isna(opener["rest_days"])  # must not report ~190 days of "rest" across an offseason
