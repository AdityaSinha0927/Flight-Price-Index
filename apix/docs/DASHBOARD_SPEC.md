# DASHBOARD_SPEC.md

Framework: Streamlit, charts via Plotly. Pulls data from the FastAPI
endpoints defined in API_SPEC.md (or directly from the SQLite DB if simpler
for the prototype — note whichever approach is used in README.md).

## Page layout

### 1. Header

- Title: "APIx — Real-time Airfare Price Index"
- Subtitle showing the current overall index value and the date it was last
  updated, plus % change vs. the previous day.

### 2. Index trend chart

- Line chart of `index_value` over time.
- Toggle/selector for: overall ("ALL") vs. individual route (DEL-BOM,
  DEL-BLR).
- Toggle/selector for frequency: daily / weekly / monthly.
- Data source: `GET /api/v1/index`.

### 3. Sector-wise comparison (heatmap or bar chart)

- Compare the current index value across routes side by side.
- A heatmap is preferred if there are enough routes to make it visually
  useful; with only 2 routes in scope, a simple bar chart comparing
  route_relative values is acceptable and should be used instead if a
  heatmap looks sparse.
- Data source: `GET /api/v1/index` called once per route.

### 4. Lead-time elasticity chart

- Bar or line chart showing average total fare by advance-purchase window
  (T1, T7, T30) for a selected route.
- Route selector dropdown.
- Data source: `GET /api/v1/elasticity`.

### 5. Back-test comparison chart

- Load `cpi_1059.xlsx` and filter to `state = "All India"` and
  `sector = "Combined"`.
- Use the official MoSPI airfare CPI `index` series for January 2025 through
  July 2026. The workbook is base year 2024 = 100 and stores months by name.
- Fetch APIx's monthly-aggregated `ALL` index from
  `GET /api/v1/index?route=ALL&freq=monthly`.
- Align the MoSPI and APIx values on one year-month timeline using an outer
  join so each series remains visible across its full available range. If
  months overlap, independently rebase both series to 100 at the first
  overlapping month. If there is no overlap because official CPI publication
  lags the live APIx series, rebase each series from its own first available
  month.
- Plot both lines with clear labels such as `APIx monthly index (rebased)` and
  `MoSPI airfare CPI (rebased)`. Mark a non-overlapping interval with a
  visible gap annotation and caption it: `Official CPI data lags ~2 months
  behind real-time pricing — this gap is what APIx is designed to close.` The
  title/caption must state that this is a rebased trend comparison, not an
  exact index-level match.

### 6. Raw data table (optional, for transparency)

- Expandable table showing recent clean_quotes rows, with an `is_outlier`
  column visible, so judges can see the cleaning pipeline is doing real
  work and not hiding data.
- Data source: `GET /api/v1/quotes`.

## Non-functional

- Page should load with cached/last-known data even if a live scrape hasn't
  run recently (don't show a blank page on API failure — show the most
  recent successful data with a "last updated" timestamp).
- Keep it to a single page for the prototype; no need for multi-page
  navigation.
