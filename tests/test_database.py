"""Tests for src/database/db.py -- upsert behavior, the thing everything
else (rerunnable collectors, safe daily updates) depends on being correct."""

import sqlite3

import pandas as pd
import pytest

from src.database import db as db_module

TEAM_COLUMNS = ["team_abbrev", "team_name", "common_name", "place_name", "conference_name", "division_name"]


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the database module at a throwaway SQLite file for this test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    return db_path


def _team_row(abbrev: str, division: str = "Atlantic") -> pd.DataFrame:
    return pd.DataFrame([{
        "team_abbrev": abbrev,
        "team_name": f"{abbrev} Team",
        "common_name": abbrev,
        "place_name": abbrev,
        "conference_name": "Eastern",
        "division_name": division,
    }])


def test_upsert_creates_rows(temp_db):
    df = pd.concat([_team_row("TOR"), _team_row("MTL")], ignore_index=True)
    with db_module.get_connection() as conn:
        count = db_module.upsert_dataframe(conn, "teams", df, pk_columns=["team_abbrev"])
        row_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]

    assert count == 2
    assert row_count == 2


def test_upsert_is_idempotent_on_rerun(temp_db):
    """Re-upserting identical rows must not duplicate them -- this is what
    makes it safe to rerun collectors/build_database.py daily."""
    df = _team_row("TOR")
    with db_module.get_connection() as conn:
        db_module.upsert_dataframe(conn, "teams", df, pk_columns=["team_abbrev"])
        db_module.upsert_dataframe(conn, "teams", df, pk_columns=["team_abbrev"])
        row_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]

    assert row_count == 1


def test_upsert_updates_changed_values_in_place(temp_db):
    """A second upsert with new values should update the row, not add one."""
    with db_module.get_connection() as conn:
        db_module.upsert_dataframe(conn, "teams", _team_row("TOR", division="Atlantic"), pk_columns=["team_abbrev"])
        db_module.upsert_dataframe(conn, "teams", _team_row("TOR", division="Metropolitan"), pk_columns=["team_abbrev"])
        row_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        division = conn.execute("SELECT division_name FROM teams WHERE team_abbrev = 'TOR'").fetchone()[0]

    assert row_count == 1
    assert division == "Metropolitan"


def test_upsert_rejects_duplicate_pks_within_same_dataframe(temp_db):
    """Two rows with the same PK in one DataFrame is ambiguous -- fail loudly
    instead of silently picking one and dropping the other."""
    df = pd.concat([_team_row("TOR", "Atlantic"), _team_row("TOR", "Metropolitan")], ignore_index=True)
    with db_module.get_connection() as conn:
        with pytest.raises(ValueError, match="share a primary key"):
            db_module.upsert_dataframe(conn, "teams", df, pk_columns=["team_abbrev"])


def test_upsert_empty_dataframe_is_a_noop(temp_db):
    df = pd.DataFrame(columns=TEAM_COLUMNS)
    with db_module.get_connection() as conn:
        count = db_module.upsert_dataframe(conn, "teams", df, pk_columns=["team_abbrev"])

    assert count == 0


def test_foreign_key_violation_is_rejected(temp_db):
    """games.home_team/away_team must reference an existing team."""
    game = pd.DataFrame([{
        "game_id": 1, "season": 20252026, "game_type": 2, "game_date": "2025-10-08",
        "start_time_utc": "2025-10-08T23:00:00Z", "game_state": "OFF", "venue": "Test Arena",
        "away_team": "ZZZ", "away_score": 2, "home_team": "ZZZ", "home_score": 5,
    }])
    with db_module.get_connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            db_module.upsert_dataframe(conn, "games", game, pk_columns=["game_id"])
