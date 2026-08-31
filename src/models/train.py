"""Train and compare baseline models for target_home_win.

Models are trained in increasing complexity order (Logistic Regression
-> Random Forest -> XGBoost), each evaluated the same way, so it's
obvious whether the added complexity is actually earning its keep.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from src.models.dataset import FEATURE_COLUMNS, TARGET_COLUMN, load_model_dataset
from src.models.evaluate import evaluate_classifier, majority_class_baseline
from src.models.split import time_aware_split
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def get_model_candidates() -> dict:
    """Return the models to train, in increasing-complexity order."""
    return {
        "logistic_regression": LogisticRegression(max_iter=1000),
        "random_forest": RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42),
        "xgboost": XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            eval_metric="logloss", random_state=42,
        ),
    }


def train_and_compare() -> dict:
    """Train every candidate model, evaluate on val + test, and save results.

    Returns a report dict (also written to models/evaluation_report.json)
    with metrics for the baseline and every trained model.
    """
    df = load_model_dataset()
    train_df, val_df, test_df = time_aware_split(df)

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN]
    X_val, y_val = val_df[FEATURE_COLUMNS], val_df[TARGET_COLUMN]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[TARGET_COLUMN]

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_columns": FEATURE_COLUMNS,
        "split_sizes": {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
        "results": {},
    }

    baseline_val = majority_class_baseline(y_train, y_val)
    baseline_test = majority_class_baseline(y_train, y_test)
    report["results"]["majority_class_baseline"] = {"val": baseline_val, "test": baseline_test}
    logger.info("Baseline (always predict majority class) -- val: %s", baseline_val)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in get_model_candidates().items():
        logger.info("Training %s...", name)
        model.fit(X_train, y_train)

        val_metrics = evaluate_classifier(model, X_val, y_val)
        test_metrics = evaluate_classifier(model, X_test, y_test)
        report["results"][name] = {"val": val_metrics, "test": test_metrics}
        logger.info("%s -- val: %s", name, val_metrics)

        model_path = MODELS_DIR / f"home_win_{name}_v1.joblib"
        joblib.dump(model, model_path)
        logger.info("Saved %s", model_path)

    report_path = MODELS_DIR / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Saved evaluation report to %s", report_path)

    return report


def main() -> None:
    report = train_and_compare()

    print("\n=== Model comparison (val set) ===")
    print(f"{'model':<22}{'accuracy':>10}{'log_loss':>10}{'roc_auc':>10}")
    for name, result in report["results"].items():
        m = result["val"]
        auc = f"{m['roc_auc']:.3f}" if m["roc_auc"] == m["roc_auc"] else "n/a"  # NaN check
        print(f"{name:<22}{m['accuracy']:>10.3f}{m['log_loss']:>10.3f}{auc:>10}")


if __name__ == "__main__":
    main()
