# Data storage rules

| Location | Contents | Tracked in Git? |
|---|---|---|
| `data/raw/` | Source responses exactly as retrieved (API JSON, downloaded files). Never edited. | No (directory marker only) |
| `data/interim/` | Cleaned and harmonised tables: units, periods, tags and currencies standardised. | No (directory marker only) |
| `data/processed/` | Analysis-ready Parquet tables that feed charts and the dashboard. | No (directory marker only) |
| `data/source_registry.csv` | Master catalogue linking every series to its source (lineage). | **Yes** |

## Rules

- Contents of `raw/`, `interim/` and `processed/` are reproducible outputs and are excluded from Git.
  Only the `.gitkeep` markers are tracked.
- Never commit API keys, licensed or paywalled data, or copyrighted reports.
- Every series used by a chart must have a row in `source_registry.csv`. Untraceable values are not
  charted.
- Missing values stay missing. They are never replaced with zero or filled without a documented rule.
- Nothing in this directory may contain synthetic or mock financial observations.
- Other HTTP response caches (`requests-cache`, used by non-SEC clients) are written to `.cache/`
  at the repository root, not here.

## Raw SEC responses

The raw store is also the SEC cache, so there is a single mechanism to reason about.

- Every response is written **verbatim** to
  `data/raw/sec/<kind>/<key>/<UTC timestamp>__<sha256 prefix>.<ext>`, with a
  `.meta.json` sidecar holding the URL, retrieval time (UTC), HTTP status, SHA-256 and size.
- Snapshots are append-only. A body that no longer matches its recorded checksum raises an error.
- A snapshot younger than 24 hours is reused instead of calling the SEC again. Older ones, or a
  forced refresh, fetch a new snapshot and keep the previous one. Filed documents never change, so
  a stored copy is reused indefinitely.
- The `User-Agent` sent to the SEC comes from the local `.env`. It is never stored in snapshots,
  metadata or logs.
- Kinds in use: `company_tickers`, `submissions`, `companyfacts`, `filings`.
