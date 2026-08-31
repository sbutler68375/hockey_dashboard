"""Build/update the NHL database from collected CSVs.

Run from the project root, after the collectors have produced CSVs in
data/raw/:
    venv\\Scripts\\python.exe scripts\\build_database.py

This is the "automated update pipeline" -- safe to rerun any time new
CSVs are collected. Existing rows are updated in place (upsert), not
duplicated. In the future this is the script a scheduled task would
call daily.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.db import init_db
from src.database.importers import load_all
from src.database.validate import validate_all
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Initializing database schema...")
    init_db()

    logger.info("Importing collected data...")
    counts = load_all()
    for table, count in counts.items():
        logger.info("  %s: %d rows upserted", table, count)

    logger.info("Running validation checks...")
    ok = validate_all()

    if ok:
        logger.info("Database build complete -- all validation checks passed.")
    else:
        logger.error("Database build finished with validation FAILURES -- see above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
