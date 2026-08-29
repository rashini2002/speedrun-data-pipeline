import sys
sys.path.insert(0, "/opt/airflow/extract")

from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator


def run_fetch_games():
    import fetch_games
    fetch_games.main()


def run_load_games():
    import load_games
    load_games.load_games()
    load_games.load_categories()
    load_games.conn.commit()


def run_fetch_runs():
    import fetch_runs
    fetch_runs.main()


def run_load_runs():
    import load_runs
    load_runs.load_runs()
    load_runs.conn.commit()


def run_fetch_players():
    import fetch_players
    fetch_players.main()


def run_load_players():
    import load_players
    load_players.load_players()
    load_players.conn.commit()


default_args = {
    "owner": "rashini",
}

with DAG(
    dag_id="speedrun_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["speedrun", "extraction"],
) as dag:

    extract_games = PythonOperator(task_id="extract_games", python_callable=run_fetch_games)
    load_games = PythonOperator(task_id="load_games", python_callable=run_load_games)
    extract_runs = PythonOperator(task_id="extract_runs", python_callable=run_fetch_runs)
    load_runs = PythonOperator(task_id="load_runs", python_callable=run_load_runs)
    extract_players = PythonOperator(task_id="extract_players", python_callable=run_fetch_players)
    load_players = PythonOperator(task_id="load_players", python_callable=run_load_players)

    extract_games >> load_games >> extract_runs >> load_runs >> extract_players >> load_players