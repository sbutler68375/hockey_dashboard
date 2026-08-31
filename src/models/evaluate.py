"""Classification evaluation metrics, shared across all models so every
model in the comparison report is scored identically."""

from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score


def evaluate_classifier(model: Any, X, y) -> dict[str, float]:
    """Score a fitted binary classifier on accuracy, log loss, and ROC-AUC.

    Args:
        model: A fitted sklearn-compatible classifier with predict/predict_proba.
        X: Feature matrix.
        y: True binary labels.

    Returns:
        Dict with keys "accuracy", "log_loss", "roc_auc".
    """
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]

    return {
        "accuracy": accuracy_score(y, y_pred),
        "log_loss": log_loss(y, y_proba),
        "roc_auc": roc_auc_score(y, y_proba),
    }


def majority_class_baseline(y_train, y_eval) -> dict[str, float]:
    """A "always predict the more common class" baseline -- the floor
    every real model needs to beat to be worth using at all.

    Uses y_train's majority class (not y_eval's) to decide which class
    to always predict, matching how a real deployed model would work
    (you don't get to see the answer set in advance).
    """
    majority_class = int(round(y_train.mean()))
    baseline_rate = y_train.mean() if majority_class == 1 else 1 - y_train.mean()
    y_pred = np.full(len(y_eval), majority_class)
    y_proba = np.full(len(y_eval), baseline_rate)

    return {
        "accuracy": accuracy_score(y_eval, y_pred),
        "log_loss": log_loss(y_eval, y_proba, labels=[0, 1]),
        "roc_auc": float("nan"),  # undefined for a constant predictor
    }
