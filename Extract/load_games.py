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


def load_games():
    with open(RAW_DIR / "games.json") as f:
        games = json.load(f)

    for g in games:
        cur.execute(
            """
            INSERT INTO raw.games (game_id, name, abbreviation, raw_json)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (game_id) DO UPDATE
            SET name = EXCLUDED.name,
                abbreviation = EXCLUDED.abbreviation,
                raw_json = EXCLUDED.raw_json,
                fetched_at = now();
            """,
            (g["id"], g["names"]["international"], g["abbreviation"], json.dumps(g)),
        )
    print(f"Loaded {len(games)} games.")


def load_categories():
    with open(RAW_DIR / "categories.json") as f:
        categories = json.load(f)

    for c in categories:
        # game id comes from the category's own links, find the "game" rel
        game_link = next((l["uri"] for l in c["links"] if l["rel"] == "game"), None)
        game_id = game_link.rstrip("/").split("/")[-1] if game_link else None

        cur.execute(
            """
            INSERT INTO raw.categories (category_id, game_id, name, type, raw_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (category_id) DO UPDATE
            SET name = EXCLUDED.name,
                type = EXCLUDED.type,
                raw_json = EXCLUDED.raw_json,
                fetched_at = now();
            """,
            (c["id"], game_id, c["name"], c["type"], json.dumps(c)),
        )
    print(f"Loaded {len(categories)} categories.")


if __name__ == "__main__":
    load_games()
    load_categories()
    conn.commit()
    cur.close()
    conn.close()