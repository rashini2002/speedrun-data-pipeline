# Speedrun World Record Data Pipeline

A data engineering pipeline that extracts world record and player data from the 
[speedrun.com API](https://github.com/speedruncomorg/api), transforms it into 
analysis-ready tables, and visualizes world record progression and runner geography 
on an interactive dashboard. Built as a hands-on project to practice core data 
engineering skills: API extraction, orchestration, SQL transformation, and 
containerized local development.

## Architecture
speedrun.com API (games -> categories -> runs -> players)
|
v
Python extraction scripts (requests, pagination, retry logic)
|
v
Postgres - raw schema (landing zone)
|
v
SQL / dbt transformations (staging -> marts)
|
v
Apache Airflow (schedules extract -> load -> transform)
|
v
Streamlit dashboard (record progression + runner geography map)


## Tech Stack

- **Extraction:** Python (requests)
- **Storage:** PostgreSQL
- **Transformation:** SQL / dbt
- **Orchestration:** Apache Airflow
- **Dashboard:** Streamlit
- **Environment:** Docker Compose


## Target Games

10 games spanning multiple genres (platformer, metroidvania, roguelike, FPS, puzzle). 
Full list with speedrun.com IDs in [`docs/games.md`](docs/games.md).

## Data Scope

- **Runs:** all verified runs across 10 games' per-game categories (~65,000+ runs). 
  One category (Celeste "Any%") hit the speedrun.com API's known 10,000-offset 
  pagination limit — accepted as a documented data limitation, not a bug.
- **Players:** enriched the top 1,500 most active players (by run count) out of 
  15,728 distinct players found in the run history, to keep extraction time 
  reasonable (~17 min vs. ~3 hrs for full resolution). See 
  [`docs/DECISIONS.md`](docs/DECISIONS.md) for the full reasoning.

## Setup

**Requirements:** Docker Desktop, Python 3.10+

```bash
# 1. Start Postgres + pgAdmin
docker-compose up -d

# 2. Create raw schema and tables
docker exec -i speedrun_postgres psql -U speedrun_admin -d speedrun_db < sql/00_create_raw_tables.sql
docker exec -i speedrun_postgres psql -U speedrun_admin -d speedrun_db < sql/01_create_raw_runs.sql
docker exec -i speedrun_postgres psql -U speedrun_admin -d speedrun_db < sql/02_create_raw_players.sql

# 3. Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Copy .env.example to .env and fill in DB credentials
cp .env.example .env
```

Postgres runs on `localhost:5432`, pgAdmin on `localhost:5050`.

## How to Run Extraction

Run these in order from the `extract/` folder — each step depends on the 
previous one's output. **Important:** each `fetch_*.py` script must fully 
finish (look for its final summary line, e.g. "Saved X players...") before 
running the matching `load_*.py` script. Running them too close together, or 
interrupting a fetch script partway, will load an incomplete or empty file.

```bash
cd extract

# 1. Games & categories (~1 min)
python fetch_games.py
python load_games.py

# 2. Runs — has pagination + rate-limit handling (~20-30 min)
python fetch_runs.py
python load_runs.py

# 3. Players — one API call per player, capped at top 1,500 (~17-18 min)
python fetch_players.py
python load_players.py

# 4. Sanity-check everything
python data_quality_check.py
```

## Repo Structure
/extract - Python scripts to pull data from the speedrun.com API

/sql        - Raw table schemas, staging views, and mart definitions (run in

              numeric order: 00 through 07)
/dags - Airflow DAG definitions

/dashboard - Streamlit app

/docs - Notes, decisions, and game list


## Notes & Decisions

Build log and technical decisions tracked in [`docs/DECISIONS.md`](docs/DECISIONS.md), 
including real debugging moments (API pagination limits, a 404 caused by a 
per-level vs. per-game category mismatch, and a race condition from running a 
load script before extraction had finished).

## What This Project Demonstrates

- API extraction with pagination and rate-limit handling (exponential backoff)
- Idempotent data loading (safe to re-run without duplicating data)
- Documented data-scoping decisions under real-world constraints (API limits, time)
- SQL window functions for time-series record tracking (coming in Week 2)
- Pipeline orchestration with Apache Airflow (coming in Week 3)
- End-to-end containerized local development
