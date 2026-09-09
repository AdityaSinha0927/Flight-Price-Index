# DATA_SCHEMA.md

Database: SQLite file at `db/apix.db`. Also save the raw DDL in
`db/schema.sql`.

## Table: raw_quotes

One row per scrape attempt, before cleaning.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| source | TEXT | "indigo" or "ixigo" |
| route | TEXT | e.g. "DEL-BOM" |
| carrier | TEXT | nullable |
| search_date | TEXT (ISO date) | when the scrape ran |
| travel_date | TEXT (ISO date) | date being priced |
| advance_window | TEXT | "T1", "T7", "T30" |
| fare_class | TEXT | nullable |
| base_fare | REAL | nullable |
| taxes_and_fees | REAL | nullable |
| total_fare | REAL | nullable |
| flight_number | TEXT | nullable |
| departure_time | TEXT | nullable |
| scrape_status | TEXT | "ok", "sold_out", "no_results", "error" |
| scraped_at | TEXT (ISO datetime) | timestamp of the scrape |

## Table: clean_quotes

One row per validated quote, after the cleaning pipeline. Same columns as
`raw_quotes` minus `scrape_status`, plus:

| Column | Type | Notes |
|---|---|---|
| raw_quote_id | INTEGER | foreign key to raw_quotes.id |
| is_outlier | INTEGER (0/1) | flagged but not deleted, for transparency |
| cleaning_notes | TEXT | e.g. "tax split estimated", "duplicate removed" |

Only rows with `scrape_status = "ok"` from raw_quotes are eligible to become
clean_quotes rows. `sold_out`, `no_results`, and `error` rows are kept in
raw_quotes for auditability but excluded from cleaning.

## Table: index_values

One row per day per route (and one row per day for the overall combined
index).

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| index_date | TEXT (ISO date) | the day this index value represents |
| route | TEXT | a specific route, or "ALL" for the combined index |
| index_value | REAL | see INDEX_METHODOLOGY.md for the formula |
| base_period | TEXT | the reference period this index is relative to |
| num_quotes_used | INTEGER | how many clean_quotes rows fed this value |

## Indexing / constraints

- Unique constraint on (source, route, travel_date, advance_window,
  search_date) in raw_quotes to prevent duplicate scrapes from being
  double-counted.
- Unique constraint on (index_date, route) in index_values.
