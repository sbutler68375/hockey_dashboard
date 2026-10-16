"""SHL (Sean's Hockey League) -- dashboard entrypoint.

Run from the project root:
    venv\\Scripts\\python.exe -m streamlit run dashboard\\Home.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data import (
    current_season,
    format_refresh_time,
    last_refreshed,
    page_header,
    read_only,
    refresh_all_data,
    season_label,
)
from dashboard.images import player_action_shot_url
from dashboard.style import apply_theme

st.set_page_config(page_title="SHL", page_icon="🏒", layout="wide", initial_sidebar_state="expanded")
apply_theme()

# Hero photo: Connor McDavid shooting past the goalie, the NHL's own action
# shot (hotlinked from its CDN like the logos and headshots). CSS in
# style.py zooms it in on him and fades it into the navy.
HERO_PLAYER_ID = 8478402  # Connor McDavid
HERO_PLAYER_NAME = "Connor McDavid"


# Rink markings drawn behind the hero: boards, the two blue lines, center
# ice circle and faceoff dots, all in translucent ice blue.
RINK_SVG = """
<svg class="hero-rink" viewBox="0 0 1000 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <rect x="12" y="12" width="976" height="296" rx="120" fill="none" stroke="rgba(186,230,253,0.35)" stroke-width="2"/>
  <line x1="340" y1="12" x2="340" y2="308" stroke="rgba(56,189,248,0.45)" stroke-width="10"/>
  <line x1="660" y1="12" x2="660" y2="308" stroke="rgba(56,189,248,0.45)" stroke-width="10"/>
  <line x1="500" y1="12" x2="500" y2="308" stroke="rgba(186,230,253,0.18)" stroke-width="4" stroke-dasharray="10 8"/>
  <circle cx="500" cy="160" r="82" fill="none" stroke="rgba(186,230,253,0.35)" stroke-width="2"/>
  <circle cx="500" cy="160" r="5" fill="rgba(186,230,253,0.6)"/>
  <circle cx="850" cy="160" r="96" fill="none" stroke="rgba(186,230,253,0.28)" stroke-width="2"/>
  <circle cx="160" cy="90" r="4" fill="rgba(186,230,253,0.5)"/>
  <circle cx="160" cy="230" r="4" fill="rgba(186,230,253,0.5)"/>
</svg>
"""

season = page_header(
    "SHL",
    title_html='<div class="brand brand--stacked"><span class="brand-word">SHL</span>'
               '<span class="brand-sub">Sean\'s Hockey League</span></div>',
)
status = "Live season" if season == current_season() else "Final season"
refreshed_at = last_refreshed()
refreshed_text = f"Updated {format_refresh_time(refreshed_at)}" if refreshed_at else "No data yet"

st.markdown(
    f"""
<div class="hero">
  {RINK_SVG.strip()}
  <div class="hero-glow"></div>
  <div class="hero-sweep"></div>
  <div class="hero-content">
    <div class="hero-pill"><span class="hero-dot"></span>{status} · {season_label(season)}</div>
    <div class="hero-headline">Every game.<br><span>Every stat.</span> One rink.</div>
    <p class="hero-lede">Standings, team form, player production and machine-learning ratings,
    built end-to-end from the public NHL API.</p>
    <div class="hero-meta">{refreshed_text}</div>
  </div>
  <div class="hero-photo" role="img" aria-label="{HERO_PLAYER_NAME} shooting on goal"
       style="background-image: url('{player_action_shot_url(HERO_PLAYER_ID)}')"></div>
  <div class="hero-credit">{HERO_PLAYER_NAME} · Photo: NHL</div>
</div>
""",
    unsafe_allow_html=True,
)

# Where to go: one glowing card per page.
st.markdown('<div class="explore-label">Explore</div>', unsafe_allow_html=True)
links = [
    ("pages/1_Standings.py", "Standings", ":material/leaderboard:", "League, conference and division tables."),
    ("pages/2_Team.py", "Team", ":material/groups:", "Form, special teams, goalies and model ratings."),
    ("pages/3_Players.py", "Players", ":material/sports_hockey:", "Skater and goalie stats with model ratings."),
    ("pages/4_Season_Games.py", "Season Games", ":material/calendar_month:", "Every result of the season."),
]
for i, (col, (page, label, icon, blurb)) in enumerate(zip(st.columns(4), links)):
    with col, st.container(key=f"explore_{i}"):
        st.page_link(page, label=f"**{label}**", icon=icon)
        st.caption(blurb)

with st.sidebar:
    st.header("Data")
    if not read_only() and st.button("Refresh all data", width="stretch"):
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
    st.markdown(
        f"**Last refreshed:** {format_refresh_time(refreshed_at)}"
        if refreshed_at else "**Last refreshed:** never"
    )
    if read_only():
        st.caption("Data is updated by the site owner.")
    else:
        st.caption(
            "Pulls fresh data from the NHL API and rebuilds the database. "
            "Takes about 1-2 minutes."
        )
