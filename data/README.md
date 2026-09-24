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
- HTTP response caches (`requests-cache`) are written to `.cache/` at the repository root, not here.
