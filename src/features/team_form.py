"""Per-team rolling form features, built with leakage prevention as the
central design constraint: every rolling/aggregate stat for a given game
is computed using `.shift(1)` before the rolling window, so it only ever
sees that team's STRICTLY EARLIER games in the same season. The game
being featured is never included in its own features.

Rolling/expanding stats are computed via groupby(...).transform(...),
which guarantees the result stays aligned to the original row order
regardless of internal sort order -- important here because a manual
groupby -> rolling -> reset_index chain can silently misalign rows if
group ordering assumptions turn out to be wrong.
"""

import pandas as pd

ROLLING_WINDOWS = {"last_5": 5, "last_10": 10}
GROUP_COLS = ["team_abbrev", "season"]


def build_team_game_log(games: pd.DataFrame) -> pd.DataFrame:
    """Reshape one-row-per-game into two rows per game (one per team).

    Args:
        games: DataFrame with columns game_id, season, game_date,
            home_team, home_score, away_team, away_score (as produced
            by get_completed_games()).

    Returns:
        Long-format DataFrame: one row per (game, team), with that
        team's perspective -- goals_for, goals_against, win, is_home.
    """
    home = games.rename(columns={
        "home_team": "team_abbrev", "away_team": "opponent",
        "home_score": "goals_for", "away_score": "goals_against",
    }).copy()
    home["is_home"] = 1

    away = games.rename(columns={
        "away_team": "team_abbrev", "home_team": "opponent",
        "away_score": "goals_for", "home_score": "goals_against",
    }).copy()
    away["is_home"] = 0

    columns = ["game_id", "season", "game_date", "team_abbrev", "opponent",
               "goals_for", "goals_against", "is_home"]
    log = pd.concat([home[columns], away[columns]], ignore_index=True)
    log["win"] = (log["goals_for"] > log["goals_against"]).astype(int)
    log["game_date"] = pd.to_datetime(log["game_date"])
    log = log.sort_values(GROUP_COLS + ["game_date"]).reset_index(drop=True)
    return log


def _shifted_rolling(df: pd.DataFrame, column: str, window: int) -> pd.Series:
    """Per (team, season) group: shift the column by 1, then take a
    rolling mean. shift(1) is what excludes the current game from its
    own feature; transform() keeps the result aligned to df's rows."""
    return df.groupby(GROUP_COLS)[column].transform(
        lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
    )


def add_rolling_form_features(team_log: pd.DataFrame) -> pd.DataFrame:
    """Add leakage-safe rolling and rest-day features to a team game log.

    All rolling stats use games strictly before the current row within
    the same team and season -- a new season never inherits rolling
    history from the previous one.
    """
    df = team_log.copy()

    # How many prior games (this season) this team has played going into
    # this game -- lets downstream code decide how much to trust rolling
    # stats built on very little history.
    df["games_played_prior"] = df.groupby(GROUP_COLS).cumcount()

    for label, window in ROLLING_WINDOWS.items():
        df[f"win_pct_{label}"] = _shifted_rolling(df, "win", window)
        df[f"goals_for_avg_{label}"] = _shifted_rolling(df, "goals_for", window)
        df[f"goals_against_avg_{label}"] = _shifted_rolling(df, "goals_against", window)

    # Season-to-date (expanding window), same shift-before-aggregate rule.
    df["win_pct_season_to_date"] = df.groupby(GROUP_COLS)["win"].transform(
        lambda s: s.shift(1).expanding().mean()
    )

    # Rest days: gap since this team's previous game *this season*.
    # NaN for a team's first game of the season -- there's no meaningful
    # "rest" value to give it, so it's left unset rather than guessed.
    prev_game_date = df.groupby(GROUP_COLS)["game_date"].shift(1)
    df["rest_days"] = (df["game_date"] - prev_game_date).dt.days
    back_to_back = (df["rest_days"] <= 1).astype("boolean")
    back_to_back[df["rest_days"].isna()] = pd.NA
    df["back_to_back"] = back_to_back

    return df
