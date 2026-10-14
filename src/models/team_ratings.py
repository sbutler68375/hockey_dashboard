"""Team ratings: how good is each team really, and is its record telling the truth?

The model predicts a team's points % over the REST OF THE SEASON from how
it has played so far (see pipelines.py for the shared recipe). That
prediction is the team's "expected points %" -- its underlying strength,
with the luck squeezed out: shot and shot-attempt share, goal share,
shooting and save %, special teams, and last season's results.

Weighted features: a linear model gives "points % so far" one weight,
whether it's 5 games in or 70 -- so after a hot first week it predicted a
.780 team. Each rate stat also goes in as its distance from a typical NHL
value times the share of the season played (e.g. points_pct_weighted), so
the model can trust a stat more as games pile up. Tested 2026-10-13: better
in every held-out season (average R^2 0.29 -> 0.32).

Why rest of season: a shorter target (say, the next 20 games) is mostly
random bounces -- tested 2026-10-13, no model beat the league average at
predicting it. Over the rest of a season, the underlying numbers show
through (the model beat "current points % only" in every held-out season).

From it, for each team and season:
    Overrated / Underrated -- the standings rank (by points %) is
        OVERRATED_RANK_GAP or more places better / worse than the model's.
    Playing better / worse -- the model's rating of the team from its
        last 10 games is TREND_THRESHOLD above / below its rating from the
        whole season, both rated as if 10 games had been played (so the
        only difference is the stats, not how much the model trusts them).
    PDO -- shooting % + save %: well above 1.000 usually means a team is
        riding hot shooting/goaltending that tends not to last.
"""

import pandas as pd

from src.models.pipelines import ModelSpec
from src.utils.constants import FRANCHISE_PREDECESSORS

MIN_GAMES = 5          # first snapshot: after a team's 5th game
MIN_REMAINING = 20     # training targets need at least 20 games left to average over
RECENT_GAMES = 10      # "playing better/worse" looks at the last 10 games
OVERRATED_RANK_GAP = 6     # standings rank this many places off the model's rank
TREND_THRESHOLD = 0.04     # last-10 rating vs season rating, in points % (flags ~1 in 4)
SEASON_GAMES = 82
# Training snapshots all have 20+ games left, so the model never saw one past
# game 62. Later snapshots are scored as if at game 62 rather than asking the
# model to extrapolate (it stretched end-of-season ratings when it did).
MAX_GAMES_COUNTED = SEASON_GAMES - MIN_REMAINING

# Typical NHL values the weighted features measure distance from. Shares
# center on .500; points % sits above it because overtime losses earn a point.
TYPICAL = {"points_pct": 0.555, "goal_share": 0.5, "shot_share": 0.5, "attempt_share": 0.5,
           "sat_pct_5v5": 0.5, "shooting_pct": 0.10, "save_pct": 0.90, "pp_pct": 0.21, "pk_pct": 0.79}
RATE_FEATURES = list(TYPICAL)

SPEC = ModelSpec(
    name="team_ratings",
    target="rest_of_season_points_pct",
    numeric_features=[
        "games_counted", *RATE_FEATURES, *(f"{c}_weighted" for c in RATE_FEATURES),
        "prior_points_pct",
    ],
    baseline_feature="points_pct",
)

FEATURE_LABELS = {
    "games_counted": "Games played (counted up to 62)",
    "points_pct": "Points % so far",
    "goal_share": "Share of goals",
    "shot_share": "Share of shots",
    "attempt_share": "Share of shot attempts",
    "sat_pct_5v5": "5-on-5 shot attempt share",
    "shooting_pct": "Shooting %",
    "save_pct": "Save %",
    "pp_pct": "Power play %",
    "pk_pct": "Penalty kill %",
    "prior_points_pct": "Last season's points %",
    **{f"{c}_weighted": f"{label}, weighted by games played" for c, label in [
        ("points_pct", "Points %"), ("goal_share", "Share of goals"), ("shot_share", "Share of shots"),
        ("attempt_share", "Share of shot attempts"), ("sat_pct_5v5", "5-on-5 shot attempt share"),
        ("shooting_pct", "Shooting %"), ("save_pct", "Save %"), ("pp_pct", "Power play %"),
        ("pk_pct", "Penalty kill %")]},
}

_COUNTS = ["points", "goals_for", "goals_against", "shots_for", "shots_against",
           "shot_attempts_for", "shot_attempts_against", "sat_pct_5v5",
           "pp_goals", "pp_opportunities", "pp_goals_against", "times_shorthanded"]


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.where(denominator > 0)


def _rate_features(totals: pd.DataFrame, games: pd.Series) -> pd.DataFrame:
    """The model's rate features from summed counts over `games` games."""
    t = totals
    return pd.DataFrame({
        "points_pct": t["points"] / (2 * games),
        "goal_share": _ratio(t["goals_for"], t["goals_for"] + t["goals_against"]),
        "shot_share": _ratio(t["shots_for"], t["shots_for"] + t["shots_against"]),
        "attempt_share": _ratio(t["shot_attempts_for"], t["shot_attempts_for"] + t["shot_attempts_against"]),
        "sat_pct_5v5": t["sat_pct_5v5"] / games,
        "shooting_pct": _ratio(t["goals_for"], t["shots_for"]),
        "save_pct": 1 - _ratio(t["goals_against"], t["shots_against"]),
        "pp_pct": _ratio(t["pp_goals"], t["pp_opportunities"]),
        "pk_pct": 1 - _ratio(t["pp_goals_against"], t["times_shorthanded"]),
    })


def add_weighted_features(df: pd.DataFrame, games: pd.Series | int | None = None) -> pd.DataFrame:
    """Set games_counted (games played, capped at MAX_GAMES_COUNTED -- or
    `games` if given) and add <stat>_weighted = (stat - typical) * share of
    the season counted."""
    counted = df["games_played"] if games is None else games
    df = df.assign(games_counted=pd.Series(counted, index=df.index).clip(upper=MAX_GAMES_COUNTED))
    seen = df["games_counted"] / SEASON_GAMES
    return df.assign(**{f"{c}_weighted": (df[c] - TYPICAL[c]) * seen for c in RATE_FEATURES})


def build_snapshots(team_games: pd.DataFrame, special_teams: pd.DataFrame) -> pd.DataFrame:
    """One row per team per game played (from its MIN_GAMES-th): season-to-date
    features after that game, the same features over its last RECENT_GAMES
    games (prefixed recent_), and -- where 20+ games remain -- the points %
    over the rest of the season."""
    df = team_games.merge(
        special_teams[["game_id", "team_abbrev", "pp_goals", "pp_opportunities",
                       "pp_goals_against", "times_shorthanded"]],
        on=["game_id", "team_abbrev"], how="left",
    ).sort_values(["season", "team_abbrev", "game_date", "game_id"]).reset_index(drop=True)
    df[_COUNTS] = df[_COUNTS].fillna(0)

    def by_team():
        return df.groupby(["season", "team_abbrev"], sort=False)

    df["games_played"] = by_team().cumcount() + 1
    cumulative = by_team()[_COUNTS].cumsum()
    recent = cumulative - cumulative.groupby([df["season"], df["team_abbrev"]]).shift(RECENT_GAMES).fillna(0)
    season_rates = _rate_features(cumulative, df["games_played"])
    df = pd.concat([
        df.drop(columns=[c for c in season_rates if c in df]),  # per-game sat_pct_5v5
        season_rates,
        _rate_features(recent, df["games_played"].clip(upper=RECENT_GAMES)).add_prefix("recent_"),
    ], axis=1)
    df["pdo"] = df["shooting_pct"] + df["save_pct"]

    # Target: points % over the rest of the season, when 20+ games remain.
    season_points = by_team()["points"].transform("sum")
    season_games = by_team()["games_played"].transform("max")
    remaining = season_games - df["games_played"]
    df[SPEC.target] = ((season_points - cumulative["points"]) / (2 * remaining)).where(
        remaining >= MIN_REMAINING
    )

    # Last season's final points %, for the same franchise (Utah <- Arizona).
    final = df.loc[by_team()["games_played"].idxmax(), ["season", "team_abbrev", "points_pct"]]
    prior = {(int(s), t): p for s, t, p in final.itertuples(index=False)}
    df["prior_points_pct"] = [
        prior.get((ps, team), prior.get((ps, FRANCHISE_PREDECESSORS.get(team, team))))
        for ps, team in zip(df["season"].map(_previous_season), df["team_abbrev"])
    ]

    df = add_weighted_features(df)
    recent_cols = [f"recent_{c}" for c in RATE_FEATURES]
    keep = ["season", "team_abbrev", "game_date", "games_played", "pdo",
            *SPEC.numeric_features, *recent_cols, SPEC.target]
    return df.loc[df["games_played"] >= MIN_GAMES, keep].reset_index(drop=True)


def _previous_season(season: int) -> int:
    """20252026 -> 20242025."""
    start = season // 10000
    return (start - 1) * 10000 + start


def score(model, snapshots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rate every team in every season as of its latest game.

    Returns:
        (ratings: one row per team per season with expected vs actual,
         ranks and verdicts; history: expected and actual points % after
         every game, for a chart of a team's rating over the season).
    """
    snaps = snapshots.copy()
    snaps["expected_points_pct"] = model.predict(snaps[SPEC.features])
    history = snaps[["season", "team_abbrev", "game_date", "games_played",
                     "points_pct", "expected_points_pct"]]

    latest = snaps.loc[snaps.groupby(["season", "team_abbrev"])["games_played"].idxmax()].copy()

    # Recent form: rate the last 10 games and the whole season the same way --
    # each as if it were a 10-game-old season with the same previous season --
    # so the difference is the play itself, not how much the model trusts it.
    season_input = add_weighted_features(latest, games=RECENT_GAMES)
    recent_input = latest.copy()
    for col in RATE_FEATURES:
        recent_input[col] = latest[f"recent_{col}"]
    recent_input = add_weighted_features(recent_input, games=RECENT_GAMES)
    latest["form_change"] = (model.predict(recent_input[SPEC.features])
                             - model.predict(season_input[SPEC.features]))
    # Before 2x the window, "last 10" is most of the season -- nothing to compare.
    latest.loc[latest["games_played"] < 2 * RECENT_GAMES, "form_change"] = None

    by_season = latest.groupby("season")
    latest["standings_rank"] = by_season["points_pct"].rank(ascending=False, method="min").astype(int)
    latest["model_rank"] = by_season["expected_points_pct"].rank(ascending=False, method="min").astype(int)
    latest["league_pdo"] = by_season["pdo"].transform("mean")
    # Positive: the standings rate the team higher than the model does.
    latest["rank_gap"] = latest["model_rank"] - latest["standings_rank"]
    latest["verdict"] = "Fair"
    latest.loc[latest["rank_gap"] >= OVERRATED_RANK_GAP, "verdict"] = "Overrated"
    latest.loc[latest["rank_gap"] <= -OVERRATED_RANK_GAP, "verdict"] = "Underrated"
    latest["trend"] = None
    has_trend = latest["form_change"].notna()
    latest.loc[has_trend, "trend"] = "Steady"
    latest.loc[has_trend & (latest["form_change"] >= TREND_THRESHOLD), "trend"] = "Playing better"
    latest.loc[has_trend & (latest["form_change"] <= -TREND_THRESHOLD), "trend"] = "Playing worse"

    ratings = latest[[
        "season", "team_abbrev", "game_date", "games_played", "points_pct",
        "expected_points_pct", "standings_rank", "model_rank", "rank_gap", "verdict",
        "form_change", "trend", "recent_points_pct",
        "pdo", "league_pdo", "shooting_pct", "save_pct", "shot_share", "attempt_share",
        "goal_share", "pp_pct", "pk_pct", "prior_points_pct",
    ]].rename(columns={"game_date": "as_of_date"})
    return ratings.reset_index(drop=True), history.reset_index(drop=True)
