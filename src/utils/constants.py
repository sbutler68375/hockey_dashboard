"""Shared constants for NHL data collection.

Field names and endpoints throughout this project were verified against
live API responses (see scripts/explore_api.py) rather than assumed --
the NHL does not publish official API documentation, so anything here
should be treated as "observed to work as of the date noted," not
guaranteed to stay stable forever.
"""

NHL_API_BASE = "https://api-web.nhle.com/v1"

# All 32 current NHL team abbreviations, as returned by the standings
# endpoint's teamAbbrev.default field (verified live 2026-08-26).
TEAM_ABBREVIATIONS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
]

# The season in progress -- what the dashboard shows by default. Bump
# this (and append the old value to HISTORICAL_SEASONS) each fall once
# the new season's regular season is underway.
CURRENT_SEASON = "20262027"

# Completed seasons that are still collected: their games serve as model
# training history, and the dashboard's season toggle can switch to them
# (final standings, team totals, player stats, game results).
HISTORICAL_SEASONS = ["20252026"]

# Every season that gets collected (historical + current), oldest first.
COLLECTED_SEASONS = [*HISTORICAL_SEASONS, CURRENT_SEASON]

# NHL API gameType codes, as seen in schedule/club-schedule-season responses.
GAME_TYPE_PRESEASON = 1
GAME_TYPE_REGULAR_SEASON = 2
GAME_TYPE_PLAYOFFS = 3
