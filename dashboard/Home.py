"""Hockey AI Analytics Platform -- dashboard entrypoint.

Run from the project root:
    venv\\Scripts\\python.exe -m streamlit run dashboard\\Home.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data import (
    default_season,
    load_completed_games,
    load_standings,
    refresh_all_data,
)

st.set_page_config(page_title="Hockey AI Analytics Platform", page_icon="🏒", layout="wide")

st.title("🏒 Hockey AI Analytics Platform")
st.caption(
    "NHL data collection, storage, feature engineering, and prediction modeling -- "
    "built end-to-end from the public NHL API."
)

with st.sidebar:
    st.header("Data")
    if st.button("🔄 Refresh all data", use_container_width=True):
        progress = st.empty()
        with st.spinner("Refreshing..."):
            def show_progress(step: str) -> None:
                progress.text(step)
            log = refresh_all_data(progress_callback=show_progress)
        progress.empty()
        for line in log:
            if line.startswith("FAILED"):
                st.error(line)
            else:
                st.success(line)
        if all(line.startswith("OK") for line in log):
            st.rerun()
    st.caption(
        "Pulls fresh data from the NHL API, rebuilds the database, and "
        "regenerates model features. Takes ~30-60 seconds."
    )

try:
    standings = load_standings()
    games = load_completed_games(game_type=2)
except Exception as exc:
    st.error(
        f"Couldn't load data from the database: {exc}\n\n"
        "Have you run scripts/build_database.py yet? See README.md."
    )
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Teams tracked", len(standings))
col2.metric("Regular-season games", len(games))
col3.metric("Season", default_season())
if not standings.empty:
    col4.metric("Standings as of", standings["date"].iloc[0])

st.divider()

st.subheader("League standings (top 10 by points)")
if standings.empty:
    st.info("No standings data yet -- click 'Refresh all data' in the sidebar.")
else:
    top10 = standings.sort_values("points", ascending=False).head(10)
    st.dataframe(
        top10[["team_abbrev", "wins", "losses", "ot_losses", "points", "goal_for", "goal_against"]],
        column_config={
            "team_abbrev": "Team", "wins": "W", "losses": "L", "ot_losses": "OTL",
            "points": "PTS", "goal_for": "GF", "goal_against": "GA",
        },
        hide_index=True,
        use_container_width=True,
    )

st.divider()
st.markdown(
    "**Pages:** use the sidebar to explore full standings, team profiles and form trends, "
    "player stats, game history, and matchup predictions."
)

with st.expander("About this project / known limitations"):
    st.markdown(
        "- Data comes from the NHL's unofficial public API -- no key required, but not "
        "officially documented or guaranteed stable.\n"
        "- Only the completed 2025-26 season is collected. The 2026-27 season hasn't "
        "started, so there's no live/upcoming schedule loaded yet.\n"
        "- Prediction models are intentionally simple (box-score-derived features only, "
        "no starting-goalie or special-teams data) and perform modestly better than a "
        "coin flip -- see the Predictions page for honest metrics, not just a probability."
    )
