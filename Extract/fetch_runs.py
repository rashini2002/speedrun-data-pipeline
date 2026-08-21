import json
import time
from pathlib import Path

import requests
from games_list import GAMES

BASE_URL = "https://www.speedrun.com/api/v1"
HEADERS = {"User-Agent": "rashini-speedrun-pipeline/1.0"}
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PAGE_SIZE = 200
SLEEP_BETWEEN_REQUESTS = 0.7   # ~85 req/min, safely under the 100/min limit
MAX_RETRIES = 5


def load_categories_for_game(game_id: str, all_categories: list) -> list:
    """Filter to per-game (not per-level) categories for one game."""
    return [
        c for c in all_categories
        if c.get("game_id") == game_id and c.get("type") == "per-game"
    ]


def get_with_retry(url: str, params: dict) -> dict:
    """GET with exponential backoff on rate-limit responses."""
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, params=params, headers=HEADERS)

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code in (420, 429):
            wait = 2 ** attempt  # 2, 4, 8, 16, 32 seconds
            print(f"  Rate limited (HTTP {resp.status_code}). Waiting {wait}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue

        # Any other error: raise so we notice it, don't silently skip
        resp.raise_for_status()

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}")


def fetch_runs_for_category(game_id: str, category_id: str) -> list:
    """Paginate through all verified runs for one game/category."""
    all_runs = []
    offset = 0

    while True:
        params = {
            "game": game_id,
            "category": category_id,
            "status": "verified",
            "max": PAGE_SIZE,
            "offset": offset,
        }
        data = get_with_retry(f"{BASE_URL}/runs", params)
        page_runs = data["data"]
        all_runs.extend(page_runs)

        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if len(page_runs) < PAGE_SIZE:
            break  # last page reached

        offset += PAGE_SIZE

        if offset >= 10000:
            print(f"  WARNING: category {category_id} hit the 10,000-offset "
                  f"pagination ceiling. Data beyond this point may be incomplete.")
            break

    return all_runs


def main():
    with open(RAW_DIR / "categories.json") as f:
        raw_categories = json.load(f)

    # normalize: extract game_id from links, same logic as load_categories()
    categories = []
    for c in raw_categories:
        game_link = next((l["uri"] for l in c["links"] if l["rel"] == "game"), None)
        game_id = game_link.rstrip("/").split("/")[-1] if game_link else None
        categories.append({**c, "game_id": game_id})

    all_runs = []
    summary = {}

    for g in GAMES:
        game_id = g["id"]
        game_categories = load_categories_for_game(game_id, categories)
        game_run_count = 0

        print(f"\n{g['name']} — {len(game_categories)} per-game categories")

        for cat in game_categories:
            print(f"  Fetching runs for category '{cat['name']}' ({cat['id']})...")
            runs = fetch_runs_for_category(game_id, cat["id"])
            all_runs.extend(runs)
            game_run_count += len(runs)
            print(f"    -> {len(runs)} verified runs")

        summary[g["name"]] = game_run_count

    with open(RAW_DIR / "runs.json", "w") as f:
        json.dump(all_runs, f, indent=2)

    print("\n=== Run count summary ===")
    total = 0
    for name, count in summary.items():
        print(f"  {name}: {count}")
        total += count
    print(f"  TOTAL: {total} runs saved to data/raw/runs.json")


if __name__ == "__main__":
    main()