import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()


def run_check(label, query):
    cur.execute(query)
    result = cur.fetchall()
    print(f"\n--- {label} ---")
    for row in result:
        print(f"  {row}")


print("=" * 50)
print("DATA QUALITY REPORT")
print("=" * 50)

run_check("Row counts per raw table", """
    SELECT 'games' AS table_name, COUNT(*) FROM raw.games
    UNION ALL
    SELECT 'categories', COUNT(*) FROM raw.categories
    UNION ALL
    SELECT 'runs', COUNT(*) FROM raw.runs
    UNION ALL
    SELECT 'players', COUNT(*) FROM raw.players;
""")

run_check("Runs with missing player_id", """
    SELECT COUNT(*) AS missing_player,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM raw.runs), 2) AS pct
    FROM raw.runs WHERE player_id IS NULL;
""")

run_check("Runs whose player has no resolved country", """
    SELECT COUNT(*) AS missing_country,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM raw.runs), 2) AS pct
    FROM raw.runs r
    LEFT JOIN raw.players p ON r.player_id = p.player_id
    WHERE p.country_code IS NULL;
""")

run_check("Duplicate run IDs (should be zero)", """
    SELECT run_id, COUNT(*) FROM raw.runs
    GROUP BY run_id HAVING COUNT(*) > 1;
""")

run_check("Runs with missing date_submitted", """
    SELECT COUNT(*) AS missing_date,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM raw.runs), 2) AS pct
    FROM raw.runs WHERE date_submitted IS NULL;
""")

run_check("Categories with zero runs (possible extraction gap)", """
    SELECT c.category_id, c.name, c.game_id
    FROM raw.categories c
    LEFT JOIN raw.runs r ON c.category_id = r.category_id
    WHERE c.type = 'per-game'
    GROUP BY c.category_id, c.name, c.game_id
    HAVING COUNT(r.run_id) = 0;
""")

cur.close()
conn.close()
print("\nDone.")