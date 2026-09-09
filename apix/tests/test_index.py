"""Unit tests for the fixed-basket index methodology."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from index.build_index import aggregate_monthly, aggregate_weekly, build_index


SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


@pytest.fixture
def index_db(tmp_path: Path) -> Path:
    path = tmp_path / "apix.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    return path


def add_clean_quote(path: Path, route: str, window: str, search_date: str, fare: float):
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO raw_quotes
                (source, route, carrier, search_date, travel_date, advance_window,
                 fare_class, base_fare, taxes_and_fees, total_fare, flight_number,
                 departure_time, scrape_status, scraped_at)
            VALUES ('indigo', ?, 'IndiGo', ?, ?, ?, 'economy', ?, 0, ?, '6E123', '08:00', 'ok', ?)
            """,
            (route, search_date, search_date, window, fare, fare, f"{search_date}T10:00:00+00:00"),
        )
        connection.execute(
            """
            INSERT INTO clean_quotes
                (raw_quote_id, source, route, carrier, search_date, travel_date,
                 advance_window, fare_class, base_fare, taxes_and_fees, total_fare,
                 flight_number, departure_time, scraped_at, is_outlier, cleaning_notes)
            VALUES (?, 'indigo', ?, 'IndiGo', ?, ?, ?, 'economy', ?, 0, ?, '6E123', '08:00', ?, 0, NULL)
            """,
            (cursor.lastrowid, route, search_date, search_date, window, fare, fare, f"{search_date}T10:00:00+00:00"),
        )


def index_rows(path: Path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT index_date, route, index_value, base_period, num_quotes_used FROM index_values ORDER BY index_date, route"
        ).fetchall()


def seed_two_day_basket(path: Path):
    base = {"DEL-BOM": (100.0, 100.0, 100.0), "DEL-BLR": (200.0, 200.0, 200.0)}
    day_two = {"DEL-BOM": (120.0, 130.0, 110.0), "DEL-BLR": (220.0, 200.0, 240.0)}
    for route in ("DEL-BOM", "DEL-BLR"):
        for window, fare in zip(("T1", "T7", "T30"), base[route]):
            add_clean_quote(path, route, window, "2024-01-01", fare)
        for window, fare in zip(("T1", "T7", "T30"), day_two[route]):
            add_clean_quote(path, route, window, "2024-01-02", fare)


def test_day_two_matches_manual_price_relative_calculation(index_db: Path):
    seed_two_day_basket(index_db)

    build_index(index_db)
    rows = {(row[0], row[1]): row[2] for row in index_rows(index_db)}

    # DEL-BOM: mean(1.2, 1.3, 1.1) = 1.2; DEL-BLR: mean(1.1, 1.0, 1.2) = 1.1.
    assert rows[("2024-01-02", "DEL-BOM")] == pytest.approx(120.0)
    assert rows[("2024-01-02", "DEL-BLR")] == pytest.approx(110.0)
    assert rows[("2024-01-02", "ALL")] == pytest.approx((1.2 * 1.1) ** 0.5 * 100)


def test_base_period_is_100_for_routes_and_all(index_db: Path):
    seed_two_day_basket(index_db)

    build_index(index_db)
    base_rows = [row for row in index_rows(index_db) if row[0] == "2024-01-01"]

    assert {(row[1], row[2]) for row in base_rows} == {
        ("DEL-BOM", 100.0), ("DEL-BLR", 100.0), ("ALL", 100.0)
    }


def test_weekly_and_monthly_aggregations_are_simple_averages():
    daily = pd.DataFrame(
        {
            "index_date": ["2024-01-01", "2024-01-02", "2024-02-01"],
            "route": ["ALL", "ALL", "ALL"],
            "index_value": [100.0, 120.0, 140.0],
        }
    )

    weekly = aggregate_weekly(daily)
    monthly = aggregate_monthly(daily)

    assert weekly.loc[weekly["week"] == "2024-01-01", "index_value"].iloc[0] == pytest.approx(110.0)
    assert monthly.set_index("month").loc["2024-01", "index_value"] == pytest.approx(110.0)
    assert monthly.set_index("month").loc["2024-02", "index_value"] == pytest.approx(140.0)
