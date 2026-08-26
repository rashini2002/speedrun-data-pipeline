-- stg_games: clean, typed game reference data
CREATE OR REPLACE VIEW staging.stg_games AS
SELECT
    game_id,
    name,
    abbreviation
FROM raw.games;


-- stg_categories: only per-game categories (per-level excluded, per Day 2 decision)
CREATE OR REPLACE VIEW staging.stg_categories AS
SELECT
    category_id,
    game_id,
    name AS category_name,
    type AS category_type
FROM raw.categories
WHERE type = 'per-game';


-- stg_players: clean player reference data, bucket missing country as 'Unknown'
CREATE OR REPLACE VIEW staging.stg_players AS
SELECT
    player_id,
    COALESCE(name, 'Unknown') AS player_name,
    COALESCE(country_code, 'unknown') AS country_code
FROM raw.players;


-- stg_runs: typed, cleaned runs — the core fact table for everything downstream
CREATE OR REPLACE VIEW staging.stg_runs AS
SELECT
    run_id,
    game_id,
    category_id,
    player_id,
    run_time_seconds,
    date_submitted,
    -- flag runs we can't fully attribute, rather than silently dropping them
    (player_id IS NULL) AS is_missing_player,
    (date_submitted IS NULL) AS is_missing_date
FROM raw.runs
WHERE run_time_seconds IS NOT NULL   -- already filtered in load_runs.py, but explicit here
  AND category_id IN (SELECT category_id FROM staging.stg_categories);  -- drop per-level leftovers, if any