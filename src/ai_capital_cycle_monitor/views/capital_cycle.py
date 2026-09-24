"""Prepare the capital-cycle page data: load it, prove it is traceable, format it for display."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from ai_capital_cycle_monitor.charts.capital_cycle import source_note
from ai_capital_cycle_monitor.pipelines.build import find_company
from ai_capital_cycle_monitor.pipelines.datasets import read_checks, read_long, read_quarterly
from ai_capital_cycle_monitor.pipelines.financials import series_id
from ai_capital_cycle_monitor.schemas.config import Company
from ai_capital_cycle_monitor.utils.registry import load_source_registry

DEFAULT_TICKER = "MSFT"  # Phase 2 builds Microsoft only
CHART_FIELDS = ("revenue", "operating_cash_flow", "cash_capex", "base_fcf")
MILLION = 1e6
BILLION = 1e9


class TraceabilityError(RuntimeError):
    """A displayed series has no row in the source registry, so it must not be shown."""


@dataclass(frozen=True)
class CapitalCycleView:
    ticker: str
    company_name: str
    quarterly: pd.DataFrame
    checks: pd.DataFrame
    lineage: pd.DataFrame
    filings: pd.DataFrame
    source_url: str
    retrieved_at: datetime
    note: str


@dataclass(frozen=True)
class Metric:
    """Latest value in USD billions with its change against the same quarter a year earlier."""

    label: str
    value_bn: float | None
    year_ago_change: float | None
    basis: str | None


def _billions(value: object) -> float | None:
    return None if pd.isna(value) else float(value) / BILLION


def registered_series(ticker: str, registry_path: Path) -> pd.DataFrame:
    """Registry rows behind the chart, or raise if any displayed series is not registered."""
    records = {record.series_id: record for record in load_source_registry(registry_path)}
    expected = [series_id(ticker, field) for field in CHART_FIELDS]
    missing = [name for name in expected if name not in records]
    if missing:
        raise TraceabilityError(
            "these series are not in data/source_registry.csv, so they are not shown: "
            + ", ".join(missing)
        )
    return pd.DataFrame(
        {
            "series": [records[name].series_id for name in expected],
            "basis": [records[name].reported_or_estimated.value for name in expected],
            "unit": [records[name].unit for name in expected],
            "period start": [records[name].period_start for name in expected],
            "period end": [records[name].period_end for name in expected],
            "latest filing date": [records[name].filed_or_published_date for name in expected],
            "retrieved (UTC)": [records[name].retrieved_at_utc for name in expected],
            "source": [records[name].source_url for name in expected],
            "notes": [records[name].notes for name in expected],
        }
    )


def latest_filings(
    long: pd.DataFrame | None, fiscal_year: int, fiscal_quarter: int
) -> pd.DataFrame:
    """The SEC facts behind the latest quarter, with links to the filings they came from."""
    columns = [
        "field",
        "tag",
        "form",
        "filed",
        "period start",
        "period end",
        "value (USD)",
        "filing",
    ]
    if long is None:
        return pd.DataFrame(columns=columns)
    rows = []
    selected = long[
        (long["fiscal_year"] == fiscal_year) & (long["fiscal_quarter"] == fiscal_quarter)
    ]
    for _, row in selected.iterrows():
        for component in json.loads(row["components"]):
            rows.append(
                {
                    "field": row["field"],
                    "tag": component["tag"],
                    "form": component["form"],
                    "filed": component["filed"],
                    "period start": component["start"],
                    "period end": component["end"],
                    "value (USD)": component["value"],
                    "filing": component["filing_index_url"],
                }
            )
    return pd.DataFrame(rows, columns=columns)


def load_capital_cycle_view(
    data_dir: Path, ticker: str, companies: list[Company] | None = None
) -> CapitalCycleView | None:
    """Load the built dataset, or None if it has not been built yet.

    Raises TraceabilityError when a charted series is missing from the source registry.
    """
    quarterly = read_quarterly(data_dir, ticker)
    if quarterly is None:
        return None
    checks = read_checks(data_dir, ticker)
    if checks is None:
        raise TraceabilityError(f"the checks table for {ticker} is missing; rebuild the dataset")
    lineage = registered_series(ticker, data_dir / "source_registry.csv")
    company = find_company(ticker, companies)

    quarterly = quarterly.sort_values("period_end", ignore_index=True)
    retrieved = quarterly["source_retrieved_at_utc"].iloc[0].to_pydatetime()
    year = retrieved.year
    note = source_note(
        f"{company.name} ({year}) Forms 10-Q and 10-K; U.S. Securities and Exchange Commission "
        f"({year}) XBRL Company Facts API",
        retrieved.date(),
    )
    latest = quarterly.iloc[-1]
    filings = latest_filings(
        read_long(data_dir, ticker), int(latest["fiscal_year"]), int(latest["fiscal_quarter"])
    )
    return CapitalCycleView(
        ticker=ticker,
        company_name=company.name,
        quarterly=quarterly,
        checks=checks,
        lineage=lineage,
        filings=filings,
        source_url=str(quarterly["source_url"].iloc[0]),
        retrieved_at=retrieved,
        note=note,
    )


def limit_quarters(quarterly: pd.DataFrame, count: int | None) -> pd.DataFrame:
    """The latest `count` quarters by period end, or all of them when count is None."""
    ordered = quarterly.sort_values("period_end")
    return ordered if count is None else ordered.tail(count)


def latest_metrics(quarterly: pd.DataFrame) -> tuple[str, date, list[Metric]]:
    """Latest-quarter capex, operating cash flow and base FCF, each against a year earlier."""
    ordered = quarterly.sort_values("period_end", ignore_index=True)
    latest = ordered.iloc[-1]
    year_ago = ordered[
        (ordered["fiscal_year"] == latest["fiscal_year"] - 1)
        & (ordered["fiscal_quarter"] == latest["fiscal_quarter"])
    ]
    metrics = []
    for label, column in (
        ("Capital expenditure", "cash_capex"),
        ("Operating cash flow", "operating_cash_flow"),
        ("Base free cash flow", "base_fcf"),
    ):
        current = _billions(latest[column])
        prior = _billions(year_ago[column].iloc[0]) if not year_ago.empty else None
        change = current / prior - 1 if current is not None and prior else None
        basis = latest[f"{column}_basis"]
        metrics.append(Metric(label, current, change, None if pd.isna(basis) else str(basis)))
    return str(latest["fiscal_label"]), latest["period_end"].date(), metrics


def display_table(quarterly: pd.DataFrame) -> pd.DataFrame:
    """Quarterly table in USD millions, newest first, with the basis of every value."""
    frame = quarterly.sort_values("period_end", ascending=False)
    table = pd.DataFrame(
        {
            "Fiscal quarter": frame["fiscal_label"],
            "Period end": frame["period_end"].dt.date,
        }
    )
    for title, column in (
        ("Revenue", "revenue"),
        ("Operating cash flow", "operating_cash_flow"),
        ("Capex", "cash_capex"),
        ("Base FCF", "base_fcf"),
    ):
        table[f"{title} (USD m)"] = frame[column].astype("Float64") / MILLION
        table[f"{title} basis"] = frame[f"{column}_basis"].astype(object).fillna("missing")
    return table.reset_index(drop=True)


def check_counts(checks: pd.DataFrame) -> dict[str, int]:
    counts = checks["status"].value_counts()
    return {status: int(counts.get(status, 0)) for status in ("pass", "warn", "fail", "skipped")}


def checks_needing_attention(checks: pd.DataFrame) -> pd.DataFrame:
    flagged = checks[checks["status"].isin(["warn", "fail"])]
    return flagged[["status", "check", "field", "fiscal_year", "fiscal_quarter", "detail"]]
