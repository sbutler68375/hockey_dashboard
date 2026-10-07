"""Shared, cached data access for the dashboard.

Every dashboard page imports from here rather than calling
src.database.queries directly, so caching and the refresh pipeline stay
in one place instead of duplicated across pages.
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.queries import (
    get_completed_games,
    get_player_stats,
    get_standings,
    get_team_games,
    get_team_season_stats,
    get_team_special_teams_games,
    get_teams,
)
from dashboard.images import nhl_logo_url, team_logo_url
from dashboard.style import theme_type
from src.utils.constants import COLLECTED_SEASONS, CURRENT_SEASON, TEAM_ABBREVIATIONS

CACHE_TTL_SECONDS = 300  # data only changes when the user hits "Refresh", but
                          # cap staleness in case the app is left open for days

# Session-state key holding the season picked in the page-header toggle.
# Kept separate from the widget's own key because Streamlit drops a
# widget's state when you switch to a page that hasn't rendered it yet --
# this plain key survives page switches, so the choice sticks app-wide.
_SEASON_STATE_KEY = "selected_season"
_SEASON_WIDGET_KEY = "_season_toggle"

# Set by the header's sun/moon button to the theme to switch to ("Light"
# or "Dark"); page_header() then runs the switch on that rerun.
_THEME_SWITCH_KEY = "_theme_switch_to"

# URL path of every page ("" = Home), for saving the theme choice per page.
PAGE_PATHS = [""] + [
    p.stem.split("_", 1)[1] for p in sorted((Path(__file__).parent / "pages").glob("*.py"))
]

# Same pattern for the team picked with the header's logo button.
# None means no team selected (all teams).
_TEAM_STATE_KEY = "selected_team"


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_standings(season: int) -> pd.DataFrame:
    """Latest standings snapshot within a season -- today's standings for
    the current season, final standings for a completed one."""
    return get_standings(season=season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_completed_games(season: int, game_type: int | None = 2) -> pd.DataFrame:
    return get_completed_games(game_type=game_type, season=season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_games(team_abbrev: str, season: int) -> pd.DataFrame:
    return get_team_games(team_abbrev, season=season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_player_stats(season: int, player_type: str | None = None) -> pd.DataFrame:
    return get_player_stats(season, player_type)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_season_stats(season: int) -> pd.DataFrame:
    return get_team_season_stats(season)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_special_teams_games(team_abbrev: str, season: int) -> pd.DataFrame:
    return get_team_special_teams_games(team_abbrev, season)


def team_results(games: pd.DataFrame, team: str) -> pd.DataFrame:
    """One team's games from that team's point of view, newest first.

    Adds: opponent, home_away ("Home"/"Away"), outcome ("W", "L", or "OT"
    for a loss in overtime or a shootout -- the NHL's "OT loss", worth a
    point in the standings) and result, e.g. "W 3-2" (team's goals first).
    """
    games = games[(games["home_team"] == team) | (games["away_team"] == team)]
    games = games.sort_values("game_date", ascending=False).copy()
    is_home = games["home_team"] == team
    team_score = games["home_score"].where(is_home, games["away_score"]).astype(int)
    opp_score = games["away_score"].where(is_home, games["home_score"]).astype(int)
    games["opponent"] = games["away_team"].where(is_home, games["home_team"])
    games["home_away"] = is_home.map({True: "Home", False: "Away"})
    went_past_regulation = games["last_period_type"].isin(["OT", "SO"])
    outcome = (team_score > opp_score).map({True: "W", False: "L"})
    games["outcome"] = outcome.mask((outcome == "L") & went_past_regulation, "OT")
    games["result"] = games["outcome"] + " " + team_score.astype(str) + "-" + opp_score.astype(str)
    return games


def record_text(results: pd.DataFrame) -> str:
    """W-L-OT record for team_results() rows, e.g. "6-3-1"."""
    return "-".join(str(int((results["outcome"] == o).sum())) for o in ("W", "L", "OT"))


def team_list() -> list[str]:
    return sorted(TEAM_ABBREVIATIONS)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def team_names() -> dict[str, str]:
    """{abbreviation: full team name}, e.g. {"TOR": "Toronto Maple Leafs"}."""
    try:
        teams = get_teams()
    except Exception:  # no database yet -- fall back to abbreviations
        return {}
    return dict(zip(teams["team_abbrev"], teams["team_name"]))


def team_display_name(team: str) -> str:
    return team_names().get(team, team)


def selected_team() -> str | None:
    """The team chosen with the header's logo button, or None for all teams."""
    return st.session_state.get(_TEAM_STATE_KEY)


def _select_team(team: str | None) -> None:
    st.session_state[_TEAM_STATE_KEY] = team


def _logo_label(url: str, alt: str) -> str:
    """Markdown image for a button/popover label (Streamlit renders it as an icon)."""
    return f"![{alt}]({url})"


def _team_picker() -> None:
    """The header's logo button: shows the selected team's logo (NHL logo when
    none is selected) and opens a grid of every team's logo to pick from."""
    team = selected_team()
    label = _logo_label(team_logo_url(team), team) if team else _logo_label(nhl_logo_url(), "NHL")
    with st.container(key="team_picker"):
        with st.popover(label, help="Choose a team"):
            with st.container(key="team_picker_grid"):
                st.button(
                    _logo_label(nhl_logo_url(), "NHL") + " All teams",
                    key="team_pick_all", on_click=_select_team, args=(None,),
                    type="primary" if team is None else "secondary", width="stretch",
                )
                columns = st.columns(8, gap="small")
                for i, abbrev in enumerate(team_list()):
                    with columns[i % 8]:
                        st.button(
                            _logo_label(team_logo_url(abbrev), abbrev),
                            key=f"team_pick_{abbrev}", help=team_display_name(abbrev),
                            on_click=_select_team, args=(abbrev,),
                            type="primary" if abbrev == team else "secondary", width="stretch",
                        )


def current_season() -> int:
    return int(CURRENT_SEASON)


def season_label(season: int) -> str:
    """20252026 -> '2025-26'."""
    text = str(season)
    return f"{text[:4]}-{text[6:]}"


def short_season_label(season: int) -> str:
    """20252026 -> '25/26'."""
    text = str(season)
    return f"{text[2:4]}/{text[6:]}"


def previous_season() -> int:
    """The most recent completed season -- the toggle's 'off' side."""
    return max(int(s) for s in COLLECTED_SEASONS if int(s) != current_season())


def selected_season() -> int:
    """The season chosen in the page-header toggle (current season by default)."""
    return st.session_state.get(_SEASON_STATE_KEY, current_season())


def _store_season_choice() -> None:
    is_current = st.session_state[_SEASON_WIDGET_KEY]
    st.session_state[_SEASON_STATE_KEY] = current_season() if is_current else previous_season()


def _toggle_side_label(text: str, active: bool, align: str) -> None:
    """One side's label next to the switch -- highlighted when it's the active side."""
    color = "var(--primary-color, #3b82f6)" if active else "rgba(136, 146, 160, 0.9)"
    weight = 700 if active else 500
    st.markdown(
        f'<div style="text-align:{align};color:{color};font-weight:{weight};'
        f'font-size:0.9rem;white-space:nowrap">{text}</div>',
        unsafe_allow_html=True,
    )


def _request_theme_switch() -> None:
    st.session_state[_THEME_SWITCH_KEY] = "Dark" if theme_type() == "light" else "Light"


def _theme_button() -> None:
    """The header's sun/moon button: switches this browser between the light
    and dark themes (config.toml's [theme.light] / [theme.dark])."""
    to_light = theme_type() == "dark"
    st.button(
        "", key="theme_button", on_click=_request_theme_switch,
        icon=":material/light_mode:" if to_light else ":material/dark_mode:",
        help="Switch to light theme" if to_light else "Switch to dark theme",
    )

    target = st.session_state.pop(_THEME_SWITCH_KEY, None)
    if target is None:
        return
    # Streamlit has no Python API for a viewer's theme. Its frontend reads the
    # choice from localStorage on page load (key "stActiveTheme-<path>-v2",
    # value "Light"/"Dark" as JSON -- observed in Streamlit 1.65's frontend;
    # recheck after upgrading). So save it for every page and reload, putting
    # the selected team and season in the URL so the reload keeps them
    # (_restore_from_url() reads them back).
    params = {"season": selected_season()}
    if selected_team():
        params["team"] = selected_team()
    # components.html, not st.iframe: Streamlit 1.65 flags it as deprecated,
    # but st.iframe didn't run this script when tried (2026-10-07).
    components.html(
        f"""<script>
        const store = window.parent.localStorage;
        const base = window.parent.location.pathname.replace(/[^/]*$/, "");
        for (const page of {json.dumps(PAGE_PATHS)}) {{
            store.setItem("stActiveTheme-" + base + page + "-v2", {json.dumps(json.dumps(target))});
        }}
        store.setItem("stActiveTheme-" + window.parent.location.pathname + "-v2", {json.dumps(json.dumps(target))});
        // This script runs in a sandboxed iframe, which may not navigate the
        // page itself -- so hand the reload to a function created in (and run
        // by) the same-origin parent page.
        const search = new URLSearchParams({json.dumps({k: str(v) for k, v in params.items()})}).toString();
        window.parent.setTimeout(new window.parent.Function("location.search = " + JSON.stringify(search)), 0);
        </script>""",
        height=0,
    )


def _restore_from_url() -> None:
    """After a theme switch reloads the page (new session), restore the team
    and season it put in the URL, then clear them from the URL."""
    params = st.query_params
    if "season" in params and _SEASON_STATE_KEY not in st.session_state:
        if params["season"] in COLLECTED_SEASONS:
            st.session_state[_SEASON_STATE_KEY] = int(params["season"])
        if params.get("team") in TEAM_ABBREVIATIONS:
            st.session_state[_TEAM_STATE_KEY] = params["team"]
    if "season" in params or "team" in params:
        params.clear()


def page_header(title: str) -> int:
    """Render a page title with the team logo button, the season toggle
    switch (last season <-> Current) and the light/dark theme button in the
    top-right corner, and return the
    selected season. Every page calls this in place of st.title() so the
    controls sit in the same spot everywhere; use selected_team() for the
    team."""
    _restore_from_url()
    is_current = selected_season() == current_season()
    st.session_state[_SEASON_WIDGET_KEY] = is_current

    title_col, team_col, toggle_col, theme_col = st.columns([3, 0.35, 1, 0.25], vertical_alignment="center")
    with title_col:
        st.title(title)
    with team_col:
        _team_picker()
    with toggle_col:
        past_col, switch_col, current_col = st.columns([1.2, 0.55, 1.2], vertical_alignment="center", gap="small")
        with past_col:
            _toggle_side_label(short_season_label(previous_season()), not is_current, "right")
        with switch_col:
            st.toggle(
                "Show current season",
                key=_SEASON_WIDGET_KEY,
                on_change=_store_season_choice,
                label_visibility="collapsed",
            )
        with current_col:
            _toggle_side_label("Current", is_current, "left")
    with theme_col:
        _theme_button()
    return selected_season()


def refresh_all_data(progress_callback=None) -> list[str]:
    """Rerun the full pipeline: collectors -> build_database.

    Runs each step as a subprocess (same approach as running them
    manually from the command line) so a failure in one step is caught
    and reported without crashing the dashboard process itself.

    Args:
        progress_callback: optional callable(step_name: str) invoked
            before each step starts, for UI progress updates.

    Returns:
        List of log lines describing what happened, success or failure.
    """
    steps = [
        ("Collecting team data", "collectors/collect_teams.py"),
        ("Collecting player data", "collectors/collect_players.py"),
        ("Collecting game data", "collectors/collect_games.py"),
        ("Building database", "scripts/build_database.py"),
    ]
    python_exe = sys.executable
    log: list[str] = []

    for label, script in steps:
        if progress_callback:
            progress_callback(label)
        result = subprocess.run(
            [python_exe, str(PROJECT_ROOT / script)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.append(f"FAILED: {label}\n{result.stderr[-2000:]}")
            break
        log.append(f"OK: {label}")

    st.cache_data.clear()
    return log
