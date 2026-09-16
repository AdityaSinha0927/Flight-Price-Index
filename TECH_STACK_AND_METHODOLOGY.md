# APIx Tech Stack and Methodology

## Tech stack

| Area | Technology | Purpose |
|---|---|---|
| Language | Python 3.10+ | Application and data-processing code |
| Web scraping | Playwright | Loads JavaScript-rendered airfare pages |
| Data processing | pandas and NumPy | Cleaning, aggregation, and index calculations |
| Database | SQLite | Stores raw quotes, clean quotes, and index values |
| API | FastAPI with Uvicorn | Serves health, index, quote, and elasticity endpoints |
| Validation | Pydantic | Defines and validates API response models |
| Dashboard | Streamlit | Provides the interactive multi-page interface |
| Charts | Plotly | Renders index, comparison, elasticity, and back-test charts |
| Testing | pytest | Tests cleaning rules and index calculations |

## System flow

```text
IndiGo and Ixigo
        ↓
Raw quote storage in SQLite
        ↓
Cleaning and validation pipeline
        ↓
Clean quote storage
        ↓
Daily index engine
        ↓
FastAPI endpoints
        ↓
Streamlit dashboard
```

## Methodology

### 1. Collect airfare quotes

The scraper checks two sources: the IndiGo airline website and the Ixigo online travel aggregator. It covers the one-way routes DEL-BOM and DEL-BLR at three booking windows: T+1, T+7, and T+30.

Each quote records its source, route, travel date, booking window, fare components, total fare, flight details when available, and scrape status.

### 2. Follow ethical scraping rules

Before scraping a domain, the system checks `robots.txt` and skips disallowed paths. Requests to the same domain are separated by a randomized delay of roughly three to six seconds. The scraper uses a descriptive research User-Agent and does not use CAPTCHA solving, proxy rotation, or other anti-bot evasion.

Failed pages are logged and retried once after 30 seconds. Each source, route, and booking-window combination is limited to one scrape run per day.

### 3. Clean and validate the data

Only successful raw quote rows enter the cleaning pipeline. The pipeline:

1. Separates base fare from taxes and fees, estimating the split when a source provides only a total.
2. Removes duplicate observations while keeping the latest scrape.
3. Drops missing or invalid total fares while preserving optional missing flight details.
4. Flags statistical outliers using the interquartile range (IQR) rule.
5. Applies sanity bounds and records cleaning notes for adjustments.

Outliers remain visible in `clean_quotes` for auditability but are excluded from index calculations by default.

### 4. Calculate the daily index

The first day with clean data is the base period and is assigned an index value of 100. For every route and booking window, the system compares the day's average non-outlier fare with the corresponding average fare in the base period.

The three booking-window comparisons are averaged to create a route-level movement. Route movements are combined into the overall index using a weighted geometric mean. Since verified traffic-share weights are not bundled with this prototype, DEL-BOM and DEL-BLR use equal 50/50 weights.

Weekly and monthly values are display-time averages of daily index values; they are not separate scraping pipelines.

### 5. Serve and visualize the results

FastAPI exposes the calculated index, cleaned quotes, lead-time elasticity, and data-health status under `/api/v1`. The Streamlit dashboard consumes those endpoints for the Overview charts and also provides methodology, raw-data, and insights pages.

### 6. Back-test the trend

The dashboard compares APIx's monthly overall index with the official MoSPI domestic-airfare CPI series from `cpi_1059.xlsx`. Both series are aligned by month and independently rebased to 100 at the first overlapping month. The result is a trend comparison, not an exact level-to-level match, because the sources and base periods differ.

## Current scope

The prototype intentionally covers only two routes, two sources, and three advance-purchase windows. Return fares, additional airlines or OTAs, real-time streaming, production scheduling, authentication, CAPTCHA solving, and anti-bot evasion are outside the current scope.
