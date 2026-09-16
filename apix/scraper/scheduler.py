"""Run all APIx scrapers once or on a daily local-time schedule."""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Callable

try:
    from scraper.indigo_scraper import run_daily as run_indigo
    from scraper.ixigo_scraper import run_daily as run_ixigo
    from scraper.scraper_utils import DB_PATH, ROUTES, WINDOWS, log_error, open_database
except ModuleNotFoundError:  # Supports ``python -m apix.scraper.scheduler``.
    from apix.scraper.indigo_scraper import run_daily as run_indigo
    from apix.scraper.ixigo_scraper import run_daily as run_ixigo
    from apix.scraper.scraper_utils import DB_PATH, ROUTES, WINDOWS, log_error, open_database


SOURCES: tuple[tuple[str, Callable], ...] = (
    ("indigo", run_indigo),
    ("ixigo", run_ixigo),
)
EXPECTED_ROWS_PER_SOURCE = len(ROUTES) * len(WINDOWS)
EXPECTED_ROWS = len(SOURCES) * EXPECTED_ROWS_PER_SOURCE


def _daily_counts(db_path: str | Path, run_date: date) -> tuple[int, dict[str, int], dict[str, int]]:
    connection = open_database(db_path)
    try:
        rows = connection.execute(
            """
            SELECT source, scrape_status, COUNT(*)
            FROM raw_quotes
            WHERE search_date = ?
            GROUP BY source, scrape_status
            """,
            (run_date.isoformat(),),
        ).fetchall()
    finally:
        connection.close()

    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for source, status, count in rows:
        by_source[source] = by_source.get(source, 0) + count
        by_status[status] = by_status.get(status, 0) + count
    return sum(by_source.values()), by_source, by_status


def run_once(
    run_date: date | None = None,
    db_path: str | Path = DB_PATH,
    process_results: bool = True,
) -> dict:
    """Run both sources and return an auditable per-day collection summary."""
    run_date = run_date or date.today()
    before, _, _ = _daily_counts(db_path, run_date)
    source_errors: dict[str, str] = {}

    for source, source_runner in SOURCES:
        try:
            source_runner(run_date=run_date, db_path=db_path)
        except Exception as exc:  # One broken source must not prevent the other.
            source_errors[source] = str(exc)
            log_error(source, f"daily run failed for {run_date.isoformat()}: {exc}")

    stored, by_source, by_status = _daily_counts(db_path, run_date)
    summary: dict = {
        "date": run_date.isoformat(),
        "expected_rows": EXPECTED_ROWS,
        "stored_rows": stored,
        "new_rows": stored - before,
        "complete": stored == EXPECTED_ROWS,
        "by_source": by_source,
        "missing_by_source": {
            source: max(0, EXPECTED_ROWS_PER_SOURCE - by_source.get(source, 0))
            for source, _ in SOURCES
        },
        "by_status": by_status,
        "source_errors": source_errors,
    }

    if process_results and stored:
        try:
            from pipeline.clean import run_cleaning
            from index.build_index import run_index
        except ModuleNotFoundError:
            from apix.pipeline.clean import run_cleaning
            from apix.index.build_index import run_index

        summary["cleaning"] = run_cleaning(db_path)
        try:
            summary["index"] = run_index(db_path)
        except ValueError as exc:
            # Partial/non-price runs remain useful audit data, even before an
            # index can be calculated from a complete successful basket.
            summary["index_error"] = str(exc)
    return summary


def _parse_time(value: str) -> clock_time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("time must use 24-hour HH:MM format") from exc


def _next_run(now: datetime, run_at: clock_time) -> datetime:
    candidate = datetime.combine(now.date(), run_at)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def run_forever(run_at: clock_time, db_path: str | Path = DB_PATH) -> None:
    """Run immediately, then once per local calendar day at ``run_at``."""
    print(json.dumps(run_once(db_path=db_path), indent=2), flush=True)
    while True:
        next_run = _next_run(datetime.now(), run_at)
        print(f"Next scrape: {next_run.isoformat(timespec='minutes')}", flush=True)
        while True:
            remaining = (next_run - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(remaining, 60))
        print(json.dumps(run_once(db_path=db_path), indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="stay running and scrape once per day")
    parser.add_argument("--at", type=_parse_time, default=clock_time(6, 0), metavar="HH:MM", help="daily local time in loop mode (default: 06:00)")
    parser.add_argument("--date", type=date.fromisoformat, help="search date for a one-off run (YYYY-MM-DD)")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database path")
    parser.add_argument("--no-process", action="store_true", help="skip cleaning and index rebuild")
    args = parser.parse_args()

    if args.loop:
        if args.date or args.no_process:
            parser.error("--date and --no-process are only valid for a one-off run")
        try:
            run_forever(args.at, args.db)
        except KeyboardInterrupt:
            print("Scheduler stopped.")
    else:
        print(json.dumps(run_once(args.date, args.db, not args.no_process), indent=2))


if __name__ == "__main__":
    main()
