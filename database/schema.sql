-- NHL Hockey Analytics Database Schema (SQLite)
--
-- Deliberately excludes a play_by_play table for now -- we don't collect
-- that data yet (it's Phase 8 / shot-map territory). Add it when there's
-- an actual collector feeding it, not before.

CREATE TABLE IF NOT EXISTS teams (
    team_abbrev TEXT PRIMARY KEY,
    team_name TEXT,
    common_name TEXT,
    place_name TEXT,
    conference_name TEXT,
    division_name TEXT
);

-- One row per team per standings snapshot date. Re-collecting standings
-- on a new date adds new rows (a real trend over the season) rather than
-- overwriting; re-collecting for a date already stored updates that row.
CREATE TABLE IF NOT EXISTS standings (
    team_abbrev TEXT NOT NULL,
    date TEXT NOT NULL,
    season_id INTEGER,
    games_played INTEGER,
    wins INTEGER,
    losses INTEGER,
    ot_losses INTEGER,
    ties INTEGER,
    points INTEGER,
    point_pctg REAL,
    goal_for INTEGER,
    goal_against INTEGER,
    goal_differential INTEGER,
    home_wins INTEGER,
    home_losses INTEGER,
    home_ot_losses INTEGER,
    home_points INTEGER,
    road_wins INTEGER,
    road_losses INTEGER,
    road_ot_losses INTEGER,
    road_points INTEGER,
    l10_wins INTEGER,
    l10_losses INTEGER,
    l10_ot_losses INTEGER,
    l10_points INTEGER,
    streak_code TEXT,
    streak_count INTEGER,
    PRIMARY KEY (team_abbrev, date),
    FOREIGN KEY (team_abbrev) REFERENCES teams(team_abbrev)
);

-- One row per team per season: aggregated totals from club-stats.
-- No true PP%/PK% here -- see collect_teams.py docstring for why.
CREATE TABLE IF NOT EXISTS team_season_stats (
    team_abbrev TEXT NOT NULL,
    season INTEGER NOT NULL,
    total_goals INTEGER,
    total_assists INTEGER,
    total_points INTEGER,
    total_shots INTEGER,
    total_powerplay_goals INTEGER,
    total_shorthanded_goals INTEGER,
    total_shots_against INTEGER,
    total_saves INTEGER,
    team_save_pct REAL,
    total_goals_against INTEGER,
    total_shutouts INTEGER,
    PRIMARY KEY (team_abbrev, season),
    FOREIGN KEY (team_abbrev) REFERENCES teams(team_abbrev)
);

CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY,
    season INTEGER,
    game_type INTEGER,
    game_date TEXT,
    start_time_utc TEXT,
    game_state TEXT,
    venue TEXT,
    away_team TEXT NOT NULL,
    away_score INTEGER,
    home_team TEXT NOT NULL,
    home_score INTEGER,
    FOREIGN KEY (away_team) REFERENCES teams(team_abbrev),
    FOREIGN KEY (home_team) REFERENCES teams(team_abbrev)
);

-- One row per player per team per season. A player traded mid-season can
-- legitimately have two rows (one per team), matching how the NHL's own
-- club-stats endpoint attributes stats.
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER NOT NULL,
    team_abbrev TEXT NOT NULL,
    season INTEGER NOT NULL,
    player_type TEXT NOT NULL,  -- 'skater' or 'goalie'
    first_name TEXT,
    last_name TEXT,
    position_code TEXT,
    games_played INTEGER,

    -- skater stats (NULL for goalies)
    goals INTEGER,
    assists INTEGER,
    points INTEGER,
    plus_minus INTEGER,
    penalty_minutes INTEGER,
    power_play_goals INTEGER,
    shorthanded_goals INTEGER,
    game_winning_goals INTEGER,
    overtime_goals INTEGER,
    shots INTEGER,
    shooting_pctg REAL,
    avg_time_on_ice_per_game REAL,
    avg_shifts_per_game REAL,
    faceoff_win_pctg REAL,

    -- goalie stats (NULL for skaters)
    games_started INTEGER,
    wins INTEGER,
    losses INTEGER,
    overtime_losses INTEGER,
    save_pctg REAL,
    goals_against_average REAL,
    shots_against INTEGER,
    saves INTEGER,
    goals_against INTEGER,
    shutouts INTEGER,
    goalie_time_on_ice_seconds INTEGER,

    -- bio, from current roster -- may be NULL, see collect_players.py
    height_cm REAL,
    weight_kg REAL,
    birth_date TEXT,
    birth_country TEXT,
    shoots_catches TEXT,

    PRIMARY KEY (player_id, team_abbrev, season),
    FOREIGN KEY (team_abbrev) REFERENCES teams(team_abbrev)
);

CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_players_season ON players(season);
CREATE INDEX IF NOT EXISTS idx_standings_season ON standings(season_id);
