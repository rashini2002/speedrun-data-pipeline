import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Speedrun World Record Tracker", layout="wide")

@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "speedrun_db"),
        user=os.getenv("DB_USER", "speedrun_admin"),
        password=os.getenv("DB_PASSWORD", "speedrun_pass"),
    )

@st.cache_data(ttl=600)
def load_games():
    conn = get_connection()
    return pd.read_sql("SELECT DISTINCT game_name FROM marts.mart_wr_progression ORDER BY game_name;", conn)

@st.cache_data(ttl=600)
def load_progression(game_name):
    conn = get_connection()
    query = """
        SELECT category_name, submitted_at, run_time_seconds
        FROM marts.mart_wr_progression
        WHERE game_name = %s
        ORDER BY submitted_at;
    """
    return pd.read_sql(query, conn, params=(game_name,))

st.title("🏃 Speedrun World Record Tracker")
st.caption("Tracking world record progression across 10 games, built with a Python/Postgres/Airflow pipeline")

games_df = load_games()
game_names = games_df["game_name"].tolist()

selected_game = st.selectbox("Select a game", game_names)

if selected_game:
    progression_df = load_progression(selected_game)

    if progression_df.empty:
        st.warning("No progression data found for this game.")
    else:
        categories = progression_df["category_name"].unique().tolist()
        selected_category = st.selectbox("Select a category", categories)

        filtered = progression_df[progression_df["category_name"] == selected_category]

        st.subheader(f"{selected_game} — {selected_category} World Record Progression")
        st.line_chart(filtered.set_index("submitted_at")["run_time_seconds"])

        st.dataframe(filtered[["submitted_at", "run_time_seconds"]].sort_values("submitted_at", ascending=False))