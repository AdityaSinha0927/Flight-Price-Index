"""Single-page Streamlit dashboard for the APIx prototype."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

# Port 8000 may be in use by another local service. APIx runs on 8001 in this
# workspace; deployments may still override this through APIX_API_URL.
API_BASE_URL = os.getenv("APIX_API_URL", "http://127.0.0.1:8001/api/v1").rstrip("/")
ROUTES = ("ALL", "DEL-BOM", "DEL-BLR")
ROUTE_LABELS = {"ALL": "Overall", "DEL-BOM": "DEL-BOM", "DEL-BLR": "DEL-BLR"}
WINDOWS = ("T1", "T7", "T30")

CPI_PATH = os.getenv("APIX_MOSPI_CPI_PATH")
PRIMARY_COLOR = "#2563EB"
SECONDARY_COLOR = "#F97316"
POSITIVE_COLOR = "#16A34A"
TEXT_COLOR = "#1F2937"


def apply_page_style() -> None:
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


def style_figure(figure):
    figure.update_layout(
        template="plotly_white",
        font={"family": "Arial, sans-serif", "color": TEXT_COLOR},
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    figure.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    figure.update_yaxes(showgrid=True, gridcolor="#E5E7EB")
    return figure


def _mospi_path() -> Path | None:
    candidates = [Path(CPI_PATH)] if CPI_PATH else []
    candidates.extend(
        [
            Path(__file__).resolve().parents[1] / "cpi_1059.xlsx",
            Path(__file__).resolve().parents[2] / "cpi_1059.xlsx",
            Path(__file__).resolve().parents[3] / "cpi_1059.xlsx",
        ]
    )
    return next((path for path in candidates if path.exists()), None)


@st.cache_data(show_spinner=False)
def load_mospi_airfare_cpi() -> pd.DataFrame:
    """Load the official MoSPI domestic-airfare CPI slice for the back-test."""
    path = _mospi_path()
    if path is None:
        return pd.DataFrame(columns=["date", "mospi_index"])
    source = pd.read_excel(path, sheet_name="CPI Data")
    filtered = source[
        (source["state"] == "All India")
        & (source["sector"] == "Combined")
        & (source["item"] == "Airfare")
        & (source["code"].astype(str) == "07.3.3.1.2.01")
    ].copy()
    filtered["month_number"] = pd.to_datetime(filtered["month"].astype(str), format="%B").dt.month
    filtered["date"] = pd.to_datetime(
        {"year": filtered["year"].astype(int), "month": filtered["month_number"], "day": 1}
    )
    filtered = filtered[
        (filtered["date"] >= "2025-01-01") & (filtered["date"] <= "2026-07-01")
    ]
    return (
        filtered[["date", "index"]]
        .rename(columns={"index": "mospi_index"})
        .assign(mospi_index=lambda frame: pd.to_numeric(frame["mospi_index"], errors="coerce"))
        .dropna(subset=["date", "mospi_index"])
        .sort_values("date")
        .drop_duplicates("date")
    )


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_json(endpoint: str, params: tuple[tuple[str, str], ...] = ()) -> dict:
    """Fetch an API response, allowing FastAPI a brief startup window."""
    query = urlencode(params)
    url = f"{API_BASE_URL}/{endpoint.lstrip('/')}" + (f"?{query}" if query else "")
    request = Request(url, headers={"Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urlopen(request, timeout=3) as response:
                if response.status >= 400:
                    raise RuntimeError(f"API returned HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt < 4:
                time.sleep(0.5)
    raise RuntimeError(f"FastAPI at {API_BASE_URL} did not respond after 5 attempts.") from last_error


def api_data(endpoint: str, **params):
    """Return live API data, falling back to the last successful response."""
    clean_params = tuple(sorted((key, str(value)) for key, value in params.items() if value is not None))
    cache_key = (endpoint, clean_params)
    try:
        payload = _fetch_json(endpoint, clean_params)
        st.session_state.setdefault("api_cache", {})[cache_key] = {
            "payload": payload,
            "fetched_at": datetime.now(timezone.utc),
        }
        return payload, True, None
    except Exception as exc:
        fallback = st.session_state.get("api_cache", {}).get(cache_key)
        if fallback:
            return fallback["payload"], False, fallback["fetched_at"]
        return {}, False, None


def show_api_status(live: bool, fallback_time=None) -> None:
    if live:
        st.caption("Data source: FastAPI Â· live response")
    elif fallback_time:
        st.warning(f"FastAPI unavailable; showing last successful response from {fallback_time.isoformat()}")
    else:
        st.warning("FastAPI unavailable and no cached response is available yet.")


def render_price_alerts() -> None:
    """Show each route's latest index relative to its seven-day average."""
    st.subheader("Price alert")
    columns = st.columns(len(ROUTES) - 1)
    for column, route in zip(columns, ROUTES[1:]):
        with st.spinner(f"Loading {route} alert..."):
            payload, live, fallback = api_data("index", route=route, freq="daily")
        values = payload.get("data", [])
        with column:
            if not values:
                st.info(f"{route}: no index data available")
                continue
            if len(values) < 2:
                st.caption(f"{route}: not enough history for a trend alert")
                continue

            recent_values = pd.Series([float(item["index_value"]) for item in values[-7:]])
            current = float(recent_values.iloc[-1])
            rolling_average = float(recent_values.mean())
            change_pct = ((current - rolling_average) / rolling_average * 100) if rolling_average else 0.0
            if change_pct > 0.1:
                indicator, label, color = "↑", "Fares trending up", "#d62728"
            elif change_pct < -0.1:
                indicator, label, color = "↓", "Fares trending down", "#2ca02c"
            else:
                indicator, label, color = "→", "Fares are flat", "#6b7280"

            window_note = "" if len(values) >= 7 else f" ({len(recent_values)} days available)"
            st.markdown(
                f"""
                <div style="border-left: 4px solid {color}; padding: 0.35rem 0.65rem;">
                    <div style="color: {color}; font-weight: 700;">{indicator} {route} — {label}</div>
                    <div>Current index: <b>{current:.1f}</b> · 7-day average{window_note}: {rolling_average:.1f} ({change_pct:+.1f}%)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not live and fallback:
                st.caption(f"Using cached route data from {fallback.isoformat()}")


def latest_value(payload: dict) -> tuple[float | None, str | None]:
    values = payload.get("data", [])
    if not values:
        return None, None
    latest = values[-1]
    return float(latest["index_value"]), latest["date"]


def render_header() -> None:
    st.title("APIx â€” Real-time Airfare Price Index")
    with st.spinner("Loading current index..."):
        health, health_live, health_fallback = api_data("health")
        index, index_live, index_fallback = api_data("index", route="ALL", freq="daily")
    current, current_date = latest_value(index)
    values = index.get("data", [])
    previous = float(values[-2]["index_value"]) if len(values) > 1 else None
    change = ((current - previous) / previous * 100) if current is not None and previous else None
    last_updated = health.get("last_scrape_at") or current_date or "not yet available"
    if current is None:
        st.subheader("Current overall index: unavailable")
    else:
        change_text = f" Â· {change:+.2f}% vs previous day" if change is not None else ""
        st.subheader(f"Current overall index: {current:.1f} Â· {last_updated}{change_text}")
    show_api_status(index_live and health_live, index_fallback or health_fallback)
    render_price_alerts()


def render_index_trend() -> None:
    st.header("2. Index trend")
    route = st.selectbox("Index route", ROUTES, format_func=lambda value: ROUTE_LABELS[value], key="trend_route")
    frequency = st.selectbox("Frequency", ("daily", "weekly", "monthly"), key="trend_frequency")
    with st.spinner("Loading index trend..."):
        payload, live, fallback = api_data("index", route=route, freq=frequency)
    frame = pd.DataFrame(payload.get("data", []))
    if frame.empty:
        show_api_status(live, fallback)
        st.info("No index values are available for this selection.")
        return
    frame["date"] = pd.to_datetime(frame["date"])
    figure = px.line(frame, x="date", y="index_value", markers=True, title=f"{ROUTE_LABELS[route]} index ({frequency})")
    figure.update_yaxes(title="Index value", rangemode="tozero")
    figure.update_traces(line={"color": PRIMARY_COLOR}, marker={"color": PRIMARY_COLOR})
    style_figure(figure)
    st.plotly_chart(figure, use_container_width=True)
    show_api_status(live, fallback)


def render_sector_comparison() -> None:
    st.header("3. Sector-wise comparison")
    values = []
    statuses = []
    for route in ROUTES[1:]:
        with st.spinner("Loading route comparison..."):
            payload, live, fallback = api_data("index", route=route, freq="daily")
        current, current_date = latest_value(payload)
        if current is not None:
            values.append({"route": route, "index_value": current, "date": current_date})
        statuses.append((live, fallback))
    frame = pd.DataFrame(values)
    if frame.empty:
        st.info("No route-level index values are available yet.")
        return
    figure = px.bar(
        frame,
        x="route",
        y="index_value",
        text_auto=".1f",
        color="route",
        color_discrete_map={"DEL-BOM": PRIMARY_COLOR, "DEL-BLR": SECONDARY_COLOR},
        title="Latest route index values",
    )
    figure.update_yaxes(title="Index value")
    style_figure(figure)
    st.plotly_chart(figure, use_container_width=True)
    st.caption(f"Latest available date: {frame['date'].max()}")
    for live, fallback in statuses:
        if not live and fallback:
            st.caption(f"Using cached route data from {fallback.isoformat()}")


def render_elasticity() -> None:
    st.header("4. Lead-time elasticity")
    route = st.selectbox("Elasticity route", ROUTES[1:], key="elasticity_route")
    with st.spinner("Loading elasticity data..."):
        payload, live, fallback = api_data("elasticity", route=route)
    frame = pd.DataFrame(payload.get("data", []))
    if frame.empty:
        show_api_status(live, fallback)
        st.info("No fare observations are available for this route yet.")
        return
    frame["advance_window"] = pd.Categorical(frame["advance_window"], categories=WINDOWS, ordered=True)
    frame = frame.sort_values("advance_window")
    figure = px.bar(frame, x="advance_window", y="avg_total_fare", text_auto=".0f", title=f"Average fare by booking window â€” {route}")
    figure.update_xaxes(title="Advance-purchase window")
    figure.update_yaxes(title="Average total fare (INR)")
    figure.update_traces(marker_color=PRIMARY_COLOR)
    style_figure(figure)
    st.plotly_chart(figure, use_container_width=True)
    show_api_status(live, fallback)


def render_backtest() -> None:
    st.header("5. Back-test comparison")
    with st.spinner("Loading back-test data..."):
        api_payload, api_live, api_fallback = api_data("index", route="ALL", freq="monthly")
        apix = pd.DataFrame(api_payload.get("data", []))
        mospi = load_mospi_airfare_cpi()
    if mospi.empty:
        st.warning("MoSPI CPI airfare data is unavailable. Set APIX_MOSPI_CPI_PATH to cpi_1059.xlsx.")
        show_api_status(api_live, api_fallback)
        return
    if apix.empty or not {"date", "index_value"}.issubset(apix.columns):
        show_api_status(api_live, api_fallback)
        st.info("APIx monthly index data is not available yet for the back-test.")
        return

    apix["date"] = pd.to_datetime(apix["date"]).dt.to_period("M").dt.to_timestamp()
    mospi["date"] = pd.to_datetime(mospi["date"]).dt.to_period("M").dt.to_timestamp()
    api_series = apix[["date", "index_value"]].rename(columns={"index_value": "apix_raw"})
    mospi_series = mospi[["date", "mospi_index"]].rename(columns={"mospi_index": "mospi_raw"})
    comparison = pd.merge(api_series, mospi_series, on="date", how="outer").sort_values("date")

    overlapping = pd.merge(api_series, mospi_series, on="date", how="inner").sort_values("date")
    if overlapping.empty:
        first_apix = api_series["apix_raw"].iloc[0] if not api_series.empty else None
        first_mospi = mospi_series["mospi_raw"].iloc[0]
        comparison_note = (
            "Official CPI data lags ~2 months behind real-time pricing â€” "
            "this gap is what APIx is designed to close."
            if first_apix is not None
            else "APIx monthly index data is not available yet."
        )
    else:
        first_apix = overlapping["apix_raw"].iloc[0]
        first_mospi = overlapping["mospi_raw"].iloc[0]
        comparison_note = "Both series are rebased at the first overlapping month."

    if first_apix is not None:
        comparison["APIx monthly index (rebased)"] = comparison["apix_raw"] / first_apix * 100
    comparison["MoSPI airfare CPI (rebased)"] = comparison["mospi_raw"] / first_mospi * 100
    chart_columns = ["MoSPI airfare CPI (rebased)"]
    if "APIx monthly index (rebased)" in comparison:
        chart_columns.insert(0, "APIx monthly index (rebased)")
    figure = px.line(
        comparison,
        x="date",
        y=chart_columns,
        markers=True,
        title="Rebased APIx monthly index vs. MoSPI airfare CPI",
        color_discrete_map={
            "APIx monthly index (rebased)": PRIMARY_COLOR,
            "MoSPI airfare CPI (rebased)": SECONDARY_COLOR,
        },
    )
    figure.update_yaxes(title="Rebased value (base = 100)")
    style_figure(figure)
    if overlapping.empty and not api_series.empty:
        gap_start = mospi_series["date"].max() + pd.Timedelta(days=15)
        gap_end = api_series["date"].min() - pd.Timedelta(days=15)
        if gap_start < gap_end:
            figure.add_shape(
                type="rect",
                x0=gap_start,
                x1=gap_end,
                y0=0,
                y1=1,
                yref="paper",
                fillcolor="lightgray",
                opacity=0.35,
                line_width=0,
            )
            figure.add_annotation(
                x=gap_start + (gap_end - gap_start) / 2,
                y=1.02,
                yref="paper",
                text="Publication gap",
                showarrow=False,
            )
    st.plotly_chart(figure, use_container_width=True)
    st.caption(f"Timeline: {comparison['date'].min():%Y-%m} to {comparison['date'].max():%Y-%m}. {comparison_note} This is a rebased trend comparison, not an exact index match.")
    show_api_status(api_live, api_fallback)


def render_raw_table() -> None:
    st.header("6. Recent clean quotes")
    with st.expander("Show cleaned quote data", expanded=False):
        with st.spinner("Loading clean quote data..."):
            payload, live, fallback = api_data("quotes")
        frame = pd.DataFrame(payload.get("data", []))
        if frame.empty:
            show_api_status(live, fallback)
            st.info("No cleaned quotes are available yet.")
            return
        if "travel_date" in frame:
            frame = frame.sort_values("travel_date", ascending=False).head(100)
        st.dataframe(frame, use_container_width=True, hide_index=True)
        show_api_status(live, fallback)


def main() -> None:
    st.set_page_config(page_title="APIx Airfare Price Index", page_icon="âœˆï¸", layout="wide")
    apply_page_style()
    render_header()
    render_index_trend()
    render_sector_comparison()
    render_elasticity()
    render_backtest()
    render_raw_table()


if __name__ == "__main__":
    main()
