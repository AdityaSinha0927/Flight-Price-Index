"""FastAPI read API for APIx index and quote data."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "apix.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
ROUTES = {"DEL-BOM", "DEL-BLR", "ALL"}
WINDOWS = {"T1", "T7", "T30"}
WINDOW_ORDER = ("T1", "T7", "T30")

app = FastAPI(title="APIx API", version="1.0.0")


class IndexPoint(BaseModel):
    date: str
    index_value: float


class IndexResponse(BaseModel):
    route: str
    freq: Literal["daily", "weekly", "monthly"]
    base_period: str | None
    data: list[IndexPoint]


class QuotePoint(BaseModel):
    source: str
    route: str
    travel_date: str
    advance_window: str
    total_fare: float | None
    is_outlier: bool


class QuotesResponse(BaseModel):
    data: list[QuotePoint]


class ElasticityPoint(BaseModel):
    advance_window: str
    avg_total_fare: float


class ElasticityResponse(BaseModel):
    route: str
    data: list[ElasticityPoint]


class HealthResponse(BaseModel):
    status: str
    last_scrape_at: str | None


def _connection() -> sqlite3.Connection:
    """Open the configured database, using an empty schema if it is absent."""
    if DB_PATH.exists():
        connection = sqlite3.connect(DB_PATH)
        connection.row_factory = sqlite3.Row
        return connection
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _validate_route(route: str, *, allow_all: bool = True) -> str:
    normalized = route.upper()
    valid = ROUTES if allow_all else ROUTES - {"ALL"}
    if normalized not in valid:
        allowed = ", ".join(sorted(valid))
        raise HTTPException(status_code=400, detail=f"Invalid route '{route}'. Expected one of: {allowed}")
    return normalized


def _validate_dates(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")


def _date_clause(column: str, start_date: date | None, end_date: date | None) -> tuple[str, list[str]]:
    clauses: list[str] = []
    values: list[str] = []
    if start_date:
        clauses.append(f"{column} >= ?")
        values.append(start_date.isoformat())
    if end_date:
        clauses.append(f"{column} <= ?")
        values.append(end_date.isoformat())
    return (" AND ".join(clauses) or "1=1", values)


def _period_start(value: str, freq: Literal["weekly", "monthly"]) -> str:
    parsed = date.fromisoformat(value)
    if freq == "monthly":
        return parsed.replace(day=1).isoformat()
    return (parsed - timedelta(days=parsed.weekday())).isoformat()


@app.get("/api/v1/index", response_model=IndexResponse)
def get_index(
    route: str = Query("ALL"),
    freq: Literal["daily", "weekly", "monthly"] = Query("daily"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
) -> IndexResponse:
    route = _validate_route(route)
    _validate_dates(start_date, end_date)
    date_filter, date_values = _date_clause("index_date", start_date, end_date)
    connection = _connection()
    try:
        rows = connection.execute(
            f"""
            SELECT index_date, index_value, base_period
            FROM index_values
            WHERE route = ? AND {date_filter}
            ORDER BY index_date
            """,
            [route, *date_values],
        ).fetchall()
    finally:
        connection.close()

    base_period = rows[0]["base_period"] if rows else None
    if freq == "daily":
        points = [IndexPoint(date=row["index_date"], index_value=float(row["index_value"])) for row in rows]
    else:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            grouped[_period_start(row["index_date"], freq)].append(float(row["index_value"]))
        points = [
            IndexPoint(date=period, index_value=sum(values) / len(values))
            for period, values in sorted(grouped.items())
        ]
    return IndexResponse(route=route, freq=freq, base_period=base_period, data=points)


@app.get("/api/v1/quotes", response_model=QuotesResponse)
def get_quotes(
    route: str | None = Query(None),
    advance_window: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
) -> QuotesResponse:
    if route is not None:
        route = _validate_route(route, allow_all=False)
    if advance_window is not None:
        advance_window = advance_window.upper()
        if advance_window not in WINDOWS:
            raise HTTPException(status_code=400, detail="Invalid advance_window. Expected one of: T1, T7, T30")
    _validate_dates(start_date, end_date)
    date_filter, date_values = _date_clause("travel_date", start_date, end_date)
    clauses = [date_filter]
    values: list[str] = [*date_values]
    if route:
        clauses.append("route = ?")
        values.append(route)
    if advance_window:
        clauses.append("advance_window = ?")
        values.append(advance_window)
    connection = _connection()
    try:
        rows = connection.execute(
            f"""
            SELECT source, route, travel_date, advance_window, total_fare, is_outlier
            FROM clean_quotes
            WHERE {' AND '.join(clauses)}
            ORDER BY travel_date, route, advance_window, source
            """,
            values,
        ).fetchall()
    finally:
        connection.close()
    return QuotesResponse(
        data=[
            QuotePoint(
                source=row["source"], route=row["route"], travel_date=row["travel_date"],
                advance_window=row["advance_window"],
                total_fare=float(row["total_fare"]) if row["total_fare"] is not None else None,
                is_outlier=bool(row["is_outlier"]),
            )
            for row in rows
        ]
    )


@app.get("/api/v1/elasticity", response_model=ElasticityResponse)
def get_elasticity(route: str = Query(...)) -> ElasticityResponse:
    route = _validate_route(route, allow_all=False)
    placeholders = ", ".join("?" for _ in WINDOW_ORDER)
    connection = _connection()
    try:
        rows = connection.execute(
            f"""
            SELECT advance_window, AVG(total_fare) AS avg_total_fare
            FROM clean_quotes
            WHERE route = ? AND is_outlier = 0 AND total_fare IS NOT NULL
              AND advance_window IN ({placeholders})
            GROUP BY advance_window
            """,
            [route, *WINDOW_ORDER],
        ).fetchall()
    finally:
        connection.close()
    values = {row["advance_window"]: float(row["avg_total_fare"]) for row in rows}
    return ElasticityResponse(
        route=route,
        data=[ElasticityPoint(advance_window=window, avg_total_fare=values[window]) for window in WINDOW_ORDER if window in values],
    )


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    connection = _connection()
    try:
        row = connection.execute("SELECT MAX(scraped_at) AS last_scrape_at FROM raw_quotes").fetchone()
    finally:
        connection.close()
    return HealthResponse(status="ok", last_scrape_at=row["last_scrape_at"] if row else None)
