# PROJECT_BRIEF.md

## What this project is

APIx (Airfare Price Index) is a prototype system that automatically tracks
Indian domestic flight ticket prices and turns them into a single daily index
number, similar to how the Consumer Price Index (CPI) tracks inflation.

## Why it exists (background)

- India's official CPI (published by MoSPI/NSO) includes air travel fares
  under "Transport and Communication."
- Currently these fares are collected manually from a small set of outlets,
  which does not reflect real online, dynamic pricing.
- Over 90% of domestic air tickets are booked online, and prices for the same
  route can vary 200-400% in a single day depending on booking window, demand,
  and season.
- This project builds an automated system that scrapes real online fares,
  cleans the data, and computes a real-time airfare price index.

## Who would use the real version

- National Statistical Office (NSO) / Ministry of Statistics (MoSPI)
- Reserve Bank of India (RBI), for inflation-linked monetary policy decisions

## What this prototype must demonstrate (not the full production system)

1. A scraper that pulls real flight prices from at least one airline site and
   one OTA (Online Travel Aggregator).
2. A pipeline that cleans that raw price data.
3. A formula that turns cleaned prices into one index number per day.
4. A dashboard showing that index and related charts over time.
5. A basic back-test comparing our index trend against publicly available
   DGCA (Directorate General of Civil Aviation) average fare data.

## What this prototype does NOT need to do

- Does not need to cover all 5 airlines or all 6+ OTAs named in the original
  problem statement.
- Does not need CAPTCHA-solving, IP rotation, or any anti-bot evasion.
- Does not need weekly/monthly scraping pipelines separate from daily (these
  are just aggregations of daily data).

See SCOPE.md for the exact, locked-down scope for this build.
