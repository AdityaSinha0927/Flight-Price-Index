"""Read-only view of cleaned quote records for dashboard transparency."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st


DB_PATH = Path(__file__).resolve().parents[2] / "db" / "apix.db"
EMPTY_COLUMNS = [
    "source",
    "route",
    "carrier",
    "search_date",
    "travel_date",
    "advance_window",
    "fare_class",
    "base_fare",
    "taxes_and_fees",
    "total_fare",
    "flight_number",
    "departure_time",
    "scraped_at",
    "is_outlier",
    "cleaning_notes",
]


@st.cache_data(ttl=60, show_spinner=False)
def load_clean_quotes() -> pd.DataFrame:
    """Load clean quote rows without changing the database."""
    if not DB_PATH.exists():
        return pd.DataFrame(columns=EMPTY_COLUMNS)

    query = """
        SELECT
            source,
            route,
            carrier,
            search_date,
            travel_date,
            advance_window,
            fare_class,
            base_fare,
            taxes_and_fees,
            total_fare,
            flight_number,
            departure_time,
            scraped_at,
            is_outlier,
            cleaning_notes
        FROM clean_quotes
        ORDER BY travel_date DESC, route, advance_window, source
    """
    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(query, connection)


def apply_filters(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the viewer's selections to the clean quote data."""
    st.sidebar.header("Filters")

    route_options = sorted(frame["route"].dropna().unique().tolist())
    selected_routes = st.sidebar.multiselect("Route", route_options, default=route_options)

    source_options = sorted(frame["source"].dropna().unique().tolist())
    selected_sources = st.sidebar.multiselect("Source", source_options, default=source_options)

    window_order = ["T1", "T7", "T30"]
    window_options = [window for window in window_order if window in set(frame["advance_window"].dropna())]
    selected_windows = st.sidebar.multiselect(
        "Advance window",
        window_options,
        default=window_options,
    )

    frame["travel_date"] = pd.to_datetime(frame["travel_date"], errors="coerce").dt.date
    available_dates = frame["travel_date"].dropna()
    if available_dates.empty:
        return frame.iloc[0:0]

    min_date = min(available_dates)
    max_date = max(available_dates)
    selected_range = st.sidebar.date_input(
        "Travel date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(selected_range, (tuple, list)):
        start_date, end_date = selected_range[0], selected_range[-1]
    else:
        start_date = end_date = selected_range

    filtered = frame[
        frame["route"].isin(selected_routes)
        & frame["source"].isin(selected_sources)
        & frame["advance_window"].isin(selected_windows)
        & frame["travel_date"].between(start_date, end_date)
    ].copy()
    return filtered.sort_values(
        ["travel_date", "route", "advance_window", "source"],
        ascending=[False, True, True, True],
    )


st.set_page_config(page_title="APIx Raw Data", page_icon="🧾", layout="wide")
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
st.title("3. Raw clean quote data")
st.caption("Read-only view of the fares collected and the cleaning decisions recorded for each quote.")

with st.spinner("Loading cleaned quote data..."):
    try:
        quotes = load_clean_quotes()
    except (sqlite3.Error, pd.errors.DatabaseError):
        st.warning("The clean quote data is temporarily unavailable. Please try again later.")
        st.stop()

if quotes.empty:
    st.info("No cleaned quotes are available yet.")
    st.stop()

filtered_quotes = apply_filters(quotes)
st.write(f"Showing {len(filtered_quotes):,} of {len(quotes):,} clean quote rows.")
if filtered_quotes.empty:
    st.info("No clean quote rows match the selected filters.")
    st.stop()

visible_columns = [
    "source",
    "route",
    "carrier",
    "search_date",
    "travel_date",
    "advance_window",
    "fare_class",
    "base_fare",
    "taxes_and_fees",
    "total_fare",
    "flight_number",
    "departure_time",
    "is_outlier",
    "cleaning_notes",
    "scraped_at",
]
st.dataframe(filtered_quotes[visible_columns], use_container_width=True, hide_index=True)
