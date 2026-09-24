# AI Capital Cycle Monitor: Bubble, Buildout or Both?

A Python and Streamlit research platform testing whether AI-related market expectations are
supported by capital efficiency, free cash flow, adoption and infrastructure economics.

> **Status:** Phase 1 (foundations) built, pending review. There are no data pipelines, charts or
> findings yet.
> This is educational research, not investment advice.

## Research question

Are public markets pricing the AI capital cycle faster than cash flows, utilisation and
monetisation can justify, and where is the better risk-adjusted opportunity across US AI leaders,
AI infrastructure providers and European banks?

Hypotheses and definitions are frozen in [`docs/methodology.md`](docs/methodology.md) before any
analysis. Known data risks are tracked in [`docs/limitations.md`](docs/limitations.md).

## Principles

- Every displayed number traces to a source in [`data/source_registry.csv`](data/source_registry.csv)
  or an explicit formula.
- Observed, guided, estimated, derived and scenario-modelled values are never mixed.
- Missing is not zero. There is no mock or synthetic data in outputs.
- Secrets and licensed data never enter Git.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                      # create .venv and install locked dependencies
cp .env.example .env         # then edit .env with your own values (never committed)
uv run ruff check .          # lint
uv run pytest -q             # tests
```

`.env` needs an SEC EDGAR User-Agent (a real name and contact email, per the SEC fair-access
policy) and a free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html).

## Repository layout

```text
app/            Streamlit multi-page app (added in Phase 2)
config/         YAML: companies, metric definitions, events
data/           raw / interim / processed (untracked contents) and source_registry.csv
docs/           methodology, data dictionary, limitations, chart catalogue
references/     Harvard reference list and BibTeX
reports/        figures and the research report
src/ai_capital_cycle_monitor/
  clients/      source clients (SEC, FRED, prices)
  pipelines/    raw -> interim -> processed
  analysis/     ratios, FCF, relative value, reverse DCF, event study
  charts/       Plotly builders and theme
  schemas/      Pydantic models
  utils/        paths, config and registry loaders
tests/          pytest suite
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundations: tooling, config, schemas, docs, CI | Built, pending review |
| 2 | One-company vertical slice, reconciled to its filing | Next |
| 3 | Hyperscaler panel | Planned |
| 4 | European banks, relative value, reverse DCF | Planned |
| 5 | Compute economics: tokens, GPU prices, neoclouds | Planned |
| 6 | Event study | Planned |
| 7 | Publication: report, references, release | Planned |
