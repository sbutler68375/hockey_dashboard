"""Generate data/processed/features.csv from the database.

Run from the project root, after scripts/build_database.py:
    venv\\Scripts\\python.exe scripts\\generate_features.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.build_features import main

if __name__ == "__main__":
    main()
