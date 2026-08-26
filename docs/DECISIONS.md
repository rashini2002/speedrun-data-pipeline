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

---

## Open questions / things to revisit

- Spelunky vs Spelunky 2 vs Spelunky Classic — currently using base Spelunky 
  (`2685ok6p`); may reconsider since Spelunky 2 likely has more active 
  record-progression history.
- Ori and the Blind Forest (base) vs Definitive Edition — currently using base 
  edition (`9dor8odp`); Definitive Edition may be the more commonly-run version 
  today and could split leaderboards differently.
- Need to confirm how to resolve player country data (`/users/{id}`) at scale 
  without blowing through the rate limit — likely a Day 5 problem.