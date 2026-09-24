"""Microsoft reconciliation tests on real SEC data.

The fixture is a verbatim subset of Microsoft's actual Company Facts (see
tests/fixtures/msft_companyfacts_subset.provenance.json for its source, retrieval time and
checksum). The expected values below were read from the printed statements in Microsoft's own
filings, so they are an independent reference and not derived from the same XBRL facts. All figures
are USD millions as printed.

Printed sources (Income Statements and Cash Flows Statements):
  Q1 10-Q  filed 2025-10-29, accession 0001193125-25-256321 (three months ended 30 Sep 2025)
  Q3 10-Q  filed 2026-04-29, accession 0001193125-26-191507 (3 and 9 months ended 31 Mar 2026)
  10-K     filed 2026-07-29, accession 0001193125-26-323660 (years ended 30 June 2026, 2025, 2024)
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from ai_capital_cycle_monitor.clients.raw_store import Snapshot
from ai_capital_cycle_monitor.pipelines.financials import CompanyDataset, build_company_dataset
from ai_capital_cycle_monitor.utils.config import load_companies, load_xbrl_mappings

FIXTURES = Path(__file__).parent / "fixtures"
MILLION = 1_000_000

# (revenue, operating cash flow, capex) as printed, USD millions.
PRINTED_QUARTERS = {
    (2026, 1): (77_673, 45_057, 19_394),  # Q1 10-Q, three months ended 30 Sep 2025
    (2025, 1): (65_585, None, None),  # comparative in the Q1 10-Q
    (2026, 3): (82_886, 46_679, 30_876),  # Q3 10-Q, three months ended 31 Mar 2026
    (2025, 3): (70_066, 37_044, 16_745),  # comparative in the Q3 10-Q
}
PRINTED_NINE_MONTHS_FY26 = (241_832, 127_494, 80_146)  # Q3 10-Q, nine months ended 31 Mar 2026
PRINTED_NINE_MONTHS_FY25_CAPEX = 47_472  # comparative in the Q3 10-Q
PRINTED_YEARS = {  # 10-K, years ended 30 June
    2026: (331_839, 182_935, 115_948),
    2025: (281_724, 136_162, 64_551),
    2024: (245_122, 118_548, 44_477),
}


@pytest.fixture(scope="module")
def dataset() -> CompanyDataset:
    facts = json.loads((FIXTURES / "msft_companyfacts_subset.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (FIXTURES / "msft_companyfacts_subset.provenance.json").read_text(encoding="utf-8")
    )
    snapshot = Snapshot(
        path=Path("unused"),
        url=provenance["source_url"],
        retrieved_at_utc=datetime.fromisoformat(provenance["retrieved_at_utc"]),
        http_status=200,
        sha256=provenance["source_sha256"],
        size_bytes=provenance["source_size_bytes"],
    )
    company = next(c for c in load_companies() if c.ticker == "MSFT")
    return build_company_dataset(company, load_xbrl_mappings()["MSFT"], facts, snapshot)


def _row(dataset: CompanyDataset, fiscal_year: int, fiscal_quarter: int) -> pd.Series:
    quarterly = dataset.quarterly
    match = quarterly[
        (quarterly["fiscal_year"] == fiscal_year) & (quarterly["fiscal_quarter"] == fiscal_quarter)
    ]
    assert len(match) == 1
    return match.iloc[0]


def _millions(value: object) -> int:
    return int(value) // MILLION  # type: ignore[call-overload]


def test_history_runs_fiscal_2018_to_2026_with_no_missing_quarters(dataset: CompanyDataset) -> None:
    quarterly = dataset.quarterly
    assert len(quarterly) == 36
    assert quarterly["fiscal_label"].iloc[0] == "FY18 Q1"
    assert quarterly["fiscal_label"].iloc[-1] == "FY26 Q4"
    for column in ("revenue", "operating_cash_flow", "cash_capex", "base_fcf"):
        assert quarterly[column].notna().all(), column


@pytest.mark.parametrize(("period", "printed"), PRINTED_QUARTERS.items())
def test_reported_quarters_match_the_printed_statements(
    dataset: CompanyDataset, period: tuple[int, int], printed: tuple[int, int | None, int | None]
) -> None:
    row = _row(dataset, *period)
    for column, expected in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), printed, strict=True
    ):
        if expected is not None:
            assert _millions(row[column]) == expected, (period, column)
            assert row[f"{column}_basis"] == "reported"


def test_derived_fourth_quarter_equals_printed_year_minus_printed_nine_months(
    dataset: CompanyDataset,
) -> None:
    row = _row(dataset, 2026, 4)
    expected = [
        year - nine
        for year, nine in zip(PRINTED_YEARS[2026], PRINTED_NINE_MONTHS_FY26, strict=True)
    ]
    assert expected == [90_007, 55_441, 35_802]
    for column, value in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), expected, strict=True
    ):
        assert _millions(row[column]) == value
        assert row[f"{column}_basis"] == "derived"
    assert _millions(row["base_fcf"]) == 55_441 - 35_802 == 19_639


def test_base_fcf_is_operating_cash_flow_minus_capex_for_every_quarter(
    dataset: CompanyDataset,
) -> None:
    quarterly = dataset.quarterly
    assert (
        quarterly["base_fcf"] == quarterly["operating_cash_flow"] - quarterly["cash_capex"]
    ).all()


@pytest.mark.parametrize("fiscal_year", sorted(PRINTED_YEARS))
def test_four_quarters_sum_to_the_printed_fiscal_year(
    dataset: CompanyDataset, fiscal_year: int
) -> None:
    year = dataset.quarterly[dataset.quarterly["fiscal_year"] == fiscal_year]
    assert len(year) == 4
    for column, printed in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), PRINTED_YEARS[fiscal_year], strict=True
    ):
        assert _millions(year[column].sum()) == printed, (fiscal_year, column)


def test_first_three_quarters_sum_to_the_printed_nine_months(dataset: CompanyDataset) -> None:
    nine = dataset.quarterly[
        (dataset.quarterly["fiscal_year"] == 2026) & (dataset.quarterly["fiscal_quarter"] <= 3)
    ]
    for column, printed in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), PRINTED_NINE_MONTHS_FY26, strict=True
    ):
        assert _millions(nine[column].sum()) == printed
    fy25 = dataset.quarterly[
        (dataset.quarterly["fiscal_year"] == 2025) & (dataset.quarterly["fiscal_quarter"] <= 3)
    ]
    assert _millions(fy25["cash_capex"].sum()) == PRINTED_NINE_MONTHS_FY25_CAPEX


def test_derived_quarter_cites_the_two_filings_it_came_from(dataset: CompanyDataset) -> None:
    long = dataset.long
    row = long[
        (long["field"] == "cash_capex")
        & (long["fiscal_year"] == 2026)
        & (long["fiscal_quarter"] == 4)
    ].iloc[0]
    components = json.loads(row["components"])
    assert {(c["form"], c["accession"]) for c in components} == {
        ("10-K", "0001193125-26-323660"),
        ("10-Q", "0001193125-26-191507"),
    }
    assert {c["end"] for c in components} == {"2026-06-30", "2026-03-31"}
    assert all(
        c["filing_index_url"].startswith("https://www.sec.gov/Archives/edgar/data/789019/")
        for c in components
    )
    assert row["transformation"] == "twelve-month year-to-date minus nine-month year-to-date"
    assert row["tags"] == "PaymentsToAcquirePropertyPlantAndEquipment"


def test_revenue_uses_one_tag_throughout_the_window(dataset: CompanyDataset) -> None:
    revenue = dataset.long[dataset.long["field"] == "revenue"]
    assert set(revenue["tags"]) == {"RevenueFromContractWithCustomerExcludingAssessedTax"}


def test_fourth_quarters_are_derived_from_fiscal_2021_and_reported_before(
    dataset: CompanyDataset,
) -> None:
    q4 = dataset.quarterly[dataset.quarterly["fiscal_quarter"] == 4].set_index("fiscal_year")
    assert all(q4.loc[year, "revenue_basis"] == "reported" for year in (2018, 2019, 2020))
    assert all(q4.loc[year, "revenue_basis"] == "derived" for year in range(2021, 2027))
    assert all(q4.loc[year, "cash_capex_basis"] == "derived" for year in range(2018, 2027))


def test_every_automated_check_passes_on_the_real_data(dataset: CompanyDataset) -> None:
    assert set(dataset.checks["status"]) <= {"pass", "skipped"}
    assert (dataset.checks["check"] == "quarters_sum_to_year").sum() == 3


def test_registry_rows_cover_the_four_series(dataset: CompanyDataset) -> None:
    assert {r.series_id for r in dataset.registry_records} == {
        f"sec_xbrl.msft.{name}.quarterly"
        for name in ("revenue", "operating_cash_flow", "cash_capex", "base_fcf")
    }
