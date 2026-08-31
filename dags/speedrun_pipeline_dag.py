import sys
sys.path.insert(0, "/opt/airflow/extract")

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator


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


def task_failure_alert(context):
    task_id = context["task_instance"].task_id
    dag_id = context["task_instance"].dag_id
    exec_date = context["execution_date"]
    print(f"ALERT: Task '{task_id}' in DAG '{dag_id}' failed at {exec_date}")


default_args = {
    "owner": "rashini",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": task_failure_alert,
}

with DAG(
    dag_id="speedrun_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["speedrun", "extraction", "transformation"],
    template_searchpath=["/opt/airflow/sql"],
) as dag:

    extract_games = PythonOperator(
        task_id="extract_games",
        python_callable=run_fetch_games,
    )
    load_games = PythonOperator(
        task_id="load_games",
        python_callable=run_load_games,
    )
    extract_runs = PythonOperator(
        task_id="extract_runs",
        python_callable=run_fetch_runs,
        execution_timeout=timedelta(minutes=90),
    )
    load_runs = PythonOperator(
        task_id="load_runs",
        python_callable=run_load_runs,
    )
    extract_players = PythonOperator(
        task_id="extract_players",
        python_callable=run_fetch_players,
        execution_timeout=timedelta(minutes=90),
    )
    load_players = PythonOperator(
        task_id="load_players",
        python_callable=run_load_players,
    )

    run_staging = PostgresOperator(
        task_id="run_staging",
        postgres_conn_id="speedrun_postgres",
        sql="03_staging_models.sql",
    )

    run_mart_wr_progression = PostgresOperator(
        task_id="run_mart_wr_progression",
        postgres_conn_id="speedrun_postgres",
        sql="04_mart_wr_progression.sql",
    )

    run_mart_runner_geography = PostgresOperator(
        task_id="run_mart_runner_geography",
        postgres_conn_id="speedrun_postgres",
        sql="06_mart_runner_geography.sql",
    )

    run_mart_community_and_improvement = PostgresOperator(
        task_id="run_mart_community_and_improvement",
        postgres_conn_id="speedrun_postgres",
        sql="07_mart_community_and_improvement.sql",
    )

    # Extraction chain
    extract_games >> load_games >> extract_runs >> load_runs >> extract_players >> load_players

    # Transformation chain
    load_players >> run_staging
    run_staging >> run_mart_wr_progression >> run_mart_community_and_improvement
    run_staging >> run_mart_runner_geography