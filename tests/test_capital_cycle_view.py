"""Tests for the capital-cycle page's data preparation (structure-only synthetic fixtures)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_capital_cycle_monitor.pipelines.datasets import write_dataset
from ai_capital_cycle_monitor.pipelines.financials import build_company_dataset
from ai_capital_cycle_monitor.schemas.provenance import SourceRecord
from ai_capital_cycle_monitor.utils.registry import upsert_source_records
from ai_capital_cycle_monitor.views import capital_cycle as view_module
from ai_capital_cycle_monitor.views.capital_cycle import (
    TraceabilityError,
    check_counts,
    checks_needing_attention,
    display_table,
    latest_filings,
    latest_metrics,
    limit_quarters,
    load_capital_cycle_view,
)
from synthetic import COMPANY, MAPPINGS, SNAPSHOT, payload


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    (tmp_path / "source_registry.csv").write_text(
        ",".join(SourceRecord.model_fields) + "\n", encoding="utf-8"
    )
    dataset = build_company_dataset(COMPANY, MAPPINGS, payload(), SNAPSHOT)
    write_dataset(dataset, tmp_path)
    upsert_source_records(dataset.registry_records, tmp_path / "source_registry.csv")
    return tmp_path


def _load(data_dir: Path):
    return load_capital_cycle_view(data_dir, "TEST", companies=[COMPANY])


def test_unbuilt_dataset_gives_none(tmp_path: Path) -> None:
    assert load_capital_cycle_view(tmp_path, "TEST", companies=[COMPANY]) is None


def test_view_carries_note_lineage_and_latest_quarter_filings(data_dir: Path) -> None:
    view = _load(data_dir)
    assert view is not None
    assert view.company_name == "Test Co"
    assert view.note == (
        "Source: Test Co (2026) Forms 10-Q and 10-K; U.S. Securities and Exchange Commission "
        "(2026) XBRL Company Facts API; author's calculations. Data retrieved 02 January 2026."
    )
    assert view.retrieved_at == SNAPSHOT.retrieved_at_utc
    assert view.source_url == SNAPSHOT.url
    assert len(view.lineage) == 4
    assert view.quarterly["period_end"].is_monotonic_increasing
    assert set(view.filings["field"]) == {"revenue", "operating_cash_flow", "cash_capex"}
    assert view.filings["filing"].str.contains("/Archives/edgar/data/").all()


def test_missing_registry_series_withholds_the_view(data_dir: Path) -> None:
    registry = data_dir / "source_registry.csv"
    lines = registry.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if "base_fcf" not in line]
    registry.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with pytest.raises(TraceabilityError, match="base_fcf"):
        _load(data_dir)


def test_missing_checks_table_withholds_the_view(data_dir: Path) -> None:
    (data_dir / "processed" / "test_checks.parquet").unlink()
    with pytest.raises(TraceabilityError, match="checks table"):
        _load(data_dir)


def _two_years() -> pd.DataFrame:
    rows = []
    for fiscal_year, scale in ((2024, 1), (2025, 2)):
        for quarter in (1, 2, 3, 4):
            rows.append(
                {
                    "fiscal_year": fiscal_year,
                    "fiscal_quarter": quarter,
                    "fiscal_label": f"FY{fiscal_year % 100} Q{quarter}",
                    "period_end": pd.Timestamp(fiscal_year - 1, 3 * quarter + 6, 28)
                    if quarter < 3
                    else pd.Timestamp(fiscal_year, 3 * quarter - 6, 28),
                    "operating_cash_flow": pd.NA
                    if (fiscal_year, quarter) == (2025, 3)
                    else 40 * scale * 10**9,
                    "cash_capex": 10 * scale * 10**9,
                    "base_fcf": 30 * scale * 10**9,
                    "operating_cash_flow_basis": "derived",
                    "cash_capex_basis": "derived",
                    "base_fcf_basis": "derived",
                    "revenue": 100 * 10**9,
                    "revenue_basis": "reported",
                }
            )
    frame = pd.DataFrame(rows)
    for column in ("operating_cash_flow", "cash_capex", "base_fcf", "revenue"):
        frame[column] = frame[column].astype("Int64")
    frame["operating_cash_flow_basis"] = frame["operating_cash_flow_basis"].where(
        frame["operating_cash_flow"].notna()
    )
    return frame


def test_limit_quarters_keeps_the_latest_n_or_all() -> None:
    frame = _two_years()
    assert len(limit_quarters(frame, 3)) == 3
    assert limit_quarters(frame, 3)["period_end"].is_monotonic_increasing
    assert len(limit_quarters(frame, None)) == 8


def test_latest_metrics_compare_with_the_same_quarter_a_year_earlier() -> None:
    frame = _two_years()
    label, _, metrics = latest_metrics(frame)
    latest = {m.label: m for m in metrics}
    assert label == frame.sort_values("period_end")["fiscal_label"].iloc[-1]
    assert latest["Capital expenditure"].value_bn == pytest.approx(20)
    assert latest["Capital expenditure"].year_ago_change == pytest.approx(1.0)
    assert latest["Capital expenditure"].basis == "derived"


def test_latest_metric_that_is_missing_stays_missing() -> None:
    frame = _two_years()
    latest_period = frame["period_end"].max()
    frame.loc[frame["period_end"] == latest_period, "cash_capex"] = pd.NA
    frame.loc[frame["period_end"] == latest_period, "cash_capex_basis"] = pd.NA
    _, _, metrics = latest_metrics(frame)
    capex = next(m for m in metrics if m.label == "Capital expenditure")
    assert (capex.value_bn, capex.year_ago_change, capex.basis) == (None, None, None)


def test_display_table_is_newest_first_in_millions_with_basis_and_missing() -> None:
    table = display_table(_two_years())
    assert table["Period end"].is_monotonic_decreasing
    assert table["Capex (USD m)"].iloc[0] == 20_000
    missing = table[table["Operating cash flow (USD m)"].isna()]
    assert list(missing["Operating cash flow basis"]) == ["missing"]


def test_latest_filings_expands_component_facts_with_links() -> None:
    long = pd.DataFrame(
        {
            "fiscal_year": [2025, 2025],
            "fiscal_quarter": [4, 3],
            "field": ["revenue", "revenue"],
            "components": [
                json.dumps(
                    [
                        {
                            "tag": "T",
                            "form": "10-K",
                            "filed": "2025-08-01",
                            "start": "2024-07-01",
                            "end": "2025-06-30",
                            "value": 5,
                            "filing_index_url": "https://example.com/index",
                        }
                    ]
                ),
                "[]",
            ],
        }
    )
    filings = latest_filings(long, 2025, 4)
    assert filings["filing"].tolist() == ["https://example.com/index"]
    assert latest_filings(None, 2025, 4).empty


def test_check_counts_and_attention_rows() -> None:
    checks = pd.DataFrame(
        {
            "status": ["pass", "warn", "fail", "skipped", "pass"],
            "check": list("abcde"),
            "field": "f",
            "fiscal_year": 2025,
            "fiscal_quarter": 1,
            "detail": "d",
        }
    )
    assert check_counts(checks) == {"pass": 2, "warn": 1, "fail": 1, "skipped": 1}
    assert checks_needing_attention(checks)["check"].tolist() == ["b", "c"]


def test_default_ticker_is_microsoft_only_in_phase_two() -> None:
    assert view_module.DEFAULT_TICKER == "MSFT"
