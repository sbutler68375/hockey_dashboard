"""Full league standings, sortable and filterable by conference/division."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.data import load_standings, page_header
from dashboard.images import team_logo_url
from dashboard.style import COLORS, apply_theme, section_label

st.set_page_config(page_title="Standings", page_icon="🏒", layout="wide")
apply_theme()
season = page_header("Standings")

standings = load_standings(season)
if standings.empty:
    st.info("No standings data yet -- go to Home and click 'Refresh all data'.")
    st.stop()

standings = standings.copy()
standings["logo"] = standings["team_abbrev"].apply(team_logo_url)
# One "Streak" column like "2W" / "3L" instead of separate code and count.
# Overtime losses (NHL code "OT") are shown as losses.
standings["streak"] = [
    f"{int(count)}{'L' if code == 'OT' else code}" if pd.notna(code) and pd.notna(count) else ""
    for code, count in zip(standings["streak_code"], standings["streak_count"])
]

display_cols = [
    "logo", "team_abbrev", "wins", "losses", "ot_losses", "points", "point_pctg",
    "goal_for", "goal_against", "goal_differential", "streak",
]
display_cols = [c for c in display_cols if c in standings.columns]
column_config = {
    "logo": st.column_config.ImageColumn(""),
    "team_abbrev": "Team", "wins": "W", "losses": "L", "ot_losses": "OTL",
    "points": "PTS", "point_pctg": st.column_config.NumberColumn("PT%", format="%.3f"),
    "goal_for": "GF", "goal_against": "GA", "goal_differential": "DIFF",
    "streak": "Streak",
}

# Points decide the standings, so that column is highlighted: accent-colored
# bold numbers on a faint accent-tinted background.
POINTS_STYLE = {
    "color": COLORS["accent"],
    "font-weight": "700",
    "background-color": "rgba(59, 130, 246, 0.14)",
}


def show_table(df: pd.DataFrame, title: str | None = None) -> None:
    """Render one table as a card, full height, no inner scrollbar."""
    df = df.sort_values("points", ascending=False)
    with st.container(border=True):
        if title:
            section_label(title)
        st.dataframe(
            df[display_cols].style.set_properties(subset=["points"], **POINTS_STYLE),
            column_config=column_config,
            hide_index=True,
            width="stretch",
            height=35 * (len(df) + 1) + 3,
        )


if "standings_view" not in st.session_state:
    st.session_state["standings_view"] = "All"

view = st.session_state["standings_view"]

btn_all, btn_conf, btn_div = st.columns(3)
if btn_all.button("All", width="stretch", type="primary" if view == "All" else "secondary"):
    st.session_state["standings_view"] = "All"
    st.rerun()
if btn_conf.button("Conferences", width="stretch", type="primary" if view == "Conferences" else "secondary"):
    st.session_state["standings_view"] = "Conferences"
    st.rerun()
if btn_div.button("Divisions", width="stretch", type="primary" if view == "Divisions" else "secondary"):
    st.session_state["standings_view"] = "Divisions"
    st.rerun()

st.write("")

if view == "All":
    show_table(standings)
elif view == "Conferences":
    for conference in sorted(standings["conference_name"].dropna().unique()):
        show_table(standings[standings["conference_name"] == conference], title=conference)
else:
    for conference in sorted(standings["conference_name"].dropna().unique()):
        st.subheader(conference)
        conf_standings = standings[standings["conference_name"] == conference]
        for division in sorted(conf_standings["division_name"].dropna().unique()):
            show_table(conf_standings[conf_standings["division_name"] == division], title=division)
