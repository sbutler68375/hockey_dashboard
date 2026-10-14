"""Shared display helpers for the model ratings on the Team and Players pages
(the models themselves live in src/models/)."""

import pandas as pd
import streamlit as st

from dashboard.style import colors
from src.models.pipelines import load_report

# Verdict and trend words, colored like game results: green reads as good
# news for the team/player, red as bad news, gray as neutral.
GOOD_NEWS = {"Underrated", "Playing better"}
BAD_NEWS = {"Overrated", "Playing worse"}


def verdict_style(value) -> str:
    """Cell style for a verdict/trend word. Use with DataFrame.style.map."""
    c = colors()
    if value in GOOD_NEWS:
        return f"color: {c['positive']}; font-weight: 700"
    if value in BAD_NEWS:
        return f"color: {c['negative']}; font-weight: 700"
    return f"color: {c['text_muted']}"


def ordinal(n: int) -> str:
    """1 -> '1st', 12 -> '12th', 23 -> '23rd'."""
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def model_explainer(report_name: str, what_it_predicts: str, feature_labels: dict[str, str]) -> None:
    """A collapsed "How the ratings work" section: what the model predicts,
    how every candidate model scored on the held-out season against the
    baselines, and which inputs the chosen model leans on most."""
    report = load_report(report_name)
    with st.expander("How the ratings work"):
        if report is None:
            st.caption("No trained model yet -- run scripts/build_ratings.py.")
            return
        test_season = str(report["test_season"])
        st.markdown(
            f"A machine-learning model predicts {what_it_predicts} from how they've played "
            f"so far -- that prediction is the **expected** number. It was trained on "
            f"{', '.join(_season_label(s) for s in report['train_seasons'])} and tested on "
            f"{_season_label(test_season)}, a season it never saw. Several models were tuned "
            f"and compared by cross-validation; **{report['chosen']}** won. A model only earns "
            f"its place if it beats the baselines: the league average, and current results alone."
        )
        rows = [
            {"Model": name, "Average error": r["test"]["mae"], "R²": r["test"]["r2"],
             "Chosen": "✓" if name == report["chosen"] else ""}
            for name, r in report["candidates"].items()
        ]
        st.dataframe(
            pd.DataFrame(rows),
            column_config={
                "Average error": st.column_config.NumberColumn(
                    f"Average error ({_season_label(test_season)})", format="%.3f",
                    help="Mean absolute error on the held-out season -- lower is better."),
                "R²": st.column_config.NumberColumn(
                    format="%.2f", help="Share of the variation explained -- higher is better; 0 = no better than the average."),
            },
            hide_index=True, width="stretch",
        )
        top = [feature_labels.get(f, f) for f, v in report["feature_importance"].items() if v > 0][:5]
        if top:
            st.caption("What the model leans on most (shuffling these hurts its accuracy the most): "
                       + ", ".join(top) + ".")


def _season_label(season) -> str:
    """'20252026' -> '2025-26'."""
    s = str(season)
    return f"{s[:4]}-{s[6:]}"
