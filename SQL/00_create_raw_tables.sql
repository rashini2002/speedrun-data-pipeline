CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.games (
    game_id      TEXT PRIMARY KEY,
    name         TEXT,
    abbreviation TEXT,
    fetched_at   TIMESTAMP DEFAULT now(),
    raw_json     JSONB
);

CREATE TABLE IF NOT EXISTS raw.categories (
    category_id  TEXT PRIMARY KEY,
    game_id      TEXT REFERENCES raw.games(game_id),
    name         TEXT,
    type         TEXT,
    fetched_at   TIMESTAMP DEFAULT now(),
    raw_json     JSONB
);