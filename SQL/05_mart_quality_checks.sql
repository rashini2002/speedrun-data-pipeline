-- ============================================
-- MART DATA QUALITY CHECKS
-- Run this after rebuilding any staging/mart view.
-- Every query below should return ZERO rows unless noted.
-- ============================================

-- 1. mart_wr_progression: no run should show a HIGHER time than the
--    previous record in the same category (i.e. progression must be
--    monotonically non-increasing over time)
SELECT category_id, submitted_at, run_time_seconds
FROM (
    SELECT
        category_id,
        submitted_at,
        run_time_seconds,
        LAG(run_time_seconds) OVER (PARTITION BY category_id ORDER BY submitted_at) AS prev_time
    FROM marts.mart_wr_progression
) sub
WHERE run_time_seconds > prev_time;
-- Expect: 0 rows. If not, the WR logic has regressed.

-- 2. mart_runner_geography: distinct_runners should never be negative or zero
SELECT * FROM marts.mart_runner_geography WHERE distinct_runners <= 0;
-- Expect: 0 rows.

-- 3. mart_community_activity: no future-dated months (sanity check against bad timestamps)
SELECT * FROM marts.mart_community_activity WHERE activity_month > CURRENT_DATE;
-- Expect: 0 rows.

-- 4. mart_most_improved: pct_improvement should never exceed 100% or be null
--    (100% would mean the current record is literally 0 seconds, which shouldn't happen)
SELECT * FROM marts.mart_most_improved
WHERE pct_improvement IS NULL OR pct_improvement > 100 OR pct_improvement < 0;
-- Expect: 0 rows, OR a small number of legitimate 0%-improvement categories
-- (single-run categories where first_time = current_record_time) — inspect
-- these manually rather than assuming they're bugs.

-- 5. Referential integrity: every category in the marts should trace back
--    to a real game
SELECT DISTINCT m.game_name
FROM marts.mart_wr_progression m
LEFT JOIN staging.stg_games g ON m.game_id = g.game_id
WHERE g.game_id IS NULL;
-- Expect: 0 rows.

-- 6. Row count summary across all marts (informational, not pass/fail)
SELECT 'mart_wr_progression' AS mart, COUNT(*) FROM marts.mart_wr_progression
UNION ALL
SELECT 'mart_runner_geography', COUNT(*) FROM marts.mart_runner_geography
UNION ALL
SELECT 'mart_community_activity', COUNT(*) FROM marts.mart_community_activity
UNION ALL
SELECT 'mart_most_improved', COUNT(*) FROM marts.mart_most_improved;