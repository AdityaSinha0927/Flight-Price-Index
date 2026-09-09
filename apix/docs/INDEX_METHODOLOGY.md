# INDEX_METHODOLOGY.md

This is the exact formula to implement. Do not invent an alternative formula
— this mirrors how CPI-style indices are conventionally built (fixed basket,
price relatives, geometric mean), so it stays consistent with the DGCA
back-test comparison.

## Step 1 — Choose a base period

- Pick the first day for which clean_quotes data exists as the base period
  (`base_period`). All index values are relative to this day.
- Base period index value is defined as 100.

## Step 2 — Compute price relatives

For each route and advance_window on a given day `t`:

```
price_relative(route, window, t) = avg_total_fare(route, window, t)
                                    / avg_total_fare(route, window, base_period)
```

Where `avg_total_fare` is the average of `total_fare` across all non-outlier
`clean_quotes` rows for that route/window/day (across both sources).

## Step 3 — Aggregate across advance-purchase windows (per route)

For a given route on day `t`, take the simple average of the price relatives
across the 3 windows (T1, T7, T30):

```
route_relative(route, t) = mean of price_relative(route, window, t)
                            for window in [T1, T7, T30]
```

## Step 4 — Aggregate across routes into one overall index (weighted geometric mean)

```
overall_relative(t) = ( product over routes of
                         route_relative(route, t) ^ weight(route) )
```

Where `weight(route)` is the route's share of total passenger traffic from
DGCA data, normalized so weights across the routes in SCOPE.md sum to 1.
If exact DGCA traffic-share numbers are not available in the prototype
timeframe, use an equal weight (0.5 / 0.5 for the 2 routes in scope) and
document this as a simplification in README.md.

## Step 5 — Convert to index value

```
index_value(t) = 100 * overall_relative(t)
```

Store this as the row with `route = "ALL"` in `index_values` for day `t`.
Also store each individual `route_relative(route, t) * 100` as a per-route
row in `index_values` for the sector-wise breakdown used in the dashboard.

## Step 6 — Weekly / monthly aggregation (for display only)

- Weekly index value = simple average of daily `index_value` over that
  calendar week.
- Monthly index value = simple average of daily `index_value` over that
  calendar month.
- These are computed on the fly for display; they do not need their own
  table or pipeline.

## Back-testing against the official MoSPI CPI airfare series

- Load `cpi_1059.xlsx`, the official MoSPI CPI sub-index workbook.
- Filter rows where `state = "All India"` and `sector = "Combined"`.
- Use the domestic-airfare item (`item = "Airfare"`, code
  `07.3.3.1.2.01`) for January 2025 through July 2026. The workbook's
  `index` column is the official monthly airfare CPI index with base year
  2024 = 100.
- Fetch APIx's monthly-aggregated `ALL` series from
  `GET /api/v1/index?route=ALL&freq=monthly`.
- Align both series on a shared year-month timeline using an outer join so
  each series remains visible for its full available range. When months
  overlap, normalize each series independently to 100 at the first
  overlapping month:

  ```text
  rebased_value(t) = 100 * value(t) / value(first_overlapping_month)
  ```

- If there is no overlap because official CPI publication lags the APIx
  real-time series, normalize each series from its own first available month
  and mark the gap on the chart. Annotate it as: `Official CPI data lags ~2
  months behind real-time pricing — this gap is what APIx is designed to
  close.` Plot the two rebased series together as a visual trend comparison,
  not an exact level-to-level index match, because APIx and MoSPI have
  different source definitions and base periods.
