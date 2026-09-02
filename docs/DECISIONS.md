# Project Decisions & Build Log

A running log of technical decisions, trade-offs, and what I learned each day. 
Written as I go so it stays honest — this is also my prep material for interviews.

---

## Day 1 — Environment Setup

- Chose **Docker Compose** with Postgres + pgAdmin as the local dev environment, 
  rather than installing Postgres natively, so the whole setup is reproducible 
  and disposable (`docker-compose down -v` wipes it clean if something breaks).
- Used pgAdmin for a browser-based DB UI instead of only the CLI — easier to 
  visually inspect tables while learning.

## Day 2 — API Exploration

- Read the speedrun.com API docs and manually explored endpoints before writing 
  any code, rather than guessing at the JSON shape.
- Confirmed the API is free, read-only, and doesn't require authentication, but 
  does expect a descriptive `User-Agent` header on requests.
- Confirmed two real constraints that shape the rest of this project:
  - **Rate limit:** 100 requests/minute per IP.
  - **Pagination:** results capped at 200 per page via `offset`, and offsets 
    beyond ~10,000 are unreliable — meaning mega-popular games (e.g. Super Mario 
    64, Minecraft) aren't safe to fully extract this way.
- **Decision:** picked 10 games with healthy but not massive speedrunning 
  communities (Celeste, Hollow Knight, Hades, DOOM 2016, Portal, Ori and the 
  Blind Forest, Katana ZERO, Spelunky, A Hat in Time, Cuphead) specifically to 
  stay well under the 10,000-offset pagination ceiling.
- Hit a 404 calling `/leaderboards/{game}/category/{category}` — root cause: 
  the category I picked from the game's `links` array was `"type": "per-level"`, 
  which doesn't expose a direct game-wide leaderboard the same way `"per-game"` 
  categories do. **Decision:** filter to `"type": "per-game"` categories only 
  for this project's main dataset.
- Noticed most API objects include a `links` array with ready-made URIs to 
  related resources (e.g. a game object links directly to its leaderboard) — 
  using these where possible instead of manually constructing every URL.
- Confirmed the real `run` object shape from a live leaderboard call. Key 
  finding: `players` only contains a user **ID**, not a name or country — 
  country requires a separate `/users/{id}` lookup. This directly affects the 
  Week 2 geography mart, which will need a join against player/user data.

## Day 3 — Extraction Script (Games & Categories)

- Searching game names via `/games?name=X` is sometimes ambiguous (e.g. "DOOM" 
  matched Doom 3 (2004) before DOOM (2016)). **Decision:** always verify by 
  checking the `released` year field, not just the first search result, before 
  locking in a game ID.
- Built `lookup_game_id.py` as a small reusable helper to search and print 
  candidate game IDs — faster and less error-prone than reading raw JSON in 
  the browser for every game.
- Saved raw API responses to local JSON files (`data/raw/*.json`) before 
  loading into Postgres, so extraction and loading can be debugged 
  independently — if the DB load fails, I don't need to re-hit the API.
- Loader uses `INSERT ... ON CONFLICT DO UPDATE` (upsert) rather than plain 
  INSERT, so re-running the extraction script is **idempotent** — running it 
  twice won't create duplicate rows. Decided to build this in now rather than 
  bolt it on later, since it's a core data engineering habit.
- Verified in pgAdmin: 10 rows in `raw.games`, all matching the target list; 
  `raw.categories` populated with multiple categories per game, correctly 
  linked via `game_id` parsed out of each category's `links` array.

## Day 4 — Runs Extraction & Pagination

- Built `fetch_runs.py` using the `/runs` endpoint (not `/leaderboards`), 
  filtered by game + category + status=verified, to capture full run 
  history rather than just current leaderboard standings — needed for the 
  Week 2 world-record-progression mart.
- Implemented pagination with a 200-result page size and a stop condition 
  when a page returns fewer than 200 results. Added exponential backoff 
  retry (2s, 4s, 8s...) on HTTP 420/429 rate-limit responses.
- Celeste's "Any%" category hit the known 10,000-offset pagination ceiling 
  (see Day 2 notes) — capped at 10,000 runs for that one category. Accepted 
  as a known limitation rather than building a workaround, since the goal 
  is a representative dataset, not a complete archive.
- Real mistake caught: ran `load_runs.py` immediately after starting 
  `fetch_runs.py` in a second terminal command, before extraction had 
  actually finished — `runs.json` didn't exist yet, so the load ran against 
  nothing and `raw.runs` came back empty. Lesson: long-running scripts need 
  to fully complete before their output is trusted; this is essentially why 
  Airflow enforces task dependencies instead of relying on manual timing 
  between commands (a good preview of Week 3).
- Final result: all 10 games loaded into `raw.runs`, [X] total verified runs 
  across the dataset. [Y] runs skipped due to missing run_time.
````//  grand total to log - 69628

## How to Run Extraction

Run these in order — each step depends on the previous one's output:

```bash
cd extract

# 1. Games & categories
python fetch_games.py
python load_games.py

# 2. Runs (takes a while — has pagination + rate-limit handling)
python fetch_runs.py
python load_runs.py

# 3. Players (also slow — one API call per distinct player)
python fetch_players.py
python load_players.py

# 4. Sanity-check everything
python data_quality_check.py
```

**Important:** each `fetch_*.py` script must fully finish (look for its final 
summary line) before running the matching `load_*.py` script — running them 
too close together will load an incomplete or empty file.

## Open questions / things to revisit

- Spelunky vs Spelunky 2 vs Spelunky Classic — currently using base Spelunky 
  (`2685ok6p`); may reconsider since Spelunky 2 likely has more active 
  record-progression history.
- Ori and the Blind Forest (base) vs Definitive Edition — currently using base 
  edition (`9dor8odp`); Definitive Edition may be the more commonly-run version 
  today and could split leaderboards differently.
- Need to confirm how to resolve player country data (`/users/{id}`) at scale 
  without blowing through the rate limit — likely a Day 5 problem.


## Day 5 — Data Quality Results

Final Week 1 raw data quality report:
- 10 games, 122 categories, 69,628 runs, 1,497 players loaded
- 0.47% of runs missing player_id (guest/anonymous runs) — acceptable
- 49.71% of runs have no resolved player country — expected, direct 
  consequence of capping player enrichment to the top 1,500 of 15,728 
  distinct players (see earlier scoping decision). Geography mart in Week 2 
  will bucket these as "Unknown" rather than dropping them.
- 0 duplicate run IDs — confirms upsert/primary-key logic is working correctly
- 0.16% of runs missing date_submitted — expected, matches known API behavior 
  for older runs
- 0 categories with zero runs — no extraction gaps across the target game list

Conclusion: raw data is clean and trustworthy enough to build Week 2 
transformations on top of. The one significant gap (player country coverage) 
is a documented, deliberate scoping trade-off, not a data quality defect.


## Day 8 — Staging Layer Results

- stg_games: 10 rows (matches raw)
- stg_categories: 102 rows (down from 122 in raw — 20 per-level categories 
  correctly filtered out)
- stg_players: 1,497 rows (matches raw)
- stg_runs: 69,628 rows (matches raw exactly — confirms no runs referenced 
  a filtered-out per-level category, i.e. clean referential integrity 
  between runs and categories)
- Zero duplicate run_ids, zero nulls in required fields — staging layer 
  verified and ready for mart-building.

---

## Day 9 — World Record Progression Mart

- Built mart_wr_progression using a window function: MIN(run_time_seconds) 
  OVER (PARTITION BY category_id ORDER BY date_submitted, run_id) to compute 
  a running minimum (i.e. the record at any point in time) per category.
- Excluded runs with NULL date_submitted (0.16% of runs, per Day 5's data 
  quality report) since they can't be placed on a timeline — a mart-level 
  filter, not a data loss; raw/staging data is untouched.
- Used run_id as a tiebreaker in ORDER BY alongside date_submitted, since 
  multiple runs can share a submission date and window function row 
  ordering for ties is otherwise undefined.
- Final mart keeps only rows where a run's own time equals the running 
  minimum at that point — i.e. only genuine record-breaking (or tying) runs, 
  not every attempt.
- Spot-checked [game name] against the live speedrun.com leaderboard — 
  progression and current record matched.

## Day 9 — Bug Fixed: Timestamp Precision (Resolved)

- Rebuilt stg_runs and mart_wr_progression using submitted_at (full 
  timestamp, backfilled from raw_json) instead of date_submitted (day-only 
  precision).
- Verified fix: Celeste's "Any%" category now shows a strictly decreasing 
  progression (4092.41 -> 3584 -> 3459 -> 3307 -> 3288.123 -> 2993...), 
  confirming the window function correctly identifies genuine record-breaking 
  runs in true chronological order.
- Note on Postgres: CREATE OR REPLACE VIEW cannot insert a column in the 
  middle of an existing view's column list (only append at the end) — had to 
  DROP VIEW ... CASCADE and recreate both stg_runs and mart_wr_progression 
  in dependency order instead.
- Final row count: [X] (down slightly from the earlier ~2,113, since ~233 
  runs with no resolvable timestamp are now correctly excluded).

  Final mart_wr_progression row count: 2,063 (out of 69,395 timestamped runs — 
~3% of runs represent an actual record-breaking moment, which matches 
intuition: most attempts don't beat the existing record).

## Day 10 — Runner Geography Mart

- Built mart_runner_geography joining stg_runs to stg_players via LEFT JOIN 
  (since only the top 1,500 players were resolved in Day 5), with 
  COALESCE(country_code, 'unknown') to capture unresolved players explicitly 
  rather than dropping them.
- 'unknown' is the single largest bucket (14,714 of ~total runners globally, 
  2,457 for Celeste specifically) — expected, given only ~10% of the 15,728 
  distinct players were enriched. This is a transparent consequence of the 
  Day 5 scoping decision, not a data quality defect.
- Top resolved countries globally: US, Canada, France, Germany, Australia, 
  UK — a plausible distribution for these games' speedrunning communities.

  ## Day 11 — Community Activity & Most Improved Marts

- mart_community_activity buckets runs by calendar month using 
  DATE_TRUNC('month', submitted_at) — a reusable pattern for any 
  time-series aggregation.
- mart_most_improved uses FIRST_VALUE() windowed both ascending and 
  descending by submitted_at to capture each category's first-ever and 
  current record time, then computes % improvement. Used NULLIF to guard 
  against division by zero.
- Both marts build directly on Day 9's mart_wr_progression / stg_runs, 
  reinforcing that the WR progression logic is the foundation the rest of 
  the analysis layer depends on.

  ## Day 12 — Data Quality Tests & Cleanup

- Added sql/05_mart_quality_checks.sql as a lightweight substitute for dbt 
  tests: assertions on monotonicity (WR progression never increases), 
  referential integrity, and sane bounds (0-100% improvement).
- Consolidated all mart definitions into numbered SQL files in the repo 
  (previously some existed only in pgAdmin's session, not version-controlled).
- Re-ran check #1 specifically against the Day 9 timestamp bug fix — 
  confirmed 0 violations, meaning the progression logic is now correct 
  end-to-end.

   Quality Checks: All Passed

- Check 1 (WR progression monotonicity): 0 violations — confirms Day 9's 
  timestamp bug fix is holding correctly.
- Check 2 (runner counts > 0): 0 violations.
- Check 4 (most-improved % bounds 0-100, non-null): 0 violations.
- Check 5 (referential integrity to games): 0 violations.
- Final mart row counts: mart_wr_progression (2,063), 
  mart_runner_geography (330), mart_community_activity (1,006), 
  mart_most_improved (102).


## Day 15 — Airflow Setup (Resolved)

- Airflow (webserver, scheduler, dedicated metadata Postgres) added to 
  docker-compose.yml successfully.
- Hit two setup snags: (1) a YAML indentation error placed Airflow services 
  under the wrong top-level key initially; (2) a stale container name 
  conflict from a failed first attempt required manual `docker rm -f` 
  cleanup.
- Verified with hello_world_test DAG: confirmed via `airflow dags list` CLI 
  that the DAG was correctly parsed and mounted, even though the UI 
  initially showed "No results" — a webserver restart (docker restart 
  airflow_webserver) resolved a UI/state sync issue. CLI verification was 
  useful here as a way to isolate "is the DAG actually broken" from "is the 
  UI just stale."
- Confirmed successful manual trigger and run.

## Day 16 — DAG Part 1: Extraction Tasks

- Wrapped existing fetch_*.py/load_*.py scripts as PythonOperator tasks 
  rather than rewriting them, to avoid duplicating logic already built and 
  tested in Days 3-5.
- Imports happen inside each task function (not at DAG file top-level) to 
  avoid triggering side effects (DB connections, .env loading) every time 
  Airflow's scheduler parses the DAG file.
- Had to mount .env into the Airflow containers and change DB_HOST from 
  localhost to postgres (the Docker service name), since "localhost" means 
  something different inside each container.
- Dependency chain: extract_games -> load_games -> extract_runs -> 
  load_runs -> extract_players -> load_players, enforcing the same 
  ordering that was previously done manually and error-pronely (see Day 4's 
  race-condition incident).

  ## Day 16 — DAG Extraction Tasks: Debugging the Secret Key Issue

- Wrapped fetch_*.py/load_*.py scripts as PythonOperator tasks with a linear 
  dependency chain (extract_games -> load_games -> extract_runs -> load_runs 
  -> extract_players -> load_players).
- Hit a "Could not read served logs: 403 Forbidden" error when checking task 
  logs — root cause: Airflow's webserver and scheduler containers each had 
  a different auto-generated secret_key, so the webserver couldn't 
  authenticate to fetch logs from the scheduler's log server. Fixed by 
  setting an explicit, identical AIRFLOW__WEBSERVER__SECRET_KEY across all 
  three Airflow services (webserver, scheduler, init) and doing a full 
  docker-compose down/up (not just up) so the new env var actually applied.
- Also removed a redundant/risky single-file .env mount (already caused an 
  OCI runtime error days earlier) since .env was already being read via the 
  existing extract/ folder mount.
- Once logs were readable, confirmed load_games genuinely succeeded end to 
  end through Airflow (10 games, 122 categories loaded) — matching Day 3's 
  manual run exactly.

## Day 16 — Final Verification

Post-Airflow-run row counts: games (10), categories (122), runs (69,718), 
players (1,499) — consistent with Week 1's manual run numbers (small 
increases in runs/players reflect real new activity on speedrun.com between 
runs, not a data issue). Full extraction pipeline confirmed working 
end-to-end through Airflow.

## Day 17 — DAG Part 2: Transformation Tasks

- Added PostgresOperator tasks for staging and all four marts, chained 
  after load_players with correct dependency ordering: mart_most_improved 
  depends on mart_wr_progression (reads from it), while mart_runner_geography 
  only depends on staging and can run independently.

- Hit four distinct bugs before this worked end-to-end:

  1. **Missing dependency lines.** The transformation chain comment 
     (`# Transformation chain`) was left in the DAG file with no actual 
     `>>` operators underneath it. This meant run_staging and all four mart 
     tasks had no upstream dependency at all — they started immediately on 
     trigger, running in parallel with the extraction chain against 
     stale/incomplete data, and all failed.

  2. **Jinja template path resolution.** PostgresOperator's `sql` parameter 
     treats any string ending in `.sql` as a Jinja template reference, not 
     a literal filesystem path. Passing an absolute path 
     (`/opt/airflow/sql/file.sql`) raised `jinja2.exceptions.TemplateNotFound` 
     even though the file existed at that exact path. Fixed by adding 
     `template_searchpath=["/opt/airflow/sql"]` to the DAG definition and 
     switching all four PostgresOperator tasks to relative filenames 
     (e.g. `"03_staging_models.sql"`).

  3. **Missing Airflow Connection.** The `speedrun_postgres` connection 
     (originally set up on Day 15 via the UI) no longer existed — likely 
     lost during an earlier `docker-compose down`/`up` cycle, since 
     Connections are stored in Airflow's metadata database, and that data 
     doesn't survive certain container rebuild patterns. Recreated it via 
     the CLI for speed and reproducibility:
      airflow connections add speedrun_postgres --conn-type postgres 
   --conn-host postgres --conn-schema speedrun_db 
   --conn-login speedrun_admin --conn-password speedrun_pass 
   --conn-port 5432

        Lesson: CLI-based connection setup is more reproducible than UI setup 
     for a project meant to be rebuildable from scratch.

  4. **Truncated SQL file.** `sql/03_staging_models.sql` was missing its 
     final line (`AND category_id IN (SELECT category_id FROM 
     staging.stg_categories);`), causing a genuine 
     `psycopg2.errors.SyntaxError: syntax error at end of input`. The file 
     had been cut off, likely during an earlier copy/paste or save. Fixed 
     by restoring the missing clause and verifying with `tail -3` before 
     rerunning.

- **Debugging approach:** rather than repeatedly triggering the full DAG 
  (which requires waiting through the ~90-minute extraction chain each 
  time), used `airflow tasks test <dag_id> <task_id> <date>` to run each 
  new task in isolation, bypassing dependencies entirely. This gave fast, 
  direct feedback on each bug without needing to re-run extraction, and 
  surfaced the real Python/SQL tracebacks directly in the terminal rather 
  than needing to dig through the Airflow UI's log viewer.

- **Final verification:** queried all four mart tables directly and 
  confirmed row counts exactly match Week 2's manually-verified numbers:
  - mart_wr_progression: 2,063
  - mart_runner_geography: 330
  - mart_community_activity: 1,006
  - mart_most_improved: 102

  This confirms the Airflow-orchestrated transformation layer produces 
  identical, correct output to the original manually-run SQL — the 
  orchestration wrapper introduced no data discrepancies, only the four 
  infrastructure/configuration bugs listed above.

## Day 19 — Idempotency Verification

- Rather than triggering another full ~90 minute DAG run purely to 
  re-demonstrate idempotency, verified it using evidence already available: 
  the pipeline has run multiple times this week (Days 16-18 testing plus 
  the @daily schedule), writing to the same raw.* tables each time via 
  ON CONFLICT DO UPDATE upserts (built Days 3-5).
- Ran a direct primary-key duplication check across all four raw tables:
  games (0 duplicates), categories (0), runs (0), players (0).
- This confirms the upsert logic has correctly prevented duplication 
  across every real run so far — not just a single isolated test, but 
  the accumulated result of a full week's worth of genuine re-runs.
- Marts (staging + 4 marts) are views, so CREATE OR REPLACE VIEW / 
  DROP VIEW CASCADE inherently redefine rather than accumulate — no 
  duplication risk there by construction.
- Conclusion: idempotency was effectively built and continuously validated 
  from Day 3 onward, proven definitively today with a direct primary-key 
  check rather than just count comparisons.

## Day 20 — Clean Rebuild Test: Complete Success

- After fixing the two schema gaps (staging schema creation, submitted_at 
  column), ran a full docker-compose down -v + up, recreated the Airflow 
  connection, and triggered the DAG fresh against a completely empty 
  database.
- extract_runs hit the 90-minute timeout on the first attempt (network 
  variability, consistent with earlier days) — cleared and retried, 
  completed successfully on the second run.
- Final verification: all raw tables and all four marts rebuilt correctly 
  from nothing, with row counts consistent with previous runs.
- This confirms the project is genuinely reproducible end-to-end from the 
  GitHub repo alone — not dependent on any leftover manual state. The two 
  gaps found today (staging schema, submitted_at column) would have been 
  invisible without this full clean-slate test, reinforcing that 
  incremental testing alone cannot catch this class of issue.

## Day 20 — Third Gap: submitted_at Backfill Timing

- Even after fixing the column definition, mart_wr_progression and 
  mart_community_activity came back with 0 rows post-rebuild. Root cause: 
  the submitted_at backfill (UPDATE ... SET submitted_at = ...) was placed 
  in 01_create_raw_runs.sql, which only runs once at initial schema setup 
  — before any run data exists. It never re-executes after fresh extraction.
- Fixed by moving the backfill UPDATE into 03_staging_models.sql (idempotent, 
  WHERE submitted_at IS NULL guard), so it re-runs every time staging 
  executes — correctly catching newly-loaded runs each time the DAG runs.
- Third gap found via the same clean-rebuild test — reinforces that 
  ordering/timing of one-off manual fixes matters as much as whether 
  they're captured in files at all.

## Day 22 — Dashboard Skeleton (Complete)

- Built dashboard/app.py with Streamlit: game/category selectors and a 
  line chart of world record progression, querying marts.mart_wr_progression 
  directly via psycopg2.
- Hit a Python environment mismatch: `streamlit` resolved to a system-wide 
  Python 3.12 install instead of the project's venv (Python 3.10), causing 
  a ModuleNotFoundError for psycopg2 even though it was correctly installed 
  in the venv. Fixed by launching with `python3 -m streamlit run app.py` 
  instead of the bare `streamlit` command, which forces use of the active 
  venv's interpreter.
- Verified working end-to-end: dropdowns populate from real data, chart 
  renders a correct WR progression curve (A Hat in Time Any%, 2018-2024) 
  matching the expected shape — large early improvements flattening into 
  small incremental gains over time.

## Day 23 — World Map & Remaining Charts

- Added runner geography choropleth map, community activity bar chart, 
  and a global "most improved categories" table to the dashboard.
- Real gotcha: speedrun.com returns 2-letter (ISO-2) country codes, but 
  Plotly's choropleth locationmode="ISO-3" expects 3-letter codes — a 
  mismatch that would silently render an empty map with no error. Fixed 
  using pycountry to convert alpha-2 to alpha-3 codes before plotting.
- Excluded 'unknown' country rows from the map itself but surfaced the 
  percentage as a caption, rather than hiding the data-scope limitation 
  from viewers.

## Day 23 — World Map & Remaining Charts (Complete)

- Added runner geography choropleth map (fixed via pycountry ISO-2 → ISO-3 
  conversion), community activity bar chart, and global most-improved 
  table.
- Verified working end-to-end: map correctly shows US/Canada/Australia 
  colored by runner density for A Hat in Time; caption transparently 
  states 83.8% of runners have no resolved country, rather than hiding 
  the data-scope limitation.
- Dashboard now covers all four marts built in Week 2, giving a complete 
  visual layer on top of the pipeline.


## Day 24 — Dashboard Polish (Complete)

- Redesigned the dashboard with a custom dark theme (Electric Violet / 
  Matrix Teal / Obsidian Blue palette) using CSS injection + a 
  .streamlit/config.toml theme override, styled as a card-based grid 
  layout inspired by analytics dashboard references.
- Fixed two real bugs during polish: (1) Plotly's Layout object isn't 
  dict-unpackable via **, needed a style_fig() helper function instead; 
  (2) a fixed header height in custom CSS was clipping the title's letter 
  tops — fixed by removing the height override and adding top padding to 
  the block container instead.
- Migrated from deprecated use_container_width=True to width='stretch' 
  ahead of Streamlit's 2025-12-31 removal deadline.
- Final result: KPI row, WR progression chart, runner geography map, 
  community activity chart, and most-improved table all rendering 
  consistently within roughly one scroll, with the palette applied 
  uniformly across every component.

## Day 24 (extended) — Advanced Dashboard Redesign

- Rebuilt the dashboard with a custom dark theme (Electric Violet / Matrix 
  Teal / Obsidian Blue), card-based grid layout, and a tabbed structure 
  (Game Dashboard / Global Search / Most Improved) instead of one long 
  scroll.
- Added unique, non-obvious features beyond the original mart visualizations:
  - "Days Since Last WR" and "Avg Days Between Records" — computed 
    velocity metrics per category, not directly present in any mart, 
    calculated live from mart_wr_progression timestamps.
  - Global search tab — lets users search across all games/categories/
    players at once, rather than browsing one game at a time.
  - CSV export button on the WR progression chart.
- Replaced the emoji header with a custom pixel-art trophy image, base64-
  encoded inline since Streamlit/browsers can't resolve local file paths 
  directly inside markdown HTML.
- Converted the runner geography map to a horizontal color legend 
  (matching a reference analytics-dashboard style) and enlarged it to 
  visually balance against the WR progression card.
- Debugged several real issues during this session: Plotly Layout objects 
  aren't dict-unpackable (needed a style_fig() helper), a stray invisible 
  character caused a silent syntax error, and a missing iso3 conversion 
  step (lost during editing) caused a ValueError — each traced and fixed 
  by reading the actual traceback rather than guessing.