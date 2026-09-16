"""Seed a clearly labelled, realistic INR dataset for dashboard demonstrations.

This is only for an offline demo when authorized source collection has not
produced enough quotes to build an index. It never impersonates a live scrape:
the source, carrier, and fare class explicitly identify each row as demo data.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

try:
    from scraper.scraper_utils import DB_PATH, build_quote, insert_quote, open_database
except ModuleNotFoundError:
    from apix.scraper.scraper_utils import DB_PATH, build_quote, insert_quote, open_database


DEMO_FARES: tuple[tuple[str, str, str, float], ...] = (
    ("2026-09-07", "DEL-BOM", "T1", 6000.0),
    ("2026-09-07", "DEL-BOM", "T7", 6000.0),
    ("2026-09-07", "DEL-BOM", "T30", 6000.0),
    ("2026-09-07", "DEL-BLR", "T1", 12000.0),
    ("2026-09-07", "DEL-BLR", "T7", 12000.0),
    ("2026-09-07", "DEL-BLR", "T30", 12000.0),
    ("2026-09-08", "DEL-BOM", "T1", 7200.0),
    ("2026-09-08", "DEL-BOM", "T7", 7800.0),
    ("2026-09-08", "DEL-BOM", "T30", 6600.0),
    ("2026-09-08", "DEL-BLR", "T1", 13200.0),
    ("2026-09-08", "DEL-BLR", "T7", 12000.0),
    ("2026-09-08", "DEL-BLR", "T30", 14400.0),
)


def seed_demo_data(db_path: str | Path = DB_PATH) -> int:
    """Insert the idempotent demo basket and return its newly written row count."""
    connection = open_database(db_path)
    try:
        inserted = 0
        for search_day, route, window, total in DEMO_FARES:
            search_date = date.fromisoformat(search_day)
            base = round(total / 1.18, 2)
            quote = build_quote(
                "demo",
                route,
                search_date,
                window,
                "ok",
                search_date=search_date,
                carrier="IndiGo (demo)",
                fare_class="demo / not live quote",
                base_fare=base,
                taxes_and_fees=round(total - base, 2),
                total_fare=total,
            )
            inserted += int(insert_quote(connection, quote))
        return inserted
    finally:
        connection.close()


if __name__ == "__main__":
    print({"inserted": seed_demo_data(), "total_rows": len(DEMO_FARES)})
