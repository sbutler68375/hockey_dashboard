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

# Most recently *completed* NHL season at time of writing (verified
# 2026-08-26). The 2026-27 season had not started yet, so this is the
# newest season with a full set of final results. Update this once the
# new season is underway and you want current-season data instead.
DEFAULT_SEASON = "20252026"

# NHL API gameType codes, as seen in schedule/club-schedule-season responses.
GAME_TYPE_PRESEASON = 1
GAME_TYPE_REGULAR_SEASON = 2
GAME_TYPE_PLAYOFFS = 3
