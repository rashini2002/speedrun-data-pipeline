import json
import time
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "https://www.speedrun.com/api/v1"
HEADERS = {"User-Agent": "rashini-speedrun-pipeline/1.0"}
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_BETWEEN_REQUESTS = 0.7
MAX_RETRIES = 5
REQUEST_TIMEOUT = (10, 30)


def get_with_retry(url: str) -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as error:
            if attempt == MAX_RETRIES:
                print(f"  Request failed after {MAX_RETRIES} retries: {error}")
                return None

            wait = 2 ** attempt
            print(f"  Request failed. Waiting {wait}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 404:
            # deleted/private user — skip, don't crash the whole run
            return None

        if resp.status_code in (420, 429):
            wait = 2 ** attempt
            print(f"  Rate limited. Waiting {wait}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue

        resp.raise_for_status()

    print(f"  Failed after {MAX_RETRIES} retries: {url}")
    return None


def get_distinct_player_ids(limit=1500) -> list:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT player_id, COUNT(*) AS run_count
        FROM raw.runs
        WHERE player_id IS NOT NULL
        GROUP BY player_id
        ORDER BY run_count DESC
        LIMIT %s;
    """, (limit,))
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return ids

def main():
    player_ids = get_distinct_player_ids(limit=1500)
    print(f"Fetching top {len(player_ids)} players by run count (out of 15,728 total distinct players)")
    

    all_players = []
    not_found = 0

    for i, pid in enumerate(player_ids, start=1):
        data = get_with_retry(f"{BASE_URL}/users/{pid}")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if data is None:
            not_found += 1
            continue

        all_players.append(data["data"])

        if i % 100 == 0:
            print(f"  ...fetched {i}/{len(player_ids)} players")

    with open(RAW_DIR / "players.json", "w") as f:
        json.dump(all_players, f, indent=2)

    print(f"\nSaved {len(all_players)} players to data/raw/players.json")
    print(f"Skipped {not_found} players (deleted/private/not found)")


if __name__ == "__main__":
    main()