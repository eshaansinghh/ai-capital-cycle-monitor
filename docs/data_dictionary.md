# Data dictionary

The schemas in `src/ai_capital_cycle_monitor/schemas/` are the source of truth. This page
describes them in prose. Canonical financial-table fields are defined in Phase 2.

## Source registry (`data/source_registry.csv`)

One row per series-to-source lineage entry. Blank cells mean missing and are never coerced to
zero. Column order is fixed and enforced by the loader.

| Field | Type | Required | Description |
|---|---|---|---|
| `series_id` | text | yes | Key that data tables and charts use to reference this row. |
| `source_name` | text | yes | Publisher or system, for example the filing entity or API name. |
| `source_url` | text | yes | Exact URL of the filing, API endpoint or document. |
| `source_type` | enum | yes | See [source types](#source_type). |
| `retrieved_at_utc` | timestamp with timezone | no | When the data were retrieved. Naive timestamps are rejected. |
| `observation_date` | date | no | Date the value refers to (point-in-time series). |
| `period_start` | date | no | Start of the reporting period (flow series). |
| `period_end` | date | no | End of the reporting period. Must not precede `period_start`. |
| `filed_or_published_date` | date | no | Filing date or first publication date. |
| `fiscal_year` | integer | no | Company fiscal year. |
| `fiscal_quarter` | integer 1-4 | no | Company fiscal quarter. |
| `currency` | ISO 4217 code | no | Three uppercase letters, for example `USD`. |
| `unit` | text | no | Unit and scale, for example `USD millions` or `USD per GPU-hour`. |
| `reported_or_estimated` | enum | yes | See [data basis](#reported_or_estimated). |
| `transformation` | text | no | Any calculation applied between source and stored value. |
| `notes` | text | no | Caveats, definitions, quality remarks. |

### `source_type`

| Value | Meaning |
|---|---|
| `sec_filing` | SEC EDGAR filing or XBRL API. |
| `company_ir` | Company investor-relations material. |
| `official_statistics` | FRED/ALFRED, ECB or other official statistics. |
| `regulator` | Regulator, legislation or official policy release. |
| `peer_reviewed` | Peer-reviewed paper or recognised research organisation. |
| `newswire` | Established newswire, for example for dated private-company metrics. |
| `institutional_research` | Public institutional research page. |
| `specialist_dataset` | Transparent specialist dataset, for example GPU pricing. |
| `price_aggregator` | Aggregated price API, used only when necessary. |

### `reported_or_estimated`

| Value | Meaning |
|---|---|
| `reported` | Observed and stated by the source. |
| `company_guided` | Forward guidance issued by the company. |
| `consensus_estimated` | Third-party consensus estimate. |
| `derived` | Calculated by this project from reported values. |
| `scenario_modelled` | Produced by a scenario or interpolation with stated assumptions. |

## Configuration

| File | Schema | Content |
|---|---|---|
| `config/companies.yml` | `Company` | Identifiers, role, exchange, currency, filer type, CIK and fiscal calendar. No financial values. |
| `config/metrics.yml` | `MetricDefinition` | Metric id, formula, inputs, unit and undefined-case notes. |
| `config/events.yml` | `EventDefinition` | Event timestamp, source, exposed tickers, benchmarks, confounder log and status. |
