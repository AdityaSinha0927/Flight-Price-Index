PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    route TEXT NOT NULL,
    carrier TEXT,
    search_date TEXT NOT NULL,
    travel_date TEXT NOT NULL,
    advance_window TEXT NOT NULL,
    fare_class TEXT,
    base_fare REAL,
    taxes_and_fees REAL,
    total_fare REAL,
    flight_number TEXT,
    departure_time TEXT,
    scrape_status TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    UNIQUE (source, route, travel_date, advance_window, search_date)
);

CREATE TABLE IF NOT EXISTS clean_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_quote_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    route TEXT NOT NULL,
    carrier TEXT,
    search_date TEXT NOT NULL,
    travel_date TEXT NOT NULL,
    advance_window TEXT NOT NULL,
    fare_class TEXT,
    base_fare REAL,
    taxes_and_fees REAL,
    total_fare REAL,
    flight_number TEXT,
    departure_time TEXT,
    scraped_at TEXT NOT NULL,
    is_outlier INTEGER NOT NULL DEFAULT 0,
    cleaning_notes TEXT,
    FOREIGN KEY (raw_quote_id) REFERENCES raw_quotes (id)
);

CREATE TABLE IF NOT EXISTS index_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_date TEXT NOT NULL,
    route TEXT NOT NULL,
    index_value REAL NOT NULL,
    base_period TEXT NOT NULL,
    num_quotes_used INTEGER NOT NULL,
    UNIQUE (index_date, route)
);
