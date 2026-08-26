CREATE OR REPLACE VIEW marts.mart_community_activity AS
SELECT
    r.game_id,
    g.name AS game_name,
    DATE_TRUNC('month', r.submitted_at)::date AS activity_month,
    COUNT(*) AS runs_submitted
FROM staging.stg_runs r
JOIN staging.stg_games g ON r.game_id = g.game_id
WHERE r.submitted_at IS NOT NULL
GROUP BY r.game_id, g.name, DATE_TRUNC('month', r.submitted_at)
ORDER BY r.game_id, activity_month;


CREATE OR REPLACE VIEW marts.mart_most_improved AS
WITH first_and_last AS (
    SELECT
        category_id,
        category_name,
        game_name,
        FIRST_VALUE(run_time_seconds) OVER (
            PARTITION BY category_id ORDER BY submitted_at
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS first_time,
        FIRST_VALUE(run_time_seconds) OVER (
            PARTITION BY category_id ORDER BY submitted_at DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS current_record_time
    FROM marts.mart_wr_progression
)
SELECT DISTINCT
    category_id,
    category_name,
    game_name,
    first_time,
    current_record_time,
    ROUND(
        100.0 * (first_time - current_record_time) / NULLIF(first_time, 0),
        2
    ) AS pct_improvement
FROM first_and_last
ORDER BY pct_improvement DESC;