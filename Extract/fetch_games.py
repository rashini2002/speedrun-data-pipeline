import json
import time
import requests
from pathlib import Path
from games_list import GAMES

BASE_URL = "https://www.speedrun.com/api/v1"
HEADERS = {"User-Agent": "rashini-speedrun-pipeline/1.0"}
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def fetch_game(game_id: str) -> dict:
    url = f"{BASE_URL}/games/{game_id}"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["data"]


def fetch_categories(game_id: str) -> list:
    url = f"{BASE_URL}/games/{game_id}/categories"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["data"]


def main():
    all_games = []
    all_categories = []

    for g in GAMES:
        print(f"Fetching {g['name']} ({g['id']})...")
        game_data = fetch_game(g["id"])
        all_games.append(game_data)

        categories = fetch_categories(g["id"])
        all_categories.extend(categories)

        time.sleep(0.7)  # stay well under the 100 req/min rate limit

    with open(RAW_DIR / "games.json", "w") as f:
        json.dump(all_games, f, indent=2)

    with open(RAW_DIR / "categories.json", "w") as f:
        json.dump(all_categories, f, indent=2)

    print(f"Saved {len(all_games)} games and {len(all_categories)} categories.")


if __name__ == "__main__":
    main()