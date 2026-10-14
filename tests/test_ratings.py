"""Tests for the ratings models' snapshot building and verdicts
(src/models/team_ratings.py, player_ratings.py). Like test_features.py, the
key property is leakage safety: a snapshot's features may only use games
already played, while its target uses only games after it."""

import pandas as pd
import pytest

from src.models import player_ratings, team_ratings

NO_SPECIAL_TEAMS = pd.DataFrame({
    "game_id": pd.Series(dtype="int64"), "team_abbrev": pd.Series(dtype="object"),
    **{c: pd.Series(dtype="int64") for c in
       ["pp_goals", "pp_opportunities", "pp_goals_against", "times_shorthanded"]},
})


def _team_season(team: str, season: int, points: list[int], shots_for: int = 30,
                 shots_against: int = 30) -> pd.DataFrame:
    """One team's season of team_games rows, one per entry in points."""
    n = len(points)
    return pd.DataFrame({
        "game_id": [season * 1000 + i for i in range(n)],
        "team_abbrev": team, "opponent_abbrev": "OPP", "season": season,
        "game_date": pd.date_range("2025-10-01", periods=n).strftime("%Y-%m-%d"),
        "home_road": "H", "points": points,
        "goals_for": [3 if p == 2 else 2 for p in points],
        "goals_against": [2 if p == 2 else 3 for p in points],
        "shots_for": shots_for, "shots_against": shots_against,
        "shot_attempts_for": 55, "shot_attempts_against": 55,
        "sat_pct_5v5": 0.5, "shooting_pct_5v5": 0.08, "save_pct_5v5": 0.92,
    })


def _snapshot(snaps: pd.DataFrame, games_played: int) -> pd.Series:
    return snaps[snaps["games_played"] == games_played].iloc[0]


def test_team_features_use_only_games_played_so_far():
    """Win the first 5, lose the rest: after game 5, points % is 1.0 -- the
    losses still to come must not leak into it."""
    points = [2] * 5 + [0] * 25
    snaps = team_ratings.build_snapshots(_team_season("TOR", 20252026, points), NO_SPECIAL_TEAMS)

    assert _snapshot(snaps, 5)["points_pct"] == 1.0
    assert _snapshot(snaps, 10)["points_pct"] == 0.5


def test_team_target_is_rest_of_season_points_pct():
    """After game 5 of 30, the target is points % over games 6-30; once fewer
    than 20 games remain there's no target (too few games to average)."""
    points = [2] * 5 + [1] * 25
    snaps = team_ratings.build_snapshots(_team_season("TOR", 20252026, points), NO_SPECIAL_TEAMS)

    assert _snapshot(snaps, 5)[team_ratings.SPEC.target] == pytest.approx(0.5)
    assert pd.isna(_snapshot(snaps, 11)[team_ratings.SPEC.target])  # 19 games left


def test_team_recent_features_cover_only_the_last_10_games():
    points = [0] * 10 + [2] * 10
    snaps = team_ratings.build_snapshots(_team_season("TOR", 20252026, points), NO_SPECIAL_TEAMS)

    latest = _snapshot(snaps, 20)
    assert latest["points_pct"] == 0.5
    assert latest["recent_points_pct"] == 1.0


def test_relocated_team_gets_its_predecessors_previous_season():
    """Utah's first season carries over Arizona's final points %."""
    games = pd.concat([
        _team_season("ARI", 20232024, [2] * 15 + [0] * 15),  # .500 season
        _team_season("UTA", 20242025, [1] * 30),
    ])
    snaps = team_ratings.build_snapshots(games, NO_SPECIAL_TEAMS)
    utah = snaps[snaps["team_abbrev"] == "UTA"]

    assert (utah["prior_points_pct"] == 0.5).all()
    assert snaps.loc[snaps["team_abbrev"] == "ARI", "prior_points_pct"].isna().all()


class _ShotShareModel:
    """Stand-in model whose 'expected points %' is just the team's shot share."""

    def predict(self, X: pd.DataFrame):
        return X["shot_share"].to_numpy()


def test_team_verdicts_compare_standings_rank_with_model_rank():
    """Team 0 has the best record but the worst shot share (model rank last):
    overrated. Team 13 is the reverse: underrated. Mid-table teams whose two
    ranks are close are fair."""
    games = pd.concat([
        _team_season(f"T{i:02d}", 20252026, [2] * (30 - 2 * i) + [0] * (2 * i),
                     shots_for=20 + i, shots_against=33 - i)
        for i in range(14)
    ])
    snaps = team_ratings.build_snapshots(games, NO_SPECIAL_TEAMS)
    ratings, _ = team_ratings.score(_ShotShareModel(), snaps)
    verdict = ratings.set_index("team_abbrev")["verdict"]

    assert verdict["T00"] == "Overrated"
    assert verdict["T13"] == "Underrated"
    assert verdict["T06"] == "Fair"


def _player_season(player_id: int, season: int, points: list[int]) -> pd.DataFrame:
    n = len(points)
    return pd.DataFrame({
        "player_id": player_id, "game_id": [season * 1000 + i for i in range(n)],
        "season": season, "game_date": pd.date_range("2025-10-01", periods=n).strftime("%Y-%m-%d"),
        "team_abbrev": "TOR", "opponent_abbrev": "OPP", "player_name": "Test Player",
        "position_code": "C", "goals": 0, "assists": points, "points": points, "pp_points": 0,
        "shots": 2, "toi_seconds": 1080, "ev_toi_seconds": 900, "pp_toi_seconds": 120,
        "sh_toi_seconds": 60, "shifts": 20,
    })


def test_player_target_is_points_per_game_over_next_20_games():
    """Pointless for 5 games, then a point a game: after game 5 the target
    (next 20 games) is 1.0 while the feature (so far) is still 0."""
    snaps = player_ratings.build_snapshots(_player_season(1, 20252026, [0] * 5 + [1] * 30))
    after_5 = _snapshot(snaps, 5)

    assert after_5["points_per_game"] == 0
    assert after_5[player_ratings.SPEC.target] == 1.0
    assert pd.isna(_snapshot(snaps, 16)[player_ratings.SPEC.target])  # 19 games left


def test_player_prior_season_comes_from_his_previous_season():
    games = pd.concat([
        _player_season(1, 20242025, [1, 0] * 10),  # 0.5 points per game over 20 games
        _player_season(1, 20252026, [0] * 10),
    ])
    snaps = player_ratings.build_snapshots(games)
    this_season = snaps[snaps["season"] == 20252026]

    assert (this_season["prior_points_per_game"] == 0.5).all()
    assert (this_season["prior_games_played"] == 20).all()
