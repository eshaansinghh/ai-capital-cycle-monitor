"""Helpers for offline reconciliation tests built on verbatim real SEC data.

Each company has tests/fixtures/<ticker>_companyfacts_subset.json (verbatim Company Facts entries)
and a provenance file recording its source, retrieval time and checksum. The dataset is built with
the company's real committed mapping and lease treatment, so these tests fail if either changes.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from ai_capital_cycle_monitor.clients.raw_store import Snapshot
from ai_capital_cycle_monitor.pipelines.financials import CompanyDataset, build_company_dataset
from ai_capital_cycle_monitor.utils.config import (
    load_companies,
    load_lease_adjustments,
    load_xbrl_mappings,
)

FIXTURES = Path(__file__).parent / "fixtures"
MILLION = 1_000_000


def build_real_dataset(ticker: str) -> CompanyDataset:
    stem = f"{ticker.lower()}_companyfacts_subset"
    facts = json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))
    provenance = json.loads((FIXTURES / f"{stem}.provenance.json").read_text(encoding="utf-8"))
    snapshot = Snapshot(
        path=Path("unused"),
        url=provenance["source_url"],
        retrieved_at_utc=datetime.fromisoformat(provenance["retrieved_at_utc"]),
        http_status=200,
        sha256=provenance["source_sha256"],
        size_bytes=provenance["source_size_bytes"],
    )
    company = next(c for c in load_companies() if c.ticker == ticker)
    return build_company_dataset(
        company,
        load_xbrl_mappings()[ticker],
        facts,
        snapshot,
        lease=load_lease_adjustments().get(ticker),
    )


def row(dataset: CompanyDataset, fiscal_year: int, fiscal_quarter: int) -> pd.Series:
    quarterly = dataset.quarterly
    match = quarterly[
        (quarterly["fiscal_year"] == fiscal_year) & (quarterly["fiscal_quarter"] == fiscal_quarter)
    ]
    assert len(match) == 1, (fiscal_year, fiscal_quarter)
    return match.iloc[0]


def millions(value: object) -> int:
    """A stored USD amount as whole millions (statements print in millions)."""
    return int(value) // MILLION  # type: ignore[call-overload]


def year_sum(dataset: CompanyDataset, fiscal_year: int, column: str, *, through: int = 4) -> int:
    quarterly = dataset.quarterly
    part = quarterly[
        (quarterly["fiscal_year"] == fiscal_year) & (quarterly["fiscal_quarter"] <= through)
    ]
    return millions(part[column].sum())
