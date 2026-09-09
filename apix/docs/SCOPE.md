# SCOPE.md

This document is the single source of truth for what is IN and OUT of scope.
If any other document seems to imply something bigger, this file wins.

## Routes (city-pairs) — exactly 2

- DEL-BOM (Delhi to Mumbai)
- DEL-BLR (Delhi to Bangalore)

Both directions (return fares) are out of scope. Only the routes above, one
direction each, need to be scraped.

## Sources — exactly 2

- One airline website: IndiGo
- One OTA (Online Travel Aggregator): Ixigo

Do not add MakeMyTrip, Yatra, EaseMyTrip, Cleartrip, Goibibo, Air India, Air
India Express, Akasa Air, or SpiceJet in this version. The architecture should
make adding new sources easy later, but do not build them now.

## Advance-purchase windows — exactly 3

- T+1 (booking a flight for tomorrow)
- T+7 (booking a flight 7 days ahead)
- T+30 (booking a flight 30 days ahead)

Do not build T+15 or T+45 in this version.

## Frequency — daily only

- Only build the daily scrape and daily index.
- Weekly and monthly numbers are simple aggregations (e.g. average of daily
  values) computed on top of the daily data — do not build separate weekly or
  monthly scraping pipelines.

## Explicitly out of scope

- CAPTCHA solving
- IP rotation / proxy rotation for evading detection
- Any anti-bot evasion technique
- Real-time streaming (Kafka, etc.) — batch/scheduled scraping is enough
- User authentication or multi-user support on the dashboard
- Mobile app

## Definition of done for the prototype

- Scraper successfully pulls at least one real price for each of
  (2 routes) x (2 sources) x (3 windows) = 12 data points per day, for at
  least 3-5 consecutive days before the demo.
- Cleaning pipeline runs on that data without manual intervention.
- Index engine produces one index value per day.
- Dashboard shows: index trend line, a sector-wise comparison, and a
  lead-time elasticity chart (price vs. days-to-departure).
- A short back-test comparing the index trend to publicly available DGCA
  monthly average fare data for the same routes, even if only qualitative
  (do the trends move in the same direction).
