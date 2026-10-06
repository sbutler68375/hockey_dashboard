"""Hockey AI Analytics Platform -- dashboard entrypoint.

Run from the project root:
    venv\\Scripts\\python.exe -m streamlit run dashboard\\Home.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data import (
    current_season,
    load_completed_games,
    load_standings,
    page_header,
    refresh_all_data,
    season_label,
)
from dashboard.style import apply_theme, section_label

st.set_page_config(page_title="Hockey Analytics Platform", page_icon="🏒", layout="wide")
apply_theme()

season = page_header("Hockey Analytics Platform")
st.caption(
    "NHL data collection, storage, feature engineering, and prediction modeling -- "
    "built end-to-end from the public NHL API."
)

with st.sidebar:
    st.header("Data")
    if st.button("Refresh all data", width="stretch"):
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
    standings = load_standings(season)
    games = load_completed_games(season, game_type=2)
except Exception as exc:
    st.error(
        f"Couldn't load data from the database: {exc}\n\n"
        "Have you run scripts/build_database.py yet? See README.md."
    )
    st.stop()

with st.container(border=True):
    section_label("Season snapshot")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Teams tracked", len(standings))
    col2.metric("Regular-season games", len(games))
    col3.metric("Season", season_label(season))
    if not standings.empty:
        as_of_label = "Standings as of" if season == current_season() else "Final standings as of"
        col4.metric(as_of_label, standings["date"].iloc[0])
