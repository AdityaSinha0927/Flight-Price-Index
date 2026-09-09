"""Shared, deliberately conservative helpers for the APIx scrapers."""

from __future__ import annotations

import logging
import os
import random
import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "apix.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
LOG_PATH = ROOT / "logs" / "scraper_errors.log"
USER_AGENT = "APIx-Research-Bot/0.1"
ROUTES = {"DEL-BOM": ("DEL", "BOM"), "DEL-BLR": ("DEL", "BLR")}
WINDOWS = {"T1": 1, "T7": 7, "T30": 30}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("apix.scraper")


class DomainRateLimiter:
    """Enforce a 3–6 second gap between requests to each domain."""

    def __init__(self, sleep=time.sleep, random_uniform=random.uniform) -> None:
        self._last_request: dict[str, float] = {}
        self.robots_cache: dict[str, bool] = {}
        self._sleep = sleep
        self._random_uniform = random_uniform

    def before_request(self, domain: str) -> None:
        last = self._last_request.get(domain)
        if last is not None:
            wait_for = max(0.0, self._random_uniform(3.0, 6.0) - (time.monotonic() - last))
            if wait_for:
                self._sleep(wait_for)
        self._last_request[domain] = time.monotonic()


def _domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def robots_allowed(url: str, limiter: DomainRateLimiter, user_agent: str = USER_AGENT) -> bool:
    """Fetch robots.txt and fail closed if it cannot be checked."""
    parsed = urlparse(url)
    domain = _domain(url)
    if domain in limiter.robots_cache:
        return limiter.robots_cache[domain]
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        limiter.before_request(domain)
        request = Request(robots_url, headers={"User-Agent": user_agent})
        with urlopen(request, timeout=20) as response:
            content = response.read().decode("utf-8", errors="replace")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(content.splitlines())
        allowed = parser.can_fetch(user_agent, url)
        if not allowed:
            LOGGER.warning("robots.txt disallows target path: %s", url)
        limiter.robots_cache[domain] = allowed
        return allowed
    except Exception as exc:
        log_error(domain, f"robots.txt check failed; source skipped: {exc}")
        limiter.robots_cache[domain] = False
        return False


def log_error(source: str, message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(timezone.utc).isoformat()} [{source}] {message}\n")
    LOGGER.error("[%s] %s", source, message)


def parse_money(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", value.replace("₹", ""))
    return float(match.group(0).replace(",", "")) if match else None


def text_from_first(root: Any, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        locator = root.locator(selector).first
        if locator.count():
            value = locator.inner_text().strip()
            if value:
                return value
    return None


def first_locator(root: Any, selectors: Iterable[str]) -> Any | None:
    for selector in selectors:
        locator = root.locator(selector)
        if locator.count():
            return locator.first
    return None


def extract_lowest_quote(page: Page, selectors: dict[str, tuple[str, ...]], prefer_carrier: str | None = None) -> dict[str, Any] | None:
    """Extract the lowest fare from visible result cards using source selectors."""
    cards = page.locator(selectors["card"])
    candidates: list[dict[str, Any]] = []
    for index in range(cards.count()):
        card = cards.nth(index)
        raw_text = card.inner_text().strip()
        total = parse_money(text_from_first(card, selectors["total"]) or raw_text)
        if total is None:
            continue
        carrier = text_from_first(card, selectors["carrier"])
        candidates.append(
            {
                "carrier": carrier,
                "fare_class": text_from_first(card, selectors["fare_class"]),
                "base_fare": parse_money(text_from_first(card, selectors["base"])),
                "taxes_and_fees": parse_money(text_from_first(card, selectors["taxes"])),
                "total_fare": total,
                "flight_number": text_from_first(card, selectors["flight_number"]),
                "departure_time": text_from_first(card, selectors["departure"]),
                "_preferred": bool(prefer_carrier and carrier and prefer_carrier.lower() in carrier.lower()),
            }
        )
    if not candidates:
        return None
    preferred = [item for item in candidates if item.pop("_preferred")]
    return min(preferred or candidates, key=lambda item: item["total_fare"])


def page_has_sold_out(page: Page, markers: tuple[str, ...]) -> bool:
    content = page.locator("body").inner_text().lower()
    return any(marker.lower() in content for marker in markers)


def open_database(path: str | Path = DB_PATH) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    if not connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw_quotes'").fetchone():
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def insert_quote(connection: sqlite3.Connection, quote: dict[str, Any]) -> bool:
    columns = (
        "source", "route", "carrier", "search_date", "travel_date", "advance_window",
        "fare_class", "base_fare", "taxes_and_fees", "total_fare", "flight_number",
        "departure_time", "scrape_status", "scraped_at",
    )
    values = [quote.get(column) for column in columns]
    cursor = connection.execute(
        f"INSERT OR IGNORE INTO raw_quotes ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        values,
    )
    connection.commit()
    return cursor.rowcount == 1


def build_quote(source: str, route: str, travel_date: date, window: str, status: str, **fields: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "source": source,
        "route": route,
        "search_date": now.date().isoformat(),
        "travel_date": travel_date.isoformat(),
        "advance_window": window,
        "scrape_status": status,
        "scraped_at": now.isoformat(),
        **fields,
    }


def validate_inputs(route: str, window: str) -> None:
    if route not in ROUTES:
        raise ValueError(f"Unsupported route: {route}; expected one of {sorted(ROUTES)}")
    if window not in WINDOWS:
        raise ValueError(f"Unsupported advance window: {window}; expected one of {sorted(WINDOWS)}")


def travel_date_for(window: str, run_date: date | None = None) -> date:
    validate_inputs("DEL-BOM", window)
    return (run_date or date.today()) + timedelta(days=WINDOWS[window])


def is_already_scraped(connection: sqlite3.Connection, source: str, route: str, travel_date: date, window: str) -> bool:
    return bool(connection.execute(
        "SELECT 1 FROM raw_quotes WHERE source=? AND route=? AND travel_date=? AND advance_window=? AND search_date=?",
        (source, route, travel_date.isoformat(), window, date.today().isoformat()),
    ).fetchone())


__all__ = [
    "DB_PATH", "DomainRateLimiter", "PlaywrightTimeoutError", "ROUTES", "USER_AGENT", "WINDOWS",
    "build_quote", "extract_lowest_quote", "first_locator", "insert_quote", "is_already_scraped",
    "log_error", "open_database", "page_has_sold_out", "robots_allowed", "travel_date_for",
    "validate_inputs",
]
