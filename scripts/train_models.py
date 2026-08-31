"""Train and compare baseline models for predicting home-team wins.

Run from the project root, after scripts/generate_features.py:
    venv\\Scripts\\python.exe scripts\\train_models.py

Saves trained models to models/*.joblib and a metrics comparison to
models/evaluation_report.json.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.train import main

if __name__ == "__main__":
    main()
