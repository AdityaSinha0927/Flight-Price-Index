"""Tests for daily scrape dates and the combined scheduler."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from pathlib import Path

from scraper import scheduler
from scraper.scraper_utils import (
    WINDOWS,
    build_quote,
    insert_quote,
    is_already_scraped,
    open_database,
    travel_date_for,
)


def test_explicit_search_date_is_stored_and_used_for_deduplication(tmp_path: Path):
    db_path = tmp_path / "apix.db"
    search_date = date(2026, 9, 11)
    travel_date = travel_date_for("T7", search_date)
    quote = build_quote(
        "indigo", "DEL-BOM", travel_date, "T7", "ok", search_date=search_date
    )

    connection = open_database(db_path)
    try:
        assert insert_quote(connection, quote)
        assert is_already_scraped(
            connection, "indigo", "DEL-BOM", travel_date, "T7", search_date
        )
        assert not is_already_scraped(
            connection, "indigo", "DEL-BOM", travel_date, "T7", date(2026, 9, 12)
        )
    finally:
        connection.close()

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT search_date, travel_date FROM raw_quotes"
        ).fetchone() == ("2026-09-11", "2026-09-18")


def test_combined_runner_collects_twelve_rows_and_is_idempotent(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "apix.db"
    run_date = date(2026, 9, 11)

    def fake_runner(source: str):
        def run_daily(*, run_date: date, db_path: Path):
            connection = open_database(db_path)
            try:
                for route in ("DEL-BOM", "DEL-BLR"):
                    for window in WINDOWS:
                        travel_date = travel_date_for(window, run_date)
                        quote = build_quote(
                            source,
                            route,
                            travel_date,
                            window,
                            "ok",
                            search_date=run_date,
                            total_fare=100.0,
                        )
                        insert_quote(connection, quote)
            finally:
                connection.close()

        return run_daily

    monkeypatch.setattr(
        scheduler,
        "SOURCES",
        (("indigo", fake_runner("indigo")), ("ixigo", fake_runner("ixigo"))),
    )

    first = scheduler.run_once(run_date, db_path, process_results=False)
    second = scheduler.run_once(run_date, db_path, process_results=False)

    assert first["stored_rows"] == 12
    assert first["new_rows"] == 12
    assert first["complete"] is True
    assert first["by_source"] == {"indigo": 6, "ixigo": 6}
    assert first["missing_by_source"] == {"indigo": 0, "ixigo": 0}
    assert second["stored_rows"] == 12
    assert second["new_rows"] == 0


def test_next_run_uses_the_next_local_occurrence():
    run_at = time(6, 0)

    assert scheduler._next_run(datetime(2026, 9, 11, 5, 0), run_at) == datetime(
        2026, 9, 11, 6, 0
    )
    assert scheduler._next_run(datetime(2026, 9, 11, 7, 0), run_at) == datetime(
        2026, 9, 12, 6, 0
    )
