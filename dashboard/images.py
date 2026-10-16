"""URL builders for team logos and player headshots.

Both are served from the NHL's public, keyless asset CDN
(assets.nhle.com) -- same free/no-auth spirit as the rest of this
project's data source. Nothing is downloaded or stored locally: these
functions just build a URL string, and Streamlit/the browser fetches
the image directly from the NHL's CDN each time it's displayed.

Verified live 2026-09-09 (see conversation/CLAUDE session, no
standalone script yet -- treat as observed, not guaranteed, same as
every other endpoint in this project):
    https://assets.nhle.com/logos/nhl/svg/TOR_light.svg           -> 200, image/svg+xml
    https://assets.nhle.com/mugs/nhl/20252026/TOR/8477939.png    -> 200, image/png
"""

def nhl_logo_url() -> str:
    """SVG NHL league logo, light-background version (verified live 2026-10-07)."""
    return "https://assets.nhle.com/logos/nhl/svg/NHL_light.svg"


def team_logo_url(team_abbrev: str) -> str:
    """SVG team logo, light-background version (all 32 verified live 2026-10-07)."""
    return f"https://assets.nhle.com/logos/nhl/svg/{team_abbrev}_light.svg"


def player_headshot_url(player_id: int, team_abbrev: str, season: int) -> str:
    """Player headshot for the given team/season.

    Note: this constructs the URL from the same pattern the NHL's own
    roster endpoint returns in its `headshot` field, rather than
    calling that endpoint here -- avoids an extra API round-trip per
    player, at the cost of assuming the pattern holds. If headshots
    start showing broken for real players, that assumption is the
    first thing to check.
    """
    return f"https://assets.nhle.com/mugs/nhl/{season}/{team_abbrev}/{player_id}.png"


def player_action_shot_url(player_id: int) -> str:
    """Wide (1296x729) in-game action photo of a player -- the `heroImage`
    field of the NHL's player landing endpoint (McDavid's verified live
    2026-10-15)."""
    return f"https://assets.nhle.com/mugs/actionshots/1296x729/{player_id}.jpg"
