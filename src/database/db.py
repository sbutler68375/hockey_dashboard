"""SQLite connection handling and generic upsert logic.

Kept deliberately separate from src/api and collectors/ -- this module
knows nothing about the NHL API, and the collectors know nothing about
SQLite. Only the importers module (importers.py) bridges the two.
"""

import sqlite3
from pathlib import Path
from typing import Sequence

import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "nhl_database.db"
SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Open a connection to the project's SQLite database.

    Enables foreign key enforcement, which SQLite disables by default.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added to existing tables after they were first created. schema.sql
# only creates missing tables (CREATE TABLE IF NOT EXISTS), so a database
# built before a column existed gets it added here instead.
ADDED_COLUMNS = [
    ("games", "last_period_type", "TEXT"),
    ("team_season_stats", "power_play_pct", "REAL"),
    ("team_season_stats", "penalty_kill_pct", "REAL"),
]


def init_db() -> None:
    """Create all tables/indexes from schema.sql if they don't already exist,
    and add any columns in ADDED_COLUMNS that an older database is missing."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema_sql)
        for table, column, column_type in ADDED_COLUMNS:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                logger.info("Added column %s.%s", table, column)
    logger.info("Database schema ready at %s", DB_PATH)


def upsert_dataframe(
    conn: sqlite3.Connection,
    table: str,
    df: pd.DataFrame,
    pk_columns: Sequence[str],
) -> int:
    """Insert or update rows from a DataFrame into a table, keyed on pk_columns.

    Uses SQLite's `INSERT OR REPLACE`, so re-running an import with the
    same primary key values updates those rows instead of duplicating
    them -- this is what makes collectors safe to rerun daily.

    Args:
        conn: Open sqlite3 connection.
        table: Target table name (must already exist).
        df: Data to load. Column names must match table column names.
        pk_columns: Primary key column(s) for this table, used only for
            a pre-insert duplicate check and logging -- SQLite enforces
            the actual constraint via the schema.

    Returns:
        Number of rows written.

    Raises:
        ValueError: If df has duplicate primary keys within itself
            (as opposed to across runs, which INSERT OR REPLACE handles
            fine) -- that would silently pick one row and drop the rest,
            so we fail loudly instead.
    """
    if df.empty:
        logger.warning("upsert_dataframe called with an empty DataFrame for %s -- skipping.", table)
        return 0

    dup_mask = df.duplicated(subset=list(pk_columns), keep=False)
    if dup_mask.any():
        raise ValueError(
            f"{table}: {dup_mask.sum()} rows share a primary key "
            f"{list(pk_columns)} within the incoming data itself -- "
            "refusing to upsert ambiguous rows."
        )

    clean_df = df.where(pd.notnull(df), None)
    columns = list(clean_df.columns)
    placeholders = ", ".join(["?"] * len(columns))
    column_list = ", ".join(columns)
    sql = f"INSERT OR REPLACE INTO {table} ({column_list}) VALUES ({placeholders})"

    records = [tuple(row) for row in clean_df.itertuples(index=False, name=None)]
    with conn:
        conn.executemany(sql, records)

    logger.info("Upserted %d rows into %s.", len(records), table)
    return len(records)
