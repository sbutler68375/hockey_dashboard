"""Post-import validation: row counts, null primary keys, duplicate keys,
and foreign key integrity. Run after every import so problems surface
immediately instead of silently corrupting downstream features/models.
"""

import sqlite3

from src.database.db import get_connection
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# table -> primary key columns, used for null/duplicate checks
TABLE_PKS = {
    "teams": ["team_abbrev"],
    "standings": ["team_abbrev", "date"],
    "team_season_stats": ["team_abbrev", "season"],
    "games": ["game_id"],
    "players": ["player_id", "team_abbrev", "season"],
}


def _check_null_pks(conn: sqlite3.Connection, table: str, pk_columns: list[str]) -> int:
    conditions = " OR ".join(f"{col} IS NULL" for col in pk_columns)
    count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {conditions}").fetchone()[0]
    return count


def _check_duplicate_pks(conn: sqlite3.Connection, table: str, pk_columns: list[str]) -> int:
    cols = ", ".join(pk_columns)
    query = f"""
        SELECT COUNT(*) FROM (
            SELECT {cols} FROM {table} GROUP BY {cols} HAVING COUNT(*) > 1
        )
    """
    return conn.execute(query).fetchone()[0]


def validate_all() -> bool:
    """Run all validation checks and log a pass/fail summary for each table.

    Returns True if every check passed, False if any table had a problem.
    """
    all_ok = True

    with get_connection() as conn:
        for table, pk_columns in TABLE_PKS.items():
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            null_pks = _check_null_pks(conn, table, pk_columns)
            dup_pks = _check_duplicate_pks(conn, table, pk_columns)

            status = "OK"
            if null_pks or dup_pks:
                status = "FAILED"
                all_ok = False

            logger.info(
                "%s: %d rows | null PKs: %d | duplicate PKs: %d | %s",
                table, row_count, null_pks, dup_pks, status,
            )

        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_violations:
            all_ok = False
            logger.error("Foreign key violations found: %s", fk_violations)
        else:
            logger.info("Foreign key check: OK (no orphaned references)")

    return all_ok
