import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()


def load_runs():
    with open(RAW_DIR / "runs.json") as f:
        runs = json.load(f)

    loaded = 0
    skipped = 0

    for r in runs:
        players = r.get("players", [])
        # take the first player id if present; guest runs may lack an id
        player_id = None
        for p in players:
            if p.get("rel") == "user":
                player_id = p.get("id")
                break

        run_time = r.get("times", {}).get("primary_t")
        date_submitted = r.get("date")  # may be None

        if run_time is None:
            skipped += 1
            continue

        cur.execute(
            """
            INSERT INTO raw.runs (run_id, game_id, category_id, player_id,
                                   run_time_seconds, date_submitted, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO UPDATE
            SET run_time_seconds = EXCLUDED.run_time_seconds,
                date_submitted = EXCLUDED.date_submitted,
                raw_json = EXCLUDED.raw_json,
                fetched_at = now();
            """,
            (r["id"], r["game"], r["category"], player_id,
             run_time, date_submitted, json.dumps(r)),
        )
        loaded += 1

    print(f"Loaded {loaded} runs, skipped {skipped} (missing run time).")


if __name__ == "__main__":
    load_runs()
    conn.commit()
    cur.close()
    conn.close()