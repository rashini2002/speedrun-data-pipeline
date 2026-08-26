CREATE TABLE IF NOT EXISTS raw.players (
    player_id     TEXT PRIMARY KEY,
    name          TEXT,
    country_code  TEXT,
    fetched_at    TIMESTAMP DEFAULT now(),
    raw_json      JSONB
);