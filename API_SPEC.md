# API_SPEC.md

Framework: FastAPI. Base path: `/api/v1`.

## GET /api/v1/index

Returns index values over time.

**Query params:**
- `route` (optional, e.g. "DEL-BOM" or "ALL"; default "ALL")
- `freq` (optional: "daily" | "weekly" | "monthly"; default "daily")
- `start_date` (optional, ISO date)
- `end_date` (optional, ISO date)

**Response:**
```json
{
  "route": "ALL",
  "freq": "daily",
  "base_period": "2026-08-01",
  "data": [
    { "date": "2026-08-01", "index_value": 100.0 },
    { "date": "2026-08-02", "index_value": 101.3 }
  ]
}
```

## GET /api/v1/quotes

Returns cleaned raw quotes (for transparency / debugging / heatmap data).

**Query params:**
- `route` (optional)
- `advance_window` (optional: "T1" | "T7" | "T30")
- `start_date`, `end_date` (optional)

**Response:**
```json
{
  "data": [
    {
      "source": "indigo",
      "route": "DEL-BOM",
      "travel_date": "2026-09-10",
      "advance_window": "T7",
      "total_fare": 5400,
      "is_outlier": false
    }
  ]
}
```

## GET /api/v1/elasticity

Returns average fare by advance-purchase window, per route — the data
needed for the lead-time elasticity chart.

**Query params:**
- `route` (required)

**Response:**
```json
{
  "route": "DEL-BOM",
  "data": [
    { "advance_window": "T1", "avg_total_fare": 8200 },
    { "advance_window": "T7", "avg_total_fare": 6100 },
    { "advance_window": "T30", "avg_total_fare": 4300 }
  ]
}
```

## GET /api/v1/health

Simple health check.

**Response:**
```json
{ "status": "ok", "last_scrape_at": "2026-09-08T06:00:00Z" }
```

## General rules

- All dates are ISO 8601 (`YYYY-MM-DD`).
- All errors return standard FastAPI HTTPException JSON with a clear
  `detail` message.
- Auto-generate OpenAPI docs at `/docs` (FastAPI does this by default — do
  not disable it).
