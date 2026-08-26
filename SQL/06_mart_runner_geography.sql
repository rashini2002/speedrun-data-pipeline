CREATE OR REPLACE VIEW marts.mart_runner_geography AS
SELECT
    r.game_id,
    g.name AS game_name,
    COALESCE(p.country_code, 'unknown') AS country_code,
    COUNT(DISTINCT r.player_id) AS distinct_runners
FROM staging.stg_runs r
JOIN staging.stg_games g ON r.game_id = g.game_id
LEFT JOIN staging.stg_players p ON r.player_id = p.player_id
GROUP BY r.game_id, g.name, COALESCE(p.country_code, 'unknown')
ORDER BY r.game_id, distinct_runners DESC;