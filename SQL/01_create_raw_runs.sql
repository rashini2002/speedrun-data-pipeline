CREATE TABLE IF NOT EXISTS raw.runs (
    run_id             TEXT PRIMARY KEY,
    game_id            TEXT REFERENCES raw.games(game_id),
    category_id        TEXT REFERENCES raw.categories(category_id),
    player_id          TEXT,
    run_time_seconds   NUMERIC,
    date_submitted     DATE,
    fetched_at         TIMESTAMP DEFAULT now(),
    raw_json           JSONB
);

CREATE INDEX IF NOT EXISTS idx_runs_game ON raw.runs(game_id);
CREATE INDEX IF NOT EXISTS idx_runs_category ON raw.runs(category_id);