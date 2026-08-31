"""Matchup predictions -- shown alongside honest model-quality context,
not just a bare probability number. See src/models/predict.py and
models/evaluation_report.json for where these numbers come from."""

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import default_season, team_list
from src.models.predict import MODELS_DIR, predict_matchup

st.set_page_config(page_title="Predictions", page_icon="🏒", layout="wide")
st.title("Matchup Predictions")

st.warning(
    "**Read before trusting these numbers:** these models perform only modestly "
    "better than always guessing 'home team wins' (~52-57% accuracy vs. a ~50-53% "
    "baseline). They use box-score-derived features only -- no starting goalie, "
    "no special-teams data, and only one season of training history. Treat "
    "predictions as a rough signal, not a confident forecast. Full metrics below."
)

st.markdown(
    "Also note: the 2026-27 season hasn't started, so there's no real upcoming "
    "schedule loaded yet. This predicts a **hypothetical** matchup using each "
    "team's most recent known form from the 2025-26 season."
)

col1, col2, col3 = st.columns(3)
with col1:
    home_team = st.selectbox("Home team", team_list(), index=team_list().index("TOR") if "TOR" in team_list() else 0)
with col2:
    away_team = st.selectbox("Away team", [t for t in team_list() if t != home_team])
with col3:
    model_name = st.selectbox("Model", ["random_forest", "logistic_regression", "xgboost"], index=0)

game_date = st.date_input("Hypothetical game date")

if st.button("Predict", type="primary"):
    try:
        result = predict_matchup(home_team, away_team, str(game_date), default_season(), model_name)
    except Exception as exc:
        st.error(f"Couldn't generate a prediction: {exc}")
    else:
        prob = result["home_win_probability"]
        st.metric(f"{home_team} win probability", f"{prob:.1%}")
        st.progress(prob)
        st.caption(f"{away_team} win probability: {1 - prob:.1%}")

        with st.expander("Feature vector used (for transparency, not a black box)"):
            st.json(result["features_used"])

st.divider()
st.subheader("Model comparison (from the last training run)")

report_path = MODELS_DIR / "evaluation_report.json"
if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = []
    for name, result in report["results"].items():
        val, test = result["val"], result["test"]
        rows.append({
            "model": name,
            "val_accuracy": round(val["accuracy"], 3),
            "val_roc_auc": round(val["roc_auc"], 3) if val["roc_auc"] == val["roc_auc"] else None,
            "test_accuracy": round(test["accuracy"], 3),
            "test_roc_auc": round(test["roc_auc"], 3) if test["roc_auc"] == test["roc_auc"] else None,
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(
        "'majority_class_baseline' always predicts whichever outcome was more common "
        "in training data -- the floor every real model needs to beat."
    )
else:
    st.info("No evaluation report found -- run scripts/train_models.py first.")
