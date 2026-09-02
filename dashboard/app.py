import streamlit as st
import pandas as pd
import psycopg2
import os
import pycountry
import plotly.express as px
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
    return pd.read_sql(
        "SELECT DISTINCT game_name FROM marts.mart_wr_progression ORDER BY game_name;",
        conn,
    )


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


@st.cache_data(ttl=600)
def load_runner_geography(game_name):
    conn = get_connection()
    query = """
        SELECT country_code, distinct_runners
        FROM marts.mart_runner_geography
        WHERE game_name = %s
        ORDER BY distinct_runners DESC;
    """
    return pd.read_sql(query, conn, params=(game_name,))


@st.cache_data(ttl=600)
def load_community_activity(game_name):
    conn = get_connection()
    query = """
        SELECT activity_month, runs_submitted
        FROM marts.mart_community_activity
        WHERE game_name = %s
        ORDER BY activity_month;
    """
    return pd.read_sql(query, conn, params=(game_name,))


@st.cache_data(ttl=600)
def load_most_improved():
    conn = get_connection()
    query = """
        SELECT game_name, category_name, first_time, current_record_time, pct_improvement
        FROM marts.mart_most_improved
        ORDER BY pct_improvement DESC
        LIMIT 15;
    """
    return pd.read_sql(query, conn)


def to_iso3(code):
    try:
        return pycountry.countries.get(alpha_2=code.upper()).alpha_3
    except (AttributeError, LookupError):
        return None


# ---------------- HEADER ----------------
st.title("🏃 Speedrun World Record Tracker")
st.caption("Tracking world record progression across 10 games, built with a Python/Postgres/Airflow pipeline")

games_df = load_games()
game_names = games_df["game_name"].tolist()

selected_game = st.selectbox("Select a game", game_names)

if selected_game:
    # ---------------- WR PROGRESSION ----------------
    progression_df = load_progression(selected_game)

    if progression_df.empty:
        st.warning("No progression data found for this game.")
    else:
        categories = progression_df["category_name"].unique().tolist()
        selected_category = st.selectbox("Select a category", categories)

        filtered = progression_df[progression_df["category_name"] == selected_category]

        st.subheader(f"{selected_game} — {selected_category} World Record Progression")
        st.line_chart(filtered.set_index("submitted_at")["run_time_seconds"])

        st.dataframe(
            filtered[["submitted_at", "run_time_seconds"]].sort_values("submitted_at", ascending=False)
        )

    # ---------------- RUNNER GEOGRAPHY MAP ----------------
    st.subheader(f"Runner Geography — {selected_game}")
    geo_df = load_runner_geography(selected_game)

    geo_df_known = geo_df[geo_df["country_code"] != "unknown"].copy()
    geo_df_known["iso3"] = geo_df_known["country_code"].apply(to_iso3)
    geo_df_known = geo_df_known.dropna(subset=["iso3"])

    if geo_df_known.empty:
        st.info("No resolved country data available for this game.")
    else:
        fig_map = px.choropleth(
            geo_df_known,
            locations="iso3",
            locationmode="ISO-3",
            color="distinct_runners",
            color_continuous_scale="Blues",
            title=f"Distinct Runners by Country — {selected_game}",
        )
        st.plotly_chart(fig_map, use_container_width=True)

    unknown_pct = (
        geo_df[geo_df["country_code"] == "unknown"]["distinct_runners"].sum()
        / geo_df["distinct_runners"].sum()
        * 100
    ) if not geo_df.empty else 0
    st.caption(
        f"Note: {unknown_pct:.1f}% of runners have no resolved country "
        f"(see project notes on player enrichment scope)"
    )

    # ---------------- COMMUNITY ACTIVITY ----------------
    st.subheader(f"Community Activity Over Time — {selected_game}")
    activity_df = load_community_activity(selected_game)
    if not activity_df.empty:
        st.bar_chart(activity_df.set_index("activity_month")["runs_submitted"])

# ---------------- MOST IMPROVED (GLOBAL) ----------------
st.subheader("🚀 Most Improved Categories (All Games)")
improved_df = load_most_improved()
st.dataframe(
    improved_df.rename(
        columns={
            "game_name": "Game",
            "category_name": "Category",
            "first_time": "First Time (s)",
            "current_record_time": "Current Record (s)",
            "pct_improvement": "% Improved",
        }
    ),
    use_container_width=True,
)