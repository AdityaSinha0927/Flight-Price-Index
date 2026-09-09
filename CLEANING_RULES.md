# CLEANING_RULES.md

Input: rows from `raw_quotes` where `scrape_status = "ok"`.
Output: validated rows written to `clean_quotes`.

## Step 1 — Fare decomposition (base fare vs. taxes)

- If the source site already separates base fare and taxes/fees, use those
  values directly.
- If only a total fare is available (no breakdown shown), estimate:
  `base_fare = total_fare / 1.18` and `taxes_and_fees = total_fare - base_fare`
  as a rough placeholder (18% approximates typical GST + fees), and set
  `cleaning_notes = "tax split estimated"` on that row.
- `total_fare` must always equal `base_fare + taxes_and_fees` after this step
  (recompute total_fare if needed to keep this consistent).

## Step 2 — Duplicate handling

- If two raw_quotes rows exist for the same (source, route, travel_date,
  advance_window) on the same search_date, keep only the one with the latest
  `scraped_at` timestamp; mark the discarded one with
  `cleaning_notes = "duplicate removed"` in the audit log (not inserted into
  clean_quotes).

## Step 3 — Missing value handling

- If `total_fare` is null or zero for an "ok" status row, drop the row from
  clean_quotes (do not guess a fare) and log it.
- If `flight_number` or `departure_time` is missing, keep the row (these are
  not required for the index) but leave the field null.

## Step 4 — Outlier detection

- Group clean candidate rows by (route, advance_window).
- Within each group, compute the median and the interquartile range (IQR) of
  `total_fare` across the last 14 days of data (or all available data if
  fewer than 14 days exist).
- Flag a row as an outlier (`is_outlier = 1`) if:
  `total_fare < Q1 - 1.5*IQR` or `total_fare > Q3 + 1.5*IQR`
- Outlier rows are still inserted into clean_quotes (do not delete them) but
  are excluded from the index calculation by default. This preserves
  auditability — a judge or reviewer can see what was excluded and why.

## Step 5 — Sanity bounds

- Discard (do not insert into clean_quotes) any row where `total_fare <= 0`
  or `total_fare > 200000` (INR) as a data-entry/scrape error, not a real
  outlier fare. Log these separately from statistical outliers.

## Output

Every row that survives Steps 1-5 is inserted into `clean_quotes` with
`raw_quote_id` linking back to its source row and `cleaning_notes` populated
whenever any adjustment was made.
