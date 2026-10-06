"""SESPN (Sean's ESPN) -- dashboard entrypoint.

Run from the project root:
    venv\\Scripts\\python.exe -m streamlit run dashboard\\Home.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data import page_header, refresh_all_data
from dashboard.style import apply_theme

st.set_page_config(page_title="SESPN", page_icon="🏒", layout="wide")
apply_theme()

page_header("SESPN")
st.caption(
    "Sean's ESPN -- NHL data collection, storage, feature engineering, and "
    "prediction modeling, built end-to-end from the public NHL API."
)

# Home page artwork: illustration with the background removed (transparent
# PNG), centered and capped to the window height (CSS in style.py) so the
# whole picture fits on screen without scrolling.
HERO_IMAGE = Path(__file__).resolve().parent / "assets" / "sespn_champion.png"
with st.container(key="home_hero"):
    st.image(str(HERO_IMAGE), width="content")

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
        "regenerates model features. Takes about 1-2 minutes."
    )
