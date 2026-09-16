"""Unit tests for the five documented cleaning rules."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pipeline.clean import clean_database


SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


@pytest.fixture
def raw_db(tmp_path: Path) -> Path:
    """Create an isolated schema, allowing duplicate raw fixtures."""
    path = tmp_path / "apix.db"
    ddl = SCHEMA.read_text(encoding="utf-8").replace(
        "    scraped_at TEXT NOT NULL,\n    UNIQUE (source, route, travel_date, advance_window, search_date)\n",
        "    scraped_at TEXT NOT NULL\n",
    )
    with sqlite3.connect(path) as connection:
        connection.executescript(ddl)
    return path


def add_raw(path: Path, *, source="indigo", route="DEL-BOM", search_date="2024-01-01",
            travel_date="2024-01-02", window="T1", total=10000.0, base=None,
            taxes=None, scraped_at="2024-01-01T10:00:00+00:00") -> int:
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO raw_quotes
                (source, route, carrier, search_date, travel_date, advance_window,
                 fare_class, base_fare, taxes_and_fees, total_fare, flight_number,
                 departure_time, scrape_status, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', ?)
            """,
            (source, route, "IndiGo", search_date, travel_date, window, "economy",
             base, taxes, total, "6E123", "08:00", scraped_at),
        )
        return int(cursor.lastrowid)


def clean_rows(path: Path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT raw_quote_id, base_fare, taxes_and_fees, total_fare, is_outlier, cleaning_notes FROM clean_quotes ORDER BY id"
        ).fetchall()


def test_total_only_fare_is_decomposed(raw_db: Path):
    add_raw(raw_db, total=1180.0)

    clean_database(raw_db)
    row = clean_rows(raw_db)[0]

    assert row[1] == pytest.approx(1000.0)
    assert row[2] == pytest.approx(180.0)
    assert row[1] + row[2] == pytest.approx(row[3])
    assert row[5] == "tax split estimated"


def test_exact_duplicates_keep_only_latest_scrape(raw_db: Path):
    first_id = add_raw(raw_db, total=10000.0, scraped_at="2024-01-01T10:00:00+00:00")
    second_id = add_raw(raw_db, total=12500.0, scraped_at="2024-01-01T11:00:00+00:00")

    clean_database(raw_db)
    rows = clean_rows(raw_db)

    assert len(rows) == 1
    assert rows[0][0] == second_id
    assert rows[0][0] != first_id


def test_zero_total_is_dropped(raw_db: Path):
    add_raw(raw_db, total=0.0)

    clean_database(raw_db)

    assert clean_rows(raw_db) == []


def test_iqr_outlier_is_flagged_but_retained(raw_db: Path):
    for day, fare in enumerate((10000.0, 10000.0, 10000.0, 100000.0), start=1):
        day_text = f"2024-01-{day:02d}"
        add_raw(raw_db, search_date=day_text, travel_date=f"2024-01-{day + 1:02d}", total=fare)

    clean_database(raw_db)
    rows = clean_rows(raw_db)

    assert len(rows) == 4
    assert sum(row[4] for row in rows) == 1
    assert next(row for row in rows if row[3] == 100000.0)[4] == 1


def test_below_minimum_fare_is_discarded(raw_db: Path):
    add_raw(raw_db, total=220.0)

    clean_database(raw_db)

    assert clean_rows(raw_db) == []


def test_sanity_bound_violation_is_discarded(raw_db: Path):
    add_raw(raw_db, total=500000.0)

    clean_database(raw_db)

    assert clean_rows(raw_db) == []
