# APIx — Airfare Price Index

APIx is a prototype that tracks Indian domestic airfare quotes and converts
them into a daily CPI-style price index.

## Problem statement reference

SIH Statement ID 26056 addresses the gap between manually collected airfare
components in official inflation statistics and the dynamic prices seen by
travellers online. APIx demonstrates a small, transparent system for
collecting online fares, cleaning them, calculating an index, serving the
results through an API, and visualizing the trend.

## What this prototype does

The implemented prototype is scoped to the locked-down definition of done:

- Scraper modules for IndiGo and Ixigo using Playwright.
- The two one-way routes `DEL-BOM` and `DEL-BLR`.
- Three booking windows: `T1`, `T7`, and `T30`.
- SQLite storage for raw and clean quotes.
- Five-step cleaning pipeline: fare decomposition, duplicate handling,
  missing-value handling, IQR outlier flagging, and sanity bounds.
- Daily route and combined index values using price relatives and a weighted
  geometric mean.
- FastAPI endpoints for index values, quotes, elasticity, and health.
- A single-page Streamlit dashboard with trend, route comparison, elasticity,
  back-test, and raw-data sections.

## Architecture

```text
[Scrapers] -> [Raw Data Store] -> [Cleaning Pipeline] -> [Clean Data Store]
                                                                |
                                                                v
                                                        [Index Engine]
                                                                |
                                                                v
                                                   [API Layer] -> [Dashboard]
```

## Tech stack

| Component | Technology | Notes |
|---|---|---|
| Scraper | Python + Playwright | Headless browser for JS-rendered pages |
| Scheduler | Python daily runner | Runs both sources and then rebuilds cleaned data/index |
| Raw data store | SQLite | `db/apix.db`, table `raw_quotes` |
| Cleaning pipeline | Python + pandas | Writes `clean_quotes` |
| Clean data store | SQLite | Same database file |
| Index engine | Python + pandas/numpy | Writes `index_values` |
| API layer | FastAPI | JSON endpoints under `/api/v1` |
| Dashboard | Streamlit + Plotly | Single-page prototype |

## Setup

Use Python 3.10 or newer. The implementation was syntax-checked and run with
Python 3.13 in this environment.

From the `apix` directory:

```bash
pip install -r requirements.txt
playwright install
```

Initialize the SQLite database:

```bash
python -c "import sqlite3; c=sqlite3.connect('db/apix.db'); c.executescript(open('db/schema.sql').read()); c.close()"
```

The schema command is idempotent. The database is also initialized by the
pipeline/API helpers when the file does not yet exist.

## How to run

### Scrapers

Run one route/window manually after installing Playwright and its browser:

```bash
python -c "from scraper.indigo_scraper import scrape; print(scrape('DEL-BOM', 'T1'))"
python -c "from scraper.ixigo_scraper import scrape; print(scrape('DEL-BLR', 'T7'))"
```

Each scraper checks `robots.txt`, uses a descriptive user agent, waits 3–6
seconds between requests to the same domain, retries one failed page once
after 30 seconds, and writes audit rows to `raw_quotes`.

For selector troubleshooting during an authorized run, set
`APIX_DEBUG_FARE_CAPTURE=1`. The scraper logs the selected fare element's text
and result-card HTML, while rejecting a value below INR 1,000 as an
implausible payable airfare.

The runner and browser dependency are locally testable, but the configured
live sources may refuse automated collection. Ixigo's current `robots.txt`
disallows `/search/result/`, which is the configured flight-results path, and
IndiGo returned HTTP 403 when the declared research-bot user agent requested
its `robots.txt`. The scraper fails closed in both cases and the daily summary
will report fewer than 12 stored rows. Use an authorized source/API before
relying on this prototype for unattended live data.

### Offline demo data

If authorized live collection is unavailable, seed a clearly labelled
`demo` source with realistic INR fares for a dashboard demonstration:

```bash
python -m db.seed_demo
python -m pipeline.clean
python -m index.build_index
```

These rows are marked `IndiGo (demo)` and `demo / not live quote`; they are
only for demonstrating the dashboard and index mechanics.

### Daily runner and scheduler

Use the combined runner instead of invoking one source at a time. One run
attempts all 2 sources x 2 routes x 3 windows and prints a summary showing how
many of the expected 12 audit rows are actually stored. It then runs the
cleaning pipeline and index builder:

```bash
python -m scraper.scheduler
```

That command performs one daily cycle and exits. To keep a process running,
execute a cycle immediately and then repeat it every day at 06:00 local time:

```bash
python -m scraper.scheduler --loop --at 06:00
```

Leave that terminal/process running, or configure the one-shot command in
Windows Task Scheduler. Re-running on the same date is safe: the database
uniqueness constraint prevents duplicate route/source/window rows.

### Cleaning pipeline

```bash
python -m pipeline.clean
```

### Index engine

```bash
python -m index.build_index
```

### FastAPI server

From the workspace root (`FPI`), run:

```bash
python -m uvicorn apix.api.main:app --host 127.0.0.1 --port 8001 --reload
```

Alternatively, after changing into the `apix` directory, run:

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

The API is available at `http://127.0.0.1:8001/api/v1`; interactive OpenAPI
documentation is at `/docs`.

### Streamlit dashboard

For normal local use, start both services with one command. It starts FastAPI,
waits for its health endpoint, then launches Streamlit. Closing Streamlit also
stops the FastAPI process it started:

```powershell
.\.venv\Scripts\python.exe run_dashboard.py
```

This prevents the dashboard from opening before FastAPI is ready. If the
virtual environment is new, install dependencies once first:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

To run the dashboard separately (only when FastAPI is already running), use:

In a second terminal:

```bash
streamlit run dashboard/app.py
```

The dashboard reads from `http://127.0.0.1:8001/api/v1` by default. Set
`APIX_API_URL` to point it at another API host.

## Tests

Run the full test suite from the project root:

```bash
pytest -q
```

The verified suite contains eight passing unit tests covering the cleaning
rules, price-relative index calculation, base-period normalization, and
weekly/monthly display aggregation.

## Known limitations

- Only `DEL-BOM` and `DEL-BLR` are supported; return fares are out of scope.
- Only IndiGo and Ixigo are supported.
- Only `T1`, `T7`, and `T30` are supported.
- There is no authentication, streaming layer, mobile app, CAPTCHA solving,
  proxy rotation, or anti-bot evasion. The included scheduler is a lightweight
  foreground process; production deployment should supervise it or use an OS
  scheduler.
- Route weights use an equal 0.5/0.5 split because verified DGCA traffic-share
  data was not bundled with the prototype.
- When a site provides only a total fare, the cleaning pipeline estimates the
  split using `total_fare / 1.18`.
- Source selectors and URLs are prototype-level and may need maintenance if
  either site changes its layout.
- The configured Ixigo results path is currently disallowed by its published
  `robots.txt`; IndiGo may also reject the declared research-bot user agent.
  The scraper does not bypass either restriction.
- The dashboard back-test uses the supplied MoSPI `cpi_1059.xlsx` airfare CPI
  series and requires that file at `APIX_MOSPI_CPI_PATH` or alongside the
  project/workspace. Both series are plotted across their full available
  ranges; non-overlapping periods are marked as a publication gap.
- Weekly and monthly index values are display-time averages of daily values;
  they are not separate scraping pipelines.

## Back-test results

The dashboard loads the supplied official MoSPI CPI workbook, filters it to
`All India` / `Combined`, and uses its domestic-airfare index for January 2025
through July 2026. It joins that series to APIx's monthly `ALL` index by
year-month and independently rebases both series to 100 at the first
overlapping month. The resulting chart is a trend comparison, not an exact
index-level comparison.

## Ethical scraping note

The scraper implementation:

- Fetches and checks each target domain's `robots.txt` before scraping and
  fails closed when the check cannot be completed.
- Uses `APIx-Research-Bot/0.1` rather than impersonating a browser.
- Enforces a randomized 3–6 second delay between same-domain requests.
- Records `sold_out`, `no_results`, and final `error` attempts in SQLite.
- Retries a failed page once after 30 seconds and logs the failure.
- Enforces one source/route/window scrape per search date through the database
  uniqueness constraint.

No CAPTCHA-solving service, proxy/IP rotation, stealth plugin, or other
anti-bot evasion technique is included.

## Team / credits

APIx prototype team and contributors. Implementation scaffolding and code
assistance were provided by Codex.
