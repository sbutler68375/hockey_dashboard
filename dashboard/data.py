"""Shared, cached data access for the dashboard.

Every dashboard page imports from here rather than calling
src.database.queries directly, so caching and the refresh pipeline stay
in one place instead of duplicated across pages.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.queries import (
    get_completed_games,
    get_player_stats,
    get_standings,
    get_team_games,
    get_team_season_stats,
)
from src.utils.constants import DEFAULT_SEASON, TEAM_ABBREVIATIONS

CACHE_TTL_SECONDS = 300  # data only changes when the user hits "Refresh", but
                          # cap staleness in case the app is left open for days


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_standings() -> pd.DataFrame:
    return get_standings()


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_completed_games(game_type: int | None = 2) -> pd.DataFrame:
    return get_completed_games(game_type=game_type)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_games(team_abbrev: str) -> pd.DataFrame:
    return get_team_games(team_abbrev)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_player_stats(season: int, player_type: str | None = None) -> pd.DataFrame:
    return get_player_stats(season, player_type)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_team_season_stats(season: int) -> pd.DataFrame:
    return get_team_season_stats(season)


def team_list() -> list[str]:
    return sorted(TEAM_ABBREVIATIONS)


def default_season() -> int:
    return int(DEFAULT_SEASON)


def refresh_all_data(progress_callback=None) -> list[str]:
    """Rerun the full pipeline: collectors -> build_database -> generate_features.

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
        ("Generating features", "scripts/generate_features.py"),
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
