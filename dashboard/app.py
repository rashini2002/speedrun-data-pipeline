import streamlit as st
import pandas as pd
import psycopg2
import os
import pycountry
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Speedrun World Record Tracker", layout="wide", initial_sidebar_state="collapsed")

# ---------------- THEME ----------------
PRIMARY = "#7C4DFF"
SECONDARY = "#00FFCC"
BG = "#0B0F1A"
CARD_BG = "#1A1F2C"
TEXT = "#F7F7FF"

st.markdown(f"""
<style>
    .stApp {{ background-color: {BG}; color: {TEXT}; }}
    section[data-testid="stSidebar"] {{ background-color: {CARD_BG}; }}
    div.block-container {{
        padding-top: 2 rem;
        padding-bottom: 0.5rem;
        max-width: 100%;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: {CARD_BG};
    border-radius: 12px;
    padding: 14px 16px 6px 16px;
    border: 1px solid #2A3040;
    min-height: 700px;
    }}
    h1, h2, h3, h4 {{
        color: {TEXT} !important;
        line-height: 1.4 !important;
        padding-top: 4px;
    }}
    .card-title {{ font-size: 13px; font-weight: 600; color: {SECONDARY}; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
    .metric-num {{ font-size: 28px; font-weight: 700; color: {PRIMARY}; }}
    .metric-label {{ font-size: 12px; color: #9AA0B4; }}
    div[data-baseweb="select"] > div {{ background-color: {BG}; border-color: #2A3040; }}
    .stCaption, .stMarkdown p {{ color: #9AA0B4; }}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{ background-color: {BG}; }}
</style>
""", unsafe_allow_html=True)

def style_fig(fig, height=240):
    fig.update_layout(
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        font=dict(color=TEXT, size=11),
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
        showlegend=False,
        xaxis=dict(gridcolor="#2A3040", zerolinecolor="#2A3040"),
        yaxis=dict(gridcolor="#2A3040", zerolinecolor="#2A3040"),
    )
    return fig

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
        FROM marts.mart_wr_progression WHERE game_name = %s ORDER BY submitted_at;
    """
    return pd.read_sql(query, conn, params=(game_name,))


@st.cache_data(ttl=600)
def load_runner_geography(game_name):
    conn = get_connection()
    query = """
        SELECT country_code, distinct_runners
        FROM marts.mart_runner_geography WHERE game_name = %s ORDER BY distinct_runners DESC;
    """
    return pd.read_sql(query, conn, params=(game_name,))


@st.cache_data(ttl=600)
def load_community_activity(game_name):
    conn = get_connection()
    query = """
        SELECT activity_month, runs_submitted
        FROM marts.mart_community_activity WHERE game_name = %s ORDER BY activity_month;
    """
    return pd.read_sql(query, conn, params=(game_name,))


@st.cache_data(ttl=600)
def load_most_improved():
    conn = get_connection()
    query = """
        SELECT game_name, category_name, first_time, current_record_time, pct_improvement
        FROM marts.mart_most_improved ORDER BY pct_improvement DESC LIMIT 8;
    """
    return pd.read_sql(query, conn)


@st.cache_data(ttl=600)
def get_summary_stats():
    conn = get_connection()
    return pd.read_sql("""
        SELECT
            (SELECT COUNT(DISTINCT game_id) FROM staging.stg_games) AS games,
            (SELECT COUNT(*) FROM staging.stg_runs) AS runs,
            (SELECT COUNT(*) FROM staging.stg_players) AS players,
            (SELECT MAX(submitted_at) FROM staging.stg_runs) AS last_run;
    """, conn)


def to_iso3(code):
    try:
        return pycountry.countries.get(alpha_2=code.upper()).alpha_3
    except (AttributeError, LookupError):
        return None

import base64

def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

trophy_b64 = get_base64_image("assets/image.png")

@st.cache_data(ttl=600)
def load_record_velocity(game_name, category_name):
    conn = get_connection()
    query = """
        SELECT submitted_at
        FROM marts.mart_wr_progression
        WHERE game_name = %s AND category_name = %s
        ORDER BY submitted_at;
    """
    df = pd.read_sql(query, conn, params=(game_name, category_name))
    if len(df) < 2:
        return None, None
    days_since_last = (pd.Timestamp.now() - df["submitted_at"].iloc[-1]).days
    total_days = (df["submitted_at"].iloc[-1] - df["submitted_at"].iloc[0]).days
    avg_days_between = total_days / max(len(df) - 1, 1)
    return days_since_last, round(avg_days_between, 1)


@st.cache_data(ttl=600)
def load_all_records_search():
    conn = get_connection()
    query = """
        SELECT game_name, category_name, player_id, run_time_seconds, submitted_at
        FROM marts.mart_wr_progression
        ORDER BY submitted_at DESC;
    """
    return pd.read_sql(query, conn)


# ---------------- HEADER ----------------
h1, h2 = st.columns([3, 1])
with h1:
    st.markdown(
    f"""
    <h2 style='margin-bottom:2px; display:flex; align-items:center; gap:10px;'>
        <img src="data:image/png;base64,{trophy_b64}" width="40" height="40" style="image-rendering:pixelated;">
        Speedrun World Record Tracker
    </h2>
    """,
    unsafe_allow_html=True,
)
    st.caption("Python · PostgreSQL · Apache Airflow · Streamlit — a live, self-updating pipeline dashboard")
    st.caption("Tracking world record progression, runner geography, and community activity across 10 speedrun games")

stats = get_summary_stats()
with h2:
    if not stats.empty and stats["last_run"].iloc[0] is not None:
        st.markdown(
            f"<div style='margin-top: 14px; text-align: right; color: #9AA0B4; font-size: 14px;'>"
            f"📅 Data as of {stats['last_run'].iloc[0]:%b %d, %Y}</div>",
            unsafe_allow_html=True,
        )

# ---------------- TOP KPI ROW ----------------
k1, k2, k3, k4 = st.columns(4)
kpi_defs = [
    (k1, "Games Tracked", int(stats["games"].iloc[0]) if not stats.empty else 0),
    (k2, "Total Runs", f"{int(stats['runs'].iloc[0]):,}" if not stats.empty else 0),
    (k3, "Players", f"{int(stats['players'].iloc[0]):,}" if not stats.empty else 0),
]
for col, label, val in kpi_defs:
    with col:
        with st.container(border=True):
            st.markdown(f"<div class='metric-num'>{val}</div><div class='metric-label'>{label}</div>", unsafe_allow_html=True)

games_df = load_games()
game_names = games_df["game_name"].tolist()
with k4:
    with st.container(border=True):
        st.markdown("<div class='card-title'>Select Game</div>", unsafe_allow_html=True)
        selected_game = st.selectbox("", game_names, label_visibility="collapsed")

tab1, tab2, tab3 = st.tabs(["📊 Game Dashboard", "🔍 Global Search", "🚀 Most Improved"])

with tab1:
    row1_left, row1_right = st.columns([2, 1])
    progression_df = load_progression(selected_game) if selected_game else pd.DataFrame()

    with row1_left:
        with st.container(border=True):
            st.markdown("<div class='card-title'>World Record Progression</div>", unsafe_allow_html=True)
            if progression_df.empty:
                st.info("No data.")
            else:
                categories = progression_df["category_name"].unique().tolist()
                selected_category = st.selectbox("Category", categories, label_visibility="collapsed")
                filtered = progression_df[progression_df["category_name"] == selected_category]

                days_since, avg_days = load_record_velocity(selected_game, selected_category)
                m1, m2 = st.columns(2)
                with m1:
                    st.metric("Days Since Last WR", days_since if days_since is not None else "—")
                with m2:
                    st.metric("Avg Days Between Records", avg_days if avg_days is not None else "—")

                fig = px.line(filtered, x="submitted_at", y="run_time_seconds",
                              labels={"submitted_at": "", "run_time_seconds": "Seconds"})
                fig = style_fig(fig, height=320)
                fig.update_traces(line_color=SECONDARY, line_width=2)
                st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

                csv = filtered[["submitted_at", "run_time_seconds"]].to_csv(index=False)
                st.download_button("⬇️ Download this data (CSV)", csv,
                                    file_name=f"{selected_game}_{selected_category}_wr_history.csv")

    with row1_right:
      with st.container(border=True):
        st.markdown("<div class='card-title'>Runner Geography</div>", unsafe_allow_html=True)

        geo_df = load_runner_geography(selected_game) if selected_game else pd.DataFrame()
        geo_known = geo_df[geo_df["country_code"] != "unknown"].copy() if not geo_df.empty else geo_df

        if not geo_known.empty:
            geo_known["iso3"] = geo_known["country_code"].apply(to_iso3)
            geo_known = geo_known.dropna(subset=["iso3"])

        if geo_known is None or geo_known.empty:
            st.info("No resolved country data.")
        else:
            fig_map = px.choropleth(
                geo_known,
                locations="iso3",
                locationmode="ISO-3",
                color="distinct_runners",
                color_continuous_scale=[CARD_BG, SECONDARY],
            )
            fig_map = style_fig(fig_map, height=480)
            fig_map.update_geos(
                bgcolor=CARD_BG,
                showframe=False,
                projection_type="natural earth",
            )
            fig_map.update_layout(
                coloraxis_colorbar=dict(
                    orientation="h",
                    title="Distinct Runners",
                    title_side="top",
                    y=-0.15,
                    x=0.5,
                    xanchor="center",
                    len=0.7,
                    thickness=12,
                ),
                margin=dict(l=0, r=0, t=10, b=40),
            )
            st.plotly_chart(fig_map, width='stretch', config={"displayModeBar": False})

        unk_pct = (
            geo_df[geo_df["country_code"] == "unknown"]["distinct_runners"].sum()
            / geo_df["distinct_runners"].sum()
            * 100
        ) if not geo_df.empty and geo_df["distinct_runners"].sum() > 0 else 0
        st.caption(f"{unk_pct:.0f}% unresolved country data")


    with st.container(border=True):
        st.markdown("<div class='card-title'>Community Activity</div>", unsafe_allow_html=True)
        activity_df = load_community_activity(selected_game) if selected_game else pd.DataFrame()
        if not activity_df.empty:
            fig_act = px.bar(activity_df, x="activity_month", y="runs_submitted",
                             labels={"activity_month": "", "runs_submitted": "Runs"})
            fig_act = style_fig(fig_act, height=180)
            fig_act.update_traces(marker_color=PRIMARY)
            st.plotly_chart(fig_act, width='stretch', config={"displayModeBar": False})

with tab2:
    st.markdown("<div class='card-title'>Search All World Records</div>", unsafe_allow_html=True)
    search_term = st.text_input("Search by game, category, or player ID", "")
    all_records = load_all_records_search()
    if search_term:
        mask = (
            all_records["game_name"].str.contains(search_term, case=False, na=False)
            | all_records["category_name"].str.contains(search_term, case=False, na=False)
            | all_records["player_id"].str.contains(search_term, case=False, na=False)
        )
        results = all_records[mask]
    else:
        results = all_records.head(50)
    st.dataframe(results, width='stretch', height=500, hide_index=True)
    st.caption(f"{len(results):,} records shown" + ("" if search_term else " (showing 50 most recent — type to search all)"))

with tab3:
    st.markdown("<div class='card-title'>🚀 Most Improved Categories (All Games)</div>", unsafe_allow_html=True)
    st.caption("Categories with the largest % drop between the first recorded run and the current world record.")
    improved_df = load_most_improved()
    st.dataframe(
        improved_df.rename(columns={
            "game_name": "Game", "category_name": "Category",
            "first_time": "First Time (s)", "current_record_time": "Current Record (s)",
            "pct_improvement": "% Improved",
        }),
        width='stretch', hide_index=True,
    )