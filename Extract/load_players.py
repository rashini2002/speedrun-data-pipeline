import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()


def load_players():
    with open(RAW_DIR / "players.json") as f:
        players = json.load(f)

    for p in players:
        name = p.get("names", {}).get("international")
        # country lives in the "location" object; can be entirely absent
        location = p.get("location") or {}
        country = (location.get("country") or {}).get("code")

        cur.execute(
            """
            INSERT INTO raw.players (player_id, name, country_code, raw_json)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (player_id) DO UPDATE
            SET name = EXCLUDED.name,
                country_code = EXCLUDED.country_code,
                raw_json = EXCLUDED.raw_json,
                fetched_at = now();
            """,
            (p["id"], name, country, json.dumps(p)),
        )

    print(f"Loaded {len(players)} players.")


if __name__ == "__main__":
    load_players()
    conn.commit()
    cur.close()
    conn.close()