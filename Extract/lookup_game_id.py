import requests
import time

BASE_URL = "https://www.speedrun.com/api/v1"
HEADERS = {"User-Agent": "rashini-speedrun-pipeline/1.0"}

GAME_NAMES = [
    "Celeste",
    "Hollow Knight",
    "Hades",
    "DOOM 2016",
    "Portal",
    "Ori and the Blind Forest",
    "Katana ZERO",
    "Spelunky",
    "A Hat in Time",
    "Cuphead",
]


def lookup(name: str):
    resp = requests.get(f"{BASE_URL}/games", params={"name": name}, headers=HEADERS)
    resp.raise_for_status()
    results = resp.json()["data"]
    if not results:
        print(f"{name}: NOT FOUND")
        return
    # print top match plus alternates, in case the search is ambiguous
    for g in results[:3]:
        print(f"{name} -> id={g['id']}  matched_name={g['names']['international']}")


if __name__ == "__main__":
    for name in GAME_NAMES:
        lookup(name)
        time.sleep(0.7)