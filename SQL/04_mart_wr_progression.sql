CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE VIEW marts.mart_wr_progression AS
WITH runs_with_running_min AS (
    SELECT
        r.game_id,
        g.name AS game_name,
        r.category_id,
        c.category_name,
        r.run_id,
        r.player_id,
        r.submitted_at,
        r.run_time_seconds,
        MIN(r.run_time_seconds) OVER (
            PARTITION BY r.category_id
            ORDER BY r.submitted_at, r.run_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_record_time
    FROM staging.stg_runs r
    JOIN staging.stg_games g ON r.game_id = g.game_id
    JOIN staging.stg_categories c ON r.category_id = c.category_id
    WHERE r.submitted_at IS NOT NULL
)
SELECT
    game_id,
    game_name,
    category_id,
    category_name,
    run_id,
    player_id,
    submitted_at,
    run_time_seconds,
    running_record_time
FROM runs_with_running_min
WHERE run_time_seconds = running_record_time
ORDER BY category_id, submitted_at;