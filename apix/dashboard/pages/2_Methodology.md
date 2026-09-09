# APIx Methodology

## What problem does APIx solve?

Official inflation statistics include air travel, but those fares are traditionally collected manually from a small number of outlets. That can miss the fast-changing prices people see online. More than 90% of domestic air tickets are booked online, and the same route can change by 200–400% in one day depending on demand, season, and how far ahead someone books.

APIx automatically collects online airfare, checks and cleans it, and turns it into one daily number. The goal is a more timely view of airfare inflation that could eventually help organisations such as the National Statistical Office, the Ministry of Statistics, and the Reserve Bank of India. This prototype demonstrates the approach; it is not an official inflation statistic.

## How is the index built?

The index starts at 100 on the first day for which clean fare data is available. Every later value shows how prices have changed compared with that starting point: a value of 110 means prices are about 10% higher, while 95 means they are about 5% lower.

For each route and booking window, APIx averages the usable fares collected that day. It compares that average with the same route and window in the base period. Outliers flagged by the cleaning pipeline are left out, so one unusual quote does not dominate the result.

The three booking windows—tomorrow, seven days ahead, and thirty days ahead—are averaged to produce one result for each route. The route results are then combined into the overall index. In a full version, routes would be weighted by their share of passenger traffic; in this prototype the two routes receive equal weight because verified traffic-share figures are not bundled with the build.

The dashboard's weekly and monthly figures are display-time averages of daily index values. They are not separate scraping or indexing systems.

## Which prices are collected?

APIx uses two sources:

- IndiGo, the direct airline website. The lowest available economy fare for the day is collected.
- Ixigo, an online travel aggregator. APIx uses the lowest IndiGo fare when available; otherwise it records the lowest fare shown and identifies the operating carrier.

Both sources are searched for the same routes and travel dates. The scraper records the fare components, total fare, flight details when available, and whether the search succeeded, found no results, found a sold-out flight, or failed.

## Ethical scraping rules

Before using a domain, APIx checks its `robots.txt`. If the requested path is disallowed, that source is skipped rather than scraped anyway.

Requests to the same domain are separated by at least three seconds, with a random delay of roughly three to six seconds. The scraper uses a descriptive research User-Agent instead of pretending to be a normal browser.

APIx does not solve CAPTCHAs or use proxy/IP rotation to evade detection. A route, source, and booking-window combination is scraped no more than once per day. Failed pages are logged and retried once after 30 seconds, then recorded as an error if they still fail.

## Current limitations

This prototype deliberately has a small, fixed scope:

- **2 routes:** DEL-BOM (Delhi–Mumbai) and DEL-BLR (Delhi–Bangalore), one direction only.
- **2 sources:** IndiGo and Ixigo. Other airlines and travel aggregators are not included yet.
- **3 booking windows:** T+1, T+7, and T+30. Other windows such as T+15 and T+45 are out of scope.

Scraping and indexing are daily processes. Weekly and monthly views are simple summaries of daily data, not independent pipelines. CAPTCHA solving, anti-bot evasion, real-time streaming, authentication, and a mobile app are also outside this prototype's scope.
