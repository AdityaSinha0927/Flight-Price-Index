# SCRAPER_SPEC.md

## Sources to build (per SCOPE.md)

1. IndiGo (airline direct site)
2. Ixigo (OTA)

## Fields to extract per quote

Each scrape of one (route, date, advance-purchase window) combination must
produce a record with these fields:

- `source` (e.g. "indigo", "ixigo")
- `route` (e.g. "DEL-BOM")
- `carrier` (airline actually operating the flight — on Ixigo this may differ
  from the source site)
- `search_date` (the date the scrape was run)
- `travel_date` (the date of the flight being priced)
- `advance_window` (T+1, T+7, or T+30)
- `fare_class` (e.g. economy/saver — whatever the site exposes)
- `base_fare`
- `taxes_and_fees` (includes UDF, convenience fee, GST if shown separately)
- `total_fare`
- `flight_number` (if available)
- `departure_time` (if available)
- `scrape_status` ("ok", "sold_out", "no_results", "error")

## Per-source rules

### IndiGo

- Use Playwright to load the booking search page for the given
  origin/destination/date.
- Wait for the fare grid/calendar or results list to fully render (JS-heavy
  page) before extracting.
- Take the lowest available economy fare for the day as the quote, unless a
  specific fare class is being tested.

### Ixigo

- Use Playwright to search the same route/date.
- Extract the lowest fare shown for the IndiGo flight on that route if
  available; if not available, take the lowest fare shown for any carrier and
  record which carrier it is in the `carrier` field.

## Handling edge cases

- If no flights are found for a route/date: record one row with
  `scrape_status = "no_results"` and null fare fields. Do not skip silently.
- If a flight is fully sold out but shown on the page: record
  `scrape_status = "sold_out"`.
- If the page fails to load or times out: record `scrape_status = "error"`
  and log the error message and timestamp to a log file. Retry once after 30
  seconds; if it fails again, move on to the next item.

## Ethical scraping rules (must be implemented, not just documented)

- Before scraping a domain for the first time in a run, fetch and check its
  `robots.txt`. If the target path is disallowed, log this and skip that
  source — do not scrape it anyway.
- Minimum delay of 3 seconds between consecutive requests to the same domain,
  with random jitter (e.g. 3-6 seconds) to avoid a robotic request pattern.
- Use a descriptive User-Agent string that does not impersonate a real
  browser dishonestly (e.g. `APIx-Research-Bot/0.1`) if the site allows
  custom user agents without blocking; if the site blocks non-browser user
  agents entirely, document this limitation rather than spoofing headers to
  bypass it.
- No CAPTCHA-solving services, no IP/proxy rotation for evasion purposes.
- No more than one scrape run per route/source/window per day.

## Scheduling

- One run per day, covering all 2 routes x 2 sources x 3 windows (12
  scrapes), for the travel dates implied by each window (today+1, today+7,
  today+30 from the day of the run).
- Trigger via a simple scheduler (cron, or a `schedule`-based Python loop) —
  no need for Airflow or a message queue in this prototype.
