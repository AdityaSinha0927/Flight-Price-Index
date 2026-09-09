# ARCHITECTURE.md

## System overview

```
[Scrapers] -> [Raw Data Store] -> [Cleaning Pipeline] -> [Clean Data Store]
                                                                |
                                                                v
                                                        [Index Engine]
                                                                |
                                                                v
                                                   [API Layer] -> [Dashboard]
```

## Components and required tech choices

Do not substitute these unless a library is genuinely unavailable — if you
must substitute, state it clearly in README.md.

| Component | Technology | Notes |
|---|---|---|
| Scraper | Python + Playwright | Headless browser, handles JS-rendered pages |
| Scheduler | Python `schedule` library or simple cron | Runs scraper once per day per source/route/window |
| Raw data store | SQLite (file-based, no server needed for a prototype) | Table: `raw_quotes` |
| Cleaning pipeline | Python (pandas) | Reads raw_quotes, writes to `clean_quotes` |
| Clean data store | SQLite, same database file, separate table | Table: `clean_quotes` |
| Index engine | Python (pandas/numpy) | Reads `clean_quotes`, writes to `index_values` |
| API layer | FastAPI | Serves index and raw series as JSON |
| Dashboard | Streamlit | Fastest to build for a hackathon prototype; charts via Plotly |

## Folder structure

```
apix/
  scraper/
    indigo_scraper.py
    ixigo_scraper.py
    scraper_utils.py
  pipeline/
    clean.py
    cleaning_rules.py (config-style constants, see CLEANING_RULES.md)
  index/
    build_index.py
    index_methodology.py (formula implementation, see INDEX_METHODOLOGY.md)
  api/
    main.py (FastAPI app)
    schemas.py
  dashboard/
    app.py (Streamlit app)
  db/
    apix.db (SQLite file, generated)
    schema.sql (see DATA_SCHEMA.md)
  tests/
    test_cleaning.py
    test_index.py
  docs/
    (all the .md files provided)
  README.md
```

## Data flow, step by step

1. Scheduler triggers each scraper script once a day.
2. Each scraper visits the target site for each (route, window) pair,
   extracts the fare fields, and inserts one row per quote into `raw_quotes`.
3. Cleaning pipeline runs after all scrapers finish for the day: reads new
   rows from `raw_quotes`, applies rules from CLEANING_RULES.md, writes
   validated rows into `clean_quotes`.
4. Index engine runs after cleaning: reads `clean_quotes`, applies the
   formula in INDEX_METHODOLOGY.md, writes one row per day into
   `index_values`.
5. FastAPI reads from `clean_quotes` and `index_values` to serve the API
   defined in API_SPEC.md.
6. Streamlit dashboard calls the FastAPI endpoints (or reads the DB directly
   for the prototype) to render the charts defined in DASHBOARD_SPEC.md.

## Non-functional requirements

- Every scraper run must respect the target site's robots.txt.
- Minimum 3-second delay between requests to the same source.
- If a scrape fails (site down, blocked, layout changed), log the failure and
  continue — do not crash the whole pipeline.
- All configuration (routes, sources, windows) should be read from SCOPE.md's
  values via a single `config.py`, not hardcoded in multiple files.
