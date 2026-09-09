# TESTING.md

Use `pytest`. Tests live in `tests/`.

## Unit tests — cleaning pipeline (`test_cleaning.py`)

- Given a raw row with only `total_fare` set (no base/tax split), confirm
  the fare-decomposition step produces `base_fare + taxes_and_fees ==
  total_fare`.
- Given two raw rows that are exact duplicates (same source, route,
  travel_date, advance_window, search_date), confirm only one row makes it
  into clean_quotes.
- Given a raw row with `total_fare = 0`, confirm it is dropped, not inserted
  into clean_quotes.
- Given a set of fares where one value is far outside the IQR range,
  confirm it is flagged with `is_outlier = 1` but still present in
  clean_quotes (not deleted).
- Given a raw row with `total_fare = 500000`, confirm it is discarded as a
  sanity-bound violation, not merely flagged as an outlier.

## Unit tests — index engine (`test_index.py`)

- Given a known small set of clean_quotes (hand-constructed, e.g. 2 routes x
  3 windows x 2 days), manually compute the expected index_value for day 2
  and confirm the index engine produces the same number (within floating
  point tolerance).
- Confirm the base period always produces `index_value == 100.0` for every
  route and for "ALL".
- Confirm weekly and monthly aggregation functions return the simple average
  of the correct set of daily values.

## Integration test — scraper (manual, documented not automated)

- Because live scraping depends on external sites that can change layout or
  block requests, this is not run in CI. Instead, document in README.md:
  - the date scraping was last manually verified to work end-to-end
  - a screenshot or saved HTML snapshot of a successful scrape, kept in
    `tests/fixtures/`, used to test the *parsing* logic offline (this part
    CAN be automated: feed the saved HTML into the parser and confirm it
    extracts the expected fields).

## Back-test validation

- Not a pass/fail unit test, but a documented comparison (see
  INDEX_METHODOLOGY.md's back-testing section): our monthly index trend vs.
  DGCA's published average fare trend for the same routes/period, presented
  as a chart plus a short written note on how closely they track.

## Definition of "tests passing" for the demo

- All unit tests in `test_cleaning.py` and `test_index.py` pass.
- The offline parser test using a saved HTML fixture passes for both
  IndiGo and Ixigo.
- Manual end-to-end run completed at least once within 48 hours of the demo,
  with results shown in the dashboard.
