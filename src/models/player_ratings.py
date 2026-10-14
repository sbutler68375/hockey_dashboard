"""Player ratings: who's actually good, and whose points are telling the truth?

The model predicts a skater's points per game over his NEXT 20 games from
how he has played so far this season (see pipelines.py for the shared
recipe): ice time (total, power play, shorthanded), shots, shooting %,
scoring so far, position, and last season's scoring. That prediction is
his "expected points per game" -- what his role and shot volume say he
should produce, with hot and cold streaks squeezed out.

Like the team model (team_ratings.py), scoring rates also go in weighted
by the share of the season played, and games past MAX_GAMES_COUNTED are
counted as that many. Tested 2026-10-13: better in every held-out season,
and without it the model underrated stars all season (it expected 1.40
points per game from a 1.68 McDavid).

From it, for each skater and season (ranked among qualified skaters --
see QUALIFY_SHARE):
    Overrated  -- his points-per-game percentile is VERDICT_GAP or more
        above his expected percentile (and he's a top-40% scorer, the
        players people actually rate).
    Underrated -- the reverse: the model ranks him far higher than his
        points do (and he's top 40% by the model).
    Playing better / worse -- the model's rating from his last 10 games is
        TREND_THRESHOLD above / below its rating from the whole season,
        both rated as if 10 games had been played.
Goalies aren't rated.
"""

import pandas as pd

from src.models.pipelines import ModelSpec

HORIZON = 20           # games ahead the target looks
MIN_GAMES = 5          # first snapshot: after a player's 5th game
TRAIN_EVERY = 5        # train on every 5th game's snapshot (neighbors are near-copies)
RECENT_GAMES = 10      # "playing better/worse" looks at the last 10 games
SEASON_GAMES = 82
MAX_GAMES_COUNTED = SEASON_GAMES - HORIZON  # no training snapshot is later than this
QUALIFY_SHARE = 0.25   # ranked only with 25%+ of the season's most games played (and MIN_GAMES)
VERDICT_GAP = 0.20     # percentile gap for Overrated / Underrated
VERDICT_FLOOR = 0.60   # ...and the flattering percentile must be at least this
TREND_THRESHOLD = 0.10     # last-10 rating vs season rating, points per game

# Typical NHL skater values the weighted features measure distance from.
TYPICAL = {"points_per_game": 0.45, "goals_per_game": 0.15, "pp_points_per_game": 0.12,
           "shots_per_game": 1.8, "shooting_pct": 0.09}
RATE_FEATURES = [*TYPICAL, "toi_per_game", "pp_toi_per_game", "sh_toi_per_game"]

SPEC = ModelSpec(
    name="player_ratings",
    target="future_points_per_game",
    numeric_features=[
        "games_counted", *RATE_FEATURES, *(f"{c}_weighted" for c in TYPICAL),
        "prior_points_per_game", "prior_games_played",
    ],
    categorical_features=["position_group"],
    baseline_feature="points_per_game",
)

FEATURE_LABELS = {
    "games_counted": "Games played (counted up to 62)",
    "points_per_game": "Points per game so far",
    "goals_per_game": "Goals per game",
    "pp_points_per_game": "Power play points per game",
    "shots_per_game": "Shots per game",
    "shooting_pct": "Shooting %",
    "toi_per_game": "Ice time per game",
    "pp_toi_per_game": "Power play ice time",
    "sh_toi_per_game": "Penalty kill ice time",
    "prior_points_per_game": "Last season's points per game",
    "prior_games_played": "Last season's games played",
    "position_group": "Forward or defenseman",
    **{f"{c}_weighted": f"{label}, weighted by games played" for c, label in [
        ("points_per_game", "Points per game"), ("goals_per_game", "Goals per game"),
        ("pp_points_per_game", "Power play points per game"), ("shots_per_game", "Shots per game"),
        ("shooting_pct", "Shooting %")]},
}

_COUNTS = ["goals", "assists", "points", "pp_points", "shots",
           "toi_seconds", "pp_toi_seconds", "sh_toi_seconds"]


def _rate_features(totals: pd.DataFrame, games: pd.Series) -> pd.DataFrame:
    """The model's per-game features from summed counts over `games` games."""
    t = totals
    return pd.DataFrame({
        "points_per_game": t["points"] / games,
        "goals_per_game": t["goals"] / games,
        "pp_points_per_game": t["pp_points"] / games,
        "shots_per_game": t["shots"] / games,
        "shooting_pct": t["goals"] / t["shots"].where(t["shots"] > 0),
        "toi_per_game": t["toi_seconds"] / games / 60,
        "pp_toi_per_game": t["pp_toi_seconds"] / games / 60,
        "sh_toi_per_game": t["sh_toi_seconds"] / games / 60,
    })


def add_weighted_features(df: pd.DataFrame, games: pd.Series | int | None = None) -> pd.DataFrame:
    """Set games_counted (games played, capped at MAX_GAMES_COUNTED -- or
    `games` if given) and add <stat>_weighted = (stat - typical) * share of
    the season counted. A missing shooting % (no shots yet) counts as typical."""
    counted = df["games_played"] if games is None else games
    df = df.assign(games_counted=pd.Series(counted, index=df.index).clip(upper=MAX_GAMES_COUNTED))
    seen = df["games_counted"] / SEASON_GAMES
    return df.assign(**{f"{c}_weighted": (df[c].fillna(t) - t) * seen for c, t in TYPICAL.items()})


def build_snapshots(player_games: pd.DataFrame) -> pd.DataFrame:
    """One row per skater per game played (from his MIN_GAMES-th): season-to-date
    features after that game, the same over his last RECENT_GAMES games
    (prefixed recent_), and -- where 20 more games exist -- his points per
    game over the next 20."""
    df = player_games.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
    df[_COUNTS] = df[_COUNTS].fillna(0)

    def by_player():
        return df.groupby(["season", "player_id"], sort=False)

    df["games_played"] = by_player().cumcount() + 1
    cumulative = by_player()[_COUNTS].cumsum()
    recent = cumulative - cumulative.groupby([df["season"], df["player_id"]]).shift(RECENT_GAMES).fillna(0)
    df = pd.concat([
        df.drop(columns=_COUNTS),
        _rate_features(cumulative, df["games_played"]),
        _rate_features(recent, df["games_played"].clip(upper=RECENT_GAMES)).add_prefix("recent_"),
    ], axis=1)
    df["position_group"] = df["position_code"].map(lambda p: "D" if p == "D" else "F")

    # Target: points per game over the player's next HORIZON games.
    future_points = cumulative.groupby([df["season"], df["player_id"]])["points"].shift(-HORIZON) - cumulative["points"]
    df[SPEC.target] = future_points / HORIZON

    # Last season's scoring (any team), keyed by player.
    final = df.loc[by_player()["games_played"].idxmax(), ["season", "player_id", "games_played", "points_per_game"]]
    prior = {(int(s), int(p)): (g, ppg) for s, p, g, ppg in final.itertuples(index=False)}
    keys = zip(df["season"].map(_previous_season), df["player_id"])
    prior_values = [prior.get((s, int(p)), (float("nan"), float("nan"))) for s, p in keys]
    df["prior_games_played"] = [g for g, _ in prior_values]
    df["prior_points_per_game"] = [ppg for _, ppg in prior_values]

    df = add_weighted_features(df)
    keep = ["season", "player_id", "player_name", "team_abbrev", "position_code", "game_date",
            "games_played", *SPEC.features, *(f"recent_{c}" for c in RATE_FEATURES), SPEC.target]
    return df.loc[df["games_played"] >= MIN_GAMES, keep].reset_index(drop=True)


def _previous_season(season: int) -> int:
    """20252026 -> 20242025."""
    start = season // 10000
    return (start - 1) * 10000 + start


def training_rows(snapshots: pd.DataFrame) -> pd.DataFrame:
    """Every TRAIN_EVERY-th game's snapshot -- consecutive snapshots of one
    player are nearly identical, so using all of them adds little but time."""
    return snapshots[snapshots["games_played"] % TRAIN_EVERY == 0]


def score(model, snapshots: pd.DataFrame) -> pd.DataFrame:
    """Rate every skater in every season as of his latest game: one row per
    player per season, with expected vs actual, percentiles and verdicts.
    team_abbrev is the team of his latest game."""
    latest = snapshots.loc[snapshots.groupby(["season", "player_id"])["games_played"].idxmax()].copy()
    latest["expected_points_per_game"] = model.predict(latest[SPEC.features])

    # Recent form: rate the last 10 games and the whole season the same way
    # (each as if it were 10 games old), so the difference is the play itself.
    season_input = add_weighted_features(latest, games=RECENT_GAMES)
    recent_input = latest.copy()
    for col in RATE_FEATURES:
        recent_input[col] = latest[f"recent_{col}"]
    recent_input = add_weighted_features(recent_input, games=RECENT_GAMES)
    latest["form_change"] = (model.predict(recent_input[SPEC.features])
                             - model.predict(season_input[SPEC.features]))
    latest.loc[latest["games_played"] < 2 * RECENT_GAMES, "form_change"] = None

    most_games = latest.groupby("season")["games_played"].transform("max")
    latest["qualified"] = latest["games_played"] >= (QUALIFY_SHARE * most_games).clip(lower=MIN_GAMES)
    pool = latest[latest["qualified"]].groupby("season")
    latest["points_percentile"] = pool["points_per_game"].rank(pct=True)
    latest["expected_percentile"] = pool["expected_points_per_game"].rank(pct=True)
    latest["points_rank"] = pool["points_per_game"].rank(ascending=False, method="min")
    latest["expected_rank"] = pool["expected_points_per_game"].rank(ascending=False, method="min")

    gap = latest["points_percentile"] - latest["expected_percentile"]
    latest["verdict"] = None
    latest.loc[latest["qualified"], "verdict"] = "Fair"
    latest.loc[(gap >= VERDICT_GAP) & (latest["points_percentile"] >= VERDICT_FLOOR), "verdict"] = "Overrated"
    latest.loc[(gap <= -VERDICT_GAP) & (latest["expected_percentile"] >= VERDICT_FLOOR), "verdict"] = "Underrated"
    latest["trend"] = None
    has_trend = latest["qualified"] & latest["form_change"].notna()
    latest.loc[has_trend, "trend"] = "Steady"
    latest.loc[has_trend & (latest["form_change"] >= TREND_THRESHOLD), "trend"] = "Playing better"
    latest.loc[has_trend & (latest["form_change"] <= -TREND_THRESHOLD), "trend"] = "Playing worse"

    return latest[[
        "season", "player_id", "player_name", "team_abbrev", "position_code", "game_date",
        "games_played", "qualified", "points_per_game", "expected_points_per_game",
        "points_percentile", "expected_percentile", "points_rank", "expected_rank", "verdict",
        "form_change", "trend", "recent_points_per_game", "goals_per_game",
        "shots_per_game", "shooting_pct", "toi_per_game", "pp_toi_per_game",
        "prior_points_per_game",
    ]].rename(columns={"game_date": "as_of_date"}).reset_index(drop=True)
