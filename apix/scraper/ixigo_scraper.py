"""Playwright scraper for the Ixigo flight search site."""

from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

try:
    from scraper_utils import (
        DB_PATH, DomainRateLimiter, ROUTES, USER_AGENT, WINDOWS, build_quote,
        extract_lowest_quote, insert_quote, is_already_scraped, log_error, open_database,
        page_has_sold_out, robots_allowed, travel_date_for, validate_inputs,
    )
except ModuleNotFoundError:  # Supports importing as apix.scraper.ixigo_scraper.
    from .scraper_utils import (
        DB_PATH, DomainRateLimiter, ROUTES, USER_AGENT, WINDOWS, build_quote,
        extract_lowest_quote, insert_quote, is_already_scraped, log_error, open_database,
        page_has_sold_out, robots_allowed, travel_date_for, validate_inputs,
    )

SOURCE = "ixigo"
BASE_URL = os.getenv("APIX_IXIGO_SEARCH_URL", "https://www.ixigo.com/search/result/flight")
SELECTORS = {
    "card": ("[data-testid*='flight']", ".flight-result", ".flight-card", "[class*='flight-card']"),
    # Broad price selectors can match a badge or discount, not the payable
    # flight total. Keep these selectors deliberately total-fare-specific.
    "total": (
        "[data-testid*='total-fare']",
        "[data-testid*='totalFare']",
        "[aria-label*='total fare']",
        ".total-fare",
    ),
    "carrier": ("[data-testid*='airline']", ".airline", "[class*='airline']"),
    "fare_class": ("[data-testid*='cabin']", ".fare-class", "[class*='fare-class']"),
    "base": ("[data-testid*='base']", ".base-fare", "[class*='base-fare']"),
    "taxes": ("[data-testid*='tax']", ".taxes", ".taxes-and-fees"),
    "flight_number": ("[data-testid*='flight-number']", ".flight-number"),
    "departure": ("[data-testid*='departure']", ".departure-time", ".departure"),
}
SOLD_OUT_MARKERS = ("sold out", "not available", "fully booked")


def search_url(route: str, travel_date: date) -> str:
    origin, destination = ROUTES[route]
    return f"{BASE_URL}?{urlencode({'from': origin, 'to': destination, 'date': travel_date.isoformat()})}"


def scrape(route: str, window: str, run_date: date | None = None, db_path=DB_PATH, limiter: DomainRateLimiter | None = None) -> dict | None:
    """Scrape one permitted Ixigo route/window and insert its audit row."""
    validate_inputs(route, window)
    search_date = run_date or date.today()
    travel_date = travel_date_for(window, search_date)
    connection = open_database(db_path)
    if is_already_scraped(connection, SOURCE, route, travel_date, window, search_date):
        connection.close()
        return None
    limiter = limiter or DomainRateLimiter()
    target_url = search_url(route, travel_date)
    if not robots_allowed(target_url, limiter, USER_AGENT):
        connection.close()
        return None

    for attempt in range(2):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()
                limiter.before_request("www.ixigo.com")
                page.goto(target_url, wait_until="networkidle", timeout=60_000)
                page.wait_for_timeout(3_000)
                fields = extract_lowest_quote(
                    page,
                    SELECTORS,
                    prefer_carrier="IndiGo",
                    debug_fares=os.getenv("APIX_DEBUG_FARE_CAPTURE") == "1",
                )
                if fields:
                    quote = build_quote(
                        SOURCE, route, travel_date, window, "ok", search_date=search_date, **fields
                    )
                elif page_has_sold_out(page, SOLD_OUT_MARKERS):
                    quote = build_quote(
                        SOURCE, route, travel_date, window, "sold_out", search_date=search_date
                    )
                else:
                    quote = build_quote(
                        SOURCE, route, travel_date, window, "no_results", search_date=search_date
                    )
                insert_quote(connection, quote)
                context.close()
                browser.close()
                connection.close()
                return quote
        except Exception as exc:
            if attempt == 0:
                import time
                time.sleep(30)
            else:
                log_error(SOURCE, f"{route} {window} {travel_date}: {exc}")
                quote = build_quote(
                    SOURCE, route, travel_date, window, "error", search_date=search_date
                )
                insert_quote(connection, quote)
                connection.close()
                return quote
    return None


def run_daily(run_date: date | None = None, db_path=DB_PATH) -> list[dict | None]:
    limiter = DomainRateLimiter()
    return [scrape(route, window, run_date, db_path, limiter) for route in ROUTES for window in WINDOWS]
