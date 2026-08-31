"""Tests for src/database/queries.py -- catches the kind of join/column
bug that only shows up once a dashboard page actually reads the result
(see get_standings, which needs a join to teams for conference/division)."""

import pandas as pd
import pytest

from src.database import db as db_module
from src.database.queries import get_standings


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()

    teams = pd.DataFrame([
        {"team_abbrev": "TOR", "team_name": "Maple Leafs", "common_name": "Maple Leafs",
         "place_name": "Toronto", "conference_name": "Eastern", "division_name": "Atlantic"},
        {"team_abbrev": "COL", "team_name": "Avalanche", "common_name": "Avalanche",
         "place_name": "Colorado", "conference_name": "Western", "division_name": "Central"},
    ])
    standings = pd.DataFrame([
        {"team_abbrev": "TOR", "date": "2026-04-17", "season_id": 20252026, "games_played": 82,
         "wins": 40, "losses": 30, "ot_losses": 12, "ties": 0, "points": 92, "point_pctg": 0.561,
         "goal_for": 250, "goal_against": 240, "goal_differential": 10,
         "home_wins": 20, "home_losses": 15, "home_ot_losses": 6, "home_points": 46,
         "road_wins": 20, "road_losses": 15, "road_ot_losses": 6, "road_points": 46,
         "l10_wins": 6, "l10_losses": 3, "l10_ot_losses": 1, "l10_points": 13,
         "streak_code": "W", "streak_count": 2},
        {"team_abbrev": "COL", "date": "2026-04-17", "season_id": 20252026, "games_played": 82,
         "wins": 55, "losses": 16, "ot_losses": 11, "ties": 0, "points": 121, "point_pctg": 0.738,
         "goal_for": 302, "goal_against": 203, "goal_differential": 99,
         "home_wins": 26, "home_losses": 9, "home_ot_losses": 6, "home_points": 58,
         "road_wins": 29, "road_losses": 7, "road_ot_losses": 5, "road_points": 63,
         "l10_wins": 7, "l10_losses": 2, "l10_ot_losses": 1, "l10_points": 15,
         "streak_code": "W", "streak_count": 3},
    ])

    with db_module.get_connection() as conn:
        db_module.upsert_dataframe(conn, "teams", teams, pk_columns=["team_abbrev"])
        db_module.upsert_dataframe(conn, "standings", standings, pk_columns=["team_abbrev", "date"])


def test_get_standings_includes_conference_and_division(seeded_db):
    """The dashboard's Standings page filters on these columns -- if the
    join breaks, that filter silently returns nothing instead of erroring."""
    result = get_standings()

    assert "conference_name" in result.columns
    assert "division_name" in result.columns
    tor_row = result[result["team_abbrev"] == "TOR"].iloc[0]
    assert tor_row["conference_name"] == "Eastern"
    assert tor_row["division_name"] == "Atlantic"


def test_get_standings_orders_by_points_descending(seeded_db):
    result = get_standings()
    assert result["team_abbrev"].tolist() == ["COL", "TOR"]  # COL has more points
