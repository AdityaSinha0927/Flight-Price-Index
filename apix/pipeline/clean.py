"""Apply the five documented cleaning rules to ``raw_quotes``.

The pipeline rebuilds ``clean_quotes`` from eligible raw rows on each run. The
raw table is never modified; discarded rows are recorded in the cleaning log.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from scraper.scraper_utils import DB_PATH
except ModuleNotFoundError:
    DB_PATH = Path(__file__).resolve().parents[1] / "db" / "apix.db"

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"
LOG_PATH = ROOT / "logs" / "cleaning.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

LOGGER = logging.getLogger("apix.cleaning")
_HANDLER = logging.FileHandler(LOG_PATH, encoding="utf-8")
_HANDLER.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
if not LOGGER.handlers:
    LOGGER.addHandler(_HANDLER)
LOGGER.setLevel(logging.INFO)

RAW_COLUMNS = (
    "id", "source", "route", "carrier", "search_date", "travel_date",
    "advance_window", "fare_class", "base_fare", "taxes_and_fees", "total_fare",
    "flight_number", "departure_time", "scraped_at",
)
CLEAN_COLUMNS = (
    "raw_quote_id", "source", "route", "carrier", "search_date", "travel_date",
    "advance_window", "fare_class", "base_fare", "taxes_and_fees", "total_fare",
    "flight_number", "departure_time", "scraped_at", "is_outlier", "cleaning_notes",
)


def _log(category: str, raw_id: int, message: str) -> None:
    LOGGER.info("%s raw_quote_id=%s %s", category, raw_id, message)


def _connection(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='raw_quotes'").fetchone():
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _read_ok_quotes(connection: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT id, source, route, carrier, search_date, travel_date,
               advance_window, fare_class, base_fare, taxes_and_fees,
               total_fare, flight_number, departure_time, scraped_at
        FROM raw_quotes
        WHERE scrape_status = 'ok'
        ORDER BY scraped_at ASC, id ASC
    """
    return pd.read_sql_query(query, connection)


def _decompose_fare(row: pd.Series) -> tuple[float | None, float | None, float | None, list[str]]:
    """Apply Step 1 and return base, taxes, total, and audit notes."""
    total = row["total_fare"]
    base = row["base_fare"]
    taxes = row["taxes_and_fees"]
    notes: list[str] = []

    if pd.isna(total):
        return None, None, None, notes

    if pd.isna(base) or pd.isna(taxes):
        base = float(total) / 1.18
        taxes = float(total) - base
        notes.append("tax split estimated")
    else:
        base = float(base)
        taxes = float(taxes)

    recomputed_total = base + taxes
    if float(total) != recomputed_total:
        notes.append("total recomputed")
    return base, taxes, recomputed_total, notes


def _deduplicate(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply Step 2, retaining the latest scraped row in each raw-key group."""
    if frame.empty:
        return frame
    key = ["source", "route", "travel_date", "advance_window", "search_date"]
    ordered = frame.sort_values([*key, "scraped_at", "id"])
    duplicate_mask = ordered.duplicated(key, keep="last")
    for raw_id in ordered.loc[duplicate_mask, "id"].astype(int):
        _log("duplicate_removed", raw_id, 'cleaning_notes="duplicate removed"')
    return ordered.loc[~duplicate_mask].copy()


def _drop_missing_and_invalid(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply Steps 3 and 5 before statistical outlier calculation."""
    if frame.empty:
        return frame
    keep_rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        total = row["total_fare"]
        original_total = row.get("_original_total_fare", total)
        raw_id = int(row["id"])
        if pd.isna(original_total) or float(original_total) == 0:
            _log("missing_fare", raw_id, "dropped because total_fare is null or zero")
            continue
        if float(original_total) <= 0 or float(original_total) > 200000 or pd.isna(total) or float(total) <= 0 or float(total) > 200000:
            _log("sanity_bounds", raw_id, f"dropped because total_fare={original_total} is outside (0, 200000]")
            continue
        keep_rows.append(row)
    return pd.DataFrame(keep_rows, columns=frame.columns)


def _mark_outliers(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply Step 4 using each group's most recent 14 calendar days."""
    if frame.empty:
        frame["is_outlier"] = pd.Series(dtype="int64")
        return frame
    frame = frame.copy()
    frame["is_outlier"] = 0
    frame["_search_date"] = pd.to_datetime(frame["search_date"], errors="raise")
    for (_, _), group in frame.groupby(["route", "advance_window"], sort=False):
        latest = group["_search_date"].max()
        recent = group[group["_search_date"] >= latest - pd.Timedelta(days=13)]
        values = recent["total_fare"].astype(float)
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_index = group.index[(group["total_fare"] < lower) | (group["total_fare"] > upper)]
        frame.loc[outlier_index, "is_outlier"] = 1
        for raw_id in frame.loc[outlier_index, "id"].astype(int):
            _log("statistical_outlier", raw_id, f"flagged using Q1={q1:g}, Q3={q3:g}, IQR={iqr:g}")
    return frame.drop(columns="_search_date")


def clean_database(db_path: str | Path = DB_PATH) -> dict[str, int]:
    """Read eligible raw quotes, apply all five rules, and rebuild clean_quotes."""
    connection = _connection(db_path)
    try:
        frame = _read_ok_quotes(connection)
        frame = _deduplicate(frame)

        if not frame.empty:
            frame["_original_total_fare"] = frame["total_fare"]
            decomposed = frame.apply(_decompose_fare, axis=1, result_type="expand")
            decomposed.columns = ["base_fare", "taxes_and_fees", "total_fare", "_notes"]
            frame[["base_fare", "taxes_and_fees", "total_fare", "_notes"]] = decomposed
            frame = _drop_missing_and_invalid(frame)
            frame = frame.drop(columns="_original_total_fare", errors="ignore")
        frame = _mark_outliers(frame)

        with connection:
            connection.execute("DELETE FROM clean_quotes")
            for row in frame.to_dict("records"):
                notes = [note for note in row.get("_notes", []) if note]
                connection.execute(
                    f"INSERT INTO clean_quotes ({', '.join(CLEAN_COLUMNS)}) VALUES ({', '.join('?' for _ in CLEAN_COLUMNS)})",
                    [
                        row["id"], row["source"], row["route"], row["carrier"], row["search_date"],
                        row["travel_date"], row["advance_window"], row["fare_class"], row["base_fare"],
                        row["taxes_and_fees"], row["total_fare"], row["flight_number"], row["departure_time"],
                        row["scraped_at"], int(row["is_outlier"]), "; ".join(notes) or None,
                    ],
                )
        return {
            "raw_ok": int(len(_read_ok_quotes(connection))),
            "cleaned": int(len(frame)),
            "outliers": int(frame["is_outlier"].sum()) if not frame.empty else 0,
        }
    finally:
        connection.close()


def run_cleaning(db_path: str | Path = DB_PATH) -> dict[str, int]:
    """Compatibility entry point for scheduled pipeline execution."""
    return clean_database(db_path)


if __name__ == "__main__":
    print(clean_database())
