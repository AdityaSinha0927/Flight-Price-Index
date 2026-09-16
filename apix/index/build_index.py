"""Build the APIx daily fixed-basket index from ``clean_quotes``."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "apix.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
ROUTES = ("DEL-BOM", "DEL-BLR")
WINDOWS = ("T1", "T7", "T30")
ROUTE_WEIGHTS = {"DEL-BOM": 0.5, "DEL-BLR": 0.5}


def _connection(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='clean_quotes'").fetchone():
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _read_clean_quotes(connection: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT route, advance_window, search_date, total_fare
        FROM clean_quotes
        WHERE is_outlier = 0
          AND total_fare IS NOT NULL
          AND total_fare > 0
        """,
        connection,
    )


def _daily_window_averages(quotes: pd.DataFrame) -> pd.DataFrame:
    if quotes.empty:
        return pd.DataFrame(columns=["route", "advance_window", "index_date", "avg_total_fare", "num_quotes"])
    quotes = quotes.copy()
    quotes["index_date"] = pd.to_datetime(quotes["search_date"], errors="raise").dt.date.astype(str)
    return (
        quotes.groupby(["route", "advance_window", "index_date"], as_index=False)
        .agg(avg_total_fare=("total_fare", "mean"), num_quotes=("total_fare", "count"))
    )


def _base_period(averages: pd.DataFrame) -> str:
    if averages.empty:
        raise ValueError("Cannot build an index: clean_quotes contains no non-outlier fares")
    return str(averages["index_date"].min())


def _build_route_values(averages: pd.DataFrame, base_period: str) -> pd.DataFrame:
    base = averages[averages["index_date"] == base_period].set_index(["route", "advance_window"])["avg_total_fare"]
    missing_base = [(route, window) for route in ROUTES for window in WINDOWS if (route, window) not in base.index]
    if missing_base:
        raise ValueError(f"Base period {base_period} is missing route/window fares: {missing_base}")

    rows: list[dict] = []
    for index_date in sorted(averages["index_date"].unique()):
        current = averages[averages["index_date"] == index_date]
        for route in ROUTES:
            route_rows = current[current["route"] == route].set_index("advance_window")
            if not all(window in route_rows.index for window in WINDOWS):
                continue
            relatives = [
                float(route_rows.loc[window, "avg_total_fare"] / base.loc[(route, window)])
                for window in WINDOWS
            ]
            rows.append(
                {
                    "index_date": index_date,
                    "route": route,
                    "route_relative": float(np.mean(relatives)),
                    "num_quotes_used": int(route_rows["num_quotes"].sum()),
                }
            )
    return pd.DataFrame(rows, columns=["index_date", "route", "route_relative", "num_quotes_used"])


def _build_output(route_values: pd.DataFrame, base_period: str) -> pd.DataFrame:
    if route_values.empty:
        return pd.DataFrame(columns=["index_date", "route", "index_value", "base_period", "num_quotes_used"])
    rows: list[dict] = []
    for row in route_values.itertuples(index=False):
        rows.append(
            {
                "index_date": row.index_date,
                "route": row.route,
                "index_value": float(row.route_relative * 100),
                "base_period": base_period,
                "num_quotes_used": int(row.num_quotes_used),
            }
        )

    complete_dates = (
        route_values.groupby("index_date")["route"]
        .agg(lambda values: set(values) == set(ROUTES))
    )
    for index_date in complete_dates[complete_dates].index:
        current = route_values[route_values["index_date"] == index_date].set_index("route")
        relative = float(np.prod([current.loc[route, "route_relative"] ** ROUTE_WEIGHTS[route] for route in ROUTES]))
        rows.append(
            {
                "index_date": index_date,
                "route": "ALL",
                "index_value": relative * 100,
                "base_period": base_period,
                "num_quotes_used": int(current["num_quotes_used"].sum()),
            }
        )
    return pd.DataFrame(rows)


def aggregate_weekly(index_rows: pd.DataFrame) -> pd.DataFrame:
    """Return simple calendar-week averages for display."""
    if index_rows.empty:
        return pd.DataFrame(columns=["week", "route", "index_value"])
    rows = index_rows.copy()
    rows["index_date"] = pd.to_datetime(rows["index_date"], errors="raise")
    rows["week"] = rows["index_date"].dt.to_period("W").dt.start_time.dt.date.astype(str)
    return rows.groupby(["week", "route"], as_index=False)["index_value"].mean()


def aggregate_monthly(index_rows: pd.DataFrame) -> pd.DataFrame:
    """Return simple calendar-month averages for display."""
    if index_rows.empty:
        return pd.DataFrame(columns=["month", "route", "index_value"])
    rows = index_rows.copy()
    rows["index_date"] = pd.to_datetime(rows["index_date"], errors="raise")
    rows["month"] = rows["index_date"].dt.to_period("M").astype(str)
    return rows.groupby(["month", "route"], as_index=False)["index_value"].mean()


def build_index(db_path: str | Path = DB_PATH) -> dict[str, int | str | None]:
    """Build and upsert daily route and overall index rows."""
    connection = _connection(db_path)
    try:
        averages = _daily_window_averages(_read_clean_quotes(connection))
        if averages.empty:
            # Never keep an old index visible after the cleaning pipeline has
            # rejected every current quote.
            with connection:
                connection.execute("DELETE FROM index_values")
            return {"base_period": None, "rows_written": 0}
        base_period = _base_period(averages)
        output = _build_output(_build_route_values(averages, base_period), base_period)
        with connection:
            for row in output.to_dict("records"):
                connection.execute(
                    """
                    INSERT INTO index_values
                        (index_date, route, index_value, base_period, num_quotes_used)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(index_date, route) DO UPDATE SET
                        index_value = excluded.index_value,
                        base_period = excluded.base_period,
                        num_quotes_used = excluded.num_quotes_used
                    """,
                    (row["index_date"], row["route"], row["index_value"], row["base_period"], row["num_quotes_used"]),
                )
        return {"base_period": base_period, "rows_written": int(len(output))}
    finally:
        connection.close()


def run_index(db_path: str | Path = DB_PATH) -> dict[str, int | str | None]:
    """Compatibility entry point for scheduled index execution."""
    return build_index(db_path)


if __name__ == "__main__":
    print(build_index())
