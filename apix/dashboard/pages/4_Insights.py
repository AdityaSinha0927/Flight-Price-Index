"""Simple, live insights derived from APIx's stored quote and index data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


DB_PATH = Path(__file__).resolve().parents[2] / "db" / "apix.db"
WINDOW_ORDER = ("T1", "T7", "T30")
WINDOW_LABELS = {
    "T1": "1 day ahead",
    "T7": "7 days ahead",
    "T30": "30 days ahead",
}


@st.cache_data(ttl=60, show_spinner=False)
def load_insight_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read quote and route-index data without changing the database."""
    if not DB_PATH.exists():
        return pd.DataFrame(), pd.DataFrame()

    quotes_query = """
        SELECT route, search_date, advance_window, total_fare, is_outlier
        FROM clean_quotes
        WHERE total_fare IS NOT NULL
    """
    index_query = """
        SELECT index_date, route, index_value, num_quotes_used
        FROM index_values
        WHERE route != 'ALL'
        ORDER BY index_date, route
    """
    with sqlite3.connect(DB_PATH) as connection:
        quotes = pd.read_sql_query(quotes_query, connection)
        route_index = pd.read_sql_query(index_query, connection)
    return quotes, route_index


def fare_summary(quotes: pd.DataFrame) -> pd.DataFrame:
    usable = quotes[quotes["is_outlier"].eq(0)].copy()
    return (
        usable.groupby(["route", "advance_window"], as_index=False)
        .agg(avg_total_fare=("total_fare", "mean"), quote_count=("total_fare", "count"))
    )


def recommendation(route: str, route_summary: pd.DataFrame) -> str:
    available = route_summary.set_index("advance_window")
    cheapest_window = route_summary.loc[route_summary["avg_total_fare"].idxmin(), "advance_window"]
    cheapest_fare = float(available.loc[cheapest_window, "avg_total_fare"])

    if "T1" not in available.index:
        return f"The 1-day-ahead comparison is not available yet for {route}."

    one_day_fare = float(available.loc["T1", "avg_total_fare"])
    if cheapest_window == "T1" or one_day_fare <= 0:
        return (
            f"Booking 1 day ahead for {route} currently has the lowest average fare "
            f"at ₹{one_day_fare:,.0f}."
        )

    saving_pct = (one_day_fare - cheapest_fare) / one_day_fare * 100
    return (
        f"Booking {WINDOW_LABELS[cheapest_window]} for {route} is on average "
        f"{saving_pct:.1f}% cheaper than booking 1 day ahead."
    )


def volatility_ranking(quotes: pd.DataFrame, route_index: pd.DataFrame) -> pd.DataFrame:
    usable = quotes[quotes["is_outlier"].eq(0)].copy()
    usable["search_date"] = pd.to_datetime(usable["search_date"], errors="coerce")
    daily_fares = (
        usable.dropna(subset=["search_date"])
        .groupby(["route", "search_date"], as_index=False)
        .agg(avg_total_fare=("total_fare", "mean"))
        .sort_values(["route", "search_date"])
    )
    daily_fares["fare_change_pct"] = daily_fares.groupby("route")["avg_total_fare"].pct_change() * 100

    latest_swings = daily_fares.dropna(subset=["fare_change_pct"]).groupby("route").tail(1).copy()
    if latest_swings.empty:
        return pd.DataFrame()

    latest_swings["swing_pct"] = latest_swings["fare_change_pct"].abs()
    latest_swings = latest_swings.rename(
        columns={
            "search_date": "latest_date",
            "avg_total_fare": "latest_avg_fare",
        }
    )
    latest_swings["previous_date"] = daily_fares.groupby("route")["search_date"].shift(1)

    latest_index = (
        route_index.assign(index_date=pd.to_datetime(route_index["index_date"], errors="coerce"))
        .sort_values("index_date")
        .groupby("route")
        .tail(1)[["route", "index_date", "index_value"]]
        .rename(columns={"index_date": "latest_index_date", "index_value": "latest_index_value"})
    )
    ranked = latest_swings.merge(latest_index, on="route", how="left")
    ranked = ranked.sort_values("swing_pct", ascending=False).reset_index(drop=True)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


st.set_page_config(page_title="APIx Insights", page_icon="💡", layout="wide")
st.markdown(
    """
    <style>
    .block-container { max-width: 1400px; padding-top: 2rem; padding-bottom: 3rem; }
    div[data-testid="stAppViewContainer"] { font-family: "Segoe UI", Arial, sans-serif; }
    h1, h2, h3 { letter-spacing: -0.02em; }
    div[data-testid="stAlert"] { border-radius: 0.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("4. Insights")
st.caption("These observations are calculated live from the cleaned quotes and route index stored in SQLite.")

with st.spinner("Loading insight data..."):
    try:
        quotes, route_index = load_insight_data()
    except (sqlite3.Error, pd.errors.DatabaseError):
        st.warning("The insight data is temporarily unavailable. Please try again later.")
        st.stop()

if quotes.empty:
    st.info("No clean quote data is available yet.")
    st.stop()

st.header("Best booking window by route")
summary = fare_summary(quotes)
if summary.empty:
    st.info("No non-outlier fares are available for comparison yet.")
else:
    for route in sorted(summary["route"].unique()):
        route_summary = summary[summary["route"].eq(route)].copy()
        st.write(recommendation(route, route_summary))

    display_summary = summary.copy()
    display_summary["advance_window"] = display_summary["advance_window"].map(
        lambda window: f"{window} ({WINDOW_LABELS.get(window, window)})"
    )
    display_summary = display_summary.rename(
        columns={"route": "Route", "advance_window": "Window", "avg_total_fare": "Average total fare (INR)", "quote_count": "Quotes used"}
    )
    st.dataframe(
        display_summary[["Route", "Window", "Average total fare (INR)", "Quotes used"]],
        use_container_width=True,
        hide_index=True,
    )

st.header("Which route is more volatile?")
ranking = volatility_ranking(quotes, route_index)
if ranking.empty:
    st.info("At least two scrape dates per route are needed to rank day-to-day fare volatility.")
else:
    leader = ranking.iloc[0]
    st.subheader(
        f"{leader['route']} is currently the more volatile route "
        f"({leader['swing_pct']:.1f}% day-to-day swing)."
    )
    ranking_display = ranking.copy()
    ranking_display["latest_date"] = ranking_display["latest_date"].dt.strftime("%Y-%m-%d")
    ranking_display["previous_date"] = ranking_display["previous_date"].dt.strftime("%Y-%m-%d")
    ranking_display = ranking_display.rename(
        columns={
            "rank": "Rank",
            "route": "Route",
            "previous_date": "Previous date",
            "latest_date": "Latest date",
            "latest_avg_fare": "Latest average fare (INR)",
            "fare_change_pct": "Signed change (%)",
            "swing_pct": "Absolute swing (%)",
            "latest_index_value": "Latest route index",
        }
    )
    st.dataframe(
        ranking_display[
            [
                "Rank",
                "Route",
                "Previous date",
                "Latest date",
                "Latest average fare (INR)",
                "Signed change (%)",
                "Absolute swing (%)",
                "Latest route index",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
