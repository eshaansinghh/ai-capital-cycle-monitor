"""Alphabet reconciliation tests on real SEC data.

The fixture is a verbatim subset of Alphabet's actual Company Facts (provenance in
tests/fixtures/googl_companyfacts_subset.provenance.json). Expected values were read from the
printed statements in Alphabet's own filings, so they are an independent reference. USD millions.

Printed sources:
  10-K  filed 2026-02-05  accession 0001652044-26-000018  (years ended 31 Dec 2023, 2024, 2025)
  10-Q  filed 2025-10-30  accession 0001652044-25-000091  (three and nine months ended 30 Sep 2025)
  10-Q  filed 2026-04-30  accession 0001652044-26-000048  (three months ended 31 Mar 2026)
  10-Q  filed 2026-07-23  accession 0001652044-26-000071  (three and six months ended 30 Jun 2026)

Alphabet's cash-flow statements are cumulative, so cash-flow quarters after Q1 are differences.
"""

import json

import pytest

from ai_capital_cycle_monitor.pipelines.financials import CompanyDataset
from real_data import build_real_dataset, millions, row, year_sum

# (revenue, operating cash flow, capex) for three-month periods as printed or, where the filing
# prints only year-to-date cash flows, as the difference of two printed year-to-date figures.
PRINTED_Q1 = {2026: (109_896, 45_790, 35_674), 2025: (90_234, 36_150, 17_197)}  # Q1 2026 10-Q
PRINTED_SIX_MONTHS_2026 = (229_692, 84_859, 80_598)  # Q2 2026 10-Q, six months
PRINTED_NINE_MONTHS_2025 = (289_007, 112_311, 63_596)  # Q3 2025 10-Q, nine months
PRINTED_YEARS = {  # 10-K
    2025: (402_836, 164_713, 91_447),
    2024: (350_018, 125_299, 52_535),
    2023: (307_394, 101_746, 32_251),
}
PRINTED_REVENUE_3M = {(2026, 2): 119_796, (2025, 2): 96_428, (2025, 3): 102_346}

# Lease note: (financing cash flows used for finance leases, finance-lease assets obtained).
PRINTED_LEASE_3M = {
    (2026, 1): (522, 211),
    (2025, 1): (192, 523),
    (2026, 2): (318, 691),
    (2025, 2): (110, 83),
    (2025, 3): (92, 383),
}
PRINTED_LEASE_SIX_MONTHS_2026 = (840, 902)
PRINTED_LEASE_NINE_MONTHS_2025 = (394, 989)
PRINTED_LEASE_YEARS = {2025: (1_988, 1_606), 2024: (405, 313)}


@pytest.fixture(scope="module")
def dataset() -> CompanyDataset:
    return build_real_dataset("GOOGL")


def test_history_starts_when_topic_606_applies_and_has_no_gaps(dataset: CompanyDataset) -> None:
    quarterly = dataset.quarterly
    assert quarterly["fiscal_label"].iloc[0] == "FY17 Q1"
    assert quarterly["fiscal_label"].iloc[-1] == "FY26 Q2"
    assert len(quarterly) == 38
    for column in ("revenue", "operating_cash_flow", "cash_capex", "base_fcf"):
        assert quarterly[column].notna().all(), column


@pytest.mark.parametrize("year", sorted(PRINTED_Q1))
def test_first_quarters_match_the_printed_statements(dataset: CompanyDataset, year: int) -> None:
    r = row(dataset, year, 1)
    revenue, ocf, capex = PRINTED_Q1[year]
    assert millions(r["revenue"]) == revenue
    assert millions(r["operating_cash_flow"]) == ocf
    assert millions(r["cash_capex"]) == capex
    assert r["operating_cash_flow_basis"] == "reported"  # Q1 year-to-date is the three-month figure


@pytest.mark.parametrize(("period", "printed"), PRINTED_REVENUE_3M.items())
def test_reported_three_month_revenue_matches_the_printed_income_statement(
    dataset: CompanyDataset, period: tuple[int, int], printed: int
) -> None:
    r = row(dataset, *period)
    assert millions(r["revenue"]) == printed
    assert r["revenue_basis"] == "reported"


def test_second_quarter_cash_flows_are_derived_from_two_printed_year_to_date_figures(
    dataset: CompanyDataset,
) -> None:
    r = row(dataset, 2026, 2)
    assert millions(r["operating_cash_flow"]) == PRINTED_SIX_MONTHS_2026[1] - PRINTED_Q1[2026][1]
    assert millions(r["operating_cash_flow"]) == 39_069
    assert millions(r["cash_capex"]) == PRINTED_SIX_MONTHS_2026[2] - PRINTED_Q1[2026][2] == 44_924
    assert r["operating_cash_flow_basis"] == r["cash_capex_basis"] == "derived"
    assert millions(r["base_fcf"]) == 39_069 - 44_924 == -5_855  # negative: capex above cash flow


def test_fourth_quarter_is_the_printed_year_minus_the_printed_nine_months(
    dataset: CompanyDataset,
) -> None:
    r = row(dataset, 2025, 4)
    expected = [y - n for y, n in zip(PRINTED_YEARS[2025], PRINTED_NINE_MONTHS_2025, strict=True)]
    assert expected == [113_829, 52_402, 27_851]
    for column, value in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), expected, strict=True
    ):
        assert millions(r[column]) == value
        assert r[f"{column}_basis"] == "derived"
    assert millions(r["base_fcf"]) == 52_402 - 27_851 == 24_551


@pytest.mark.parametrize("year", sorted(PRINTED_YEARS))
def test_four_quarters_agree_with_the_printed_year_to_within_rounding(
    dataset: CompanyDataset, year: int
) -> None:
    for column, printed in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), PRINTED_YEARS[year], strict=True
    ):
        assert abs(year_sum(dataset, year, column) - printed) <= 2, (year, column)


def test_the_one_million_revenue_rounding_difference_is_recorded_not_hidden(
    dataset: CompanyDataset,
) -> None:
    assert year_sum(dataset, 2025, "revenue") == 402_837  # quarters, each rounded to a million
    checks = dataset.checks
    sums = checks[(checks["check"] == "quarters_sum_to_year") & (checks["field"] == "revenue")]
    assert sums.iloc[0]["status"] == "pass"
    assert "differ by rounding only" in sums.iloc[0]["detail"]
    assert "FY25 1" in sums.iloc[0]["detail"]


def test_nine_months_of_printed_cash_flows_sum_from_the_quarters(dataset: CompanyDataset) -> None:
    for column, printed in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), PRINTED_NINE_MONTHS_2025, strict=True
    ):
        assert abs(year_sum(dataset, 2025, column, through=3) - printed) <= 2
    for column, printed in zip(
        ("revenue", "operating_cash_flow", "cash_capex"), PRINTED_SIX_MONTHS_2026, strict=True
    ):
        assert abs(year_sum(dataset, 2026, column, through=2) - printed) <= 2


@pytest.mark.parametrize(("period", "printed"), PRINTED_LEASE_3M.items())
def test_lease_quarters_match_the_printed_lease_note(
    dataset: CompanyDataset, period: tuple[int, int], printed: tuple[int, int]
) -> None:
    r = row(dataset, *period)
    assert millions(r["finance_lease_principal"]) == printed[0]
    assert millions(r["finance_lease_assets_acquired"]) == printed[1]


def test_lease_year_to_date_and_full_year_figures_reconcile(dataset: CompanyDataset) -> None:
    assert year_sum(dataset, 2026, "finance_lease_principal", through=2) == 840
    assert year_sum(dataset, 2026, "finance_lease_assets_acquired", through=2) == 902
    assert year_sum(dataset, 2025, "finance_lease_principal", through=3) == 394
    assert year_sum(dataset, 2025, "finance_lease_assets_acquired", through=3) == 989
    for year, (principal, assets) in PRINTED_LEASE_YEARS.items():
        assert year_sum(dataset, year, "finance_lease_principal") == principal
        assert year_sum(dataset, year, "finance_lease_assets_acquired") == assets


def test_the_fiscal_2025_fourth_quarter_lease_flow_carries_the_disclosed_prepayments(
    dataset: CompanyDataset,
) -> None:
    r = row(dataset, 2025, 4)
    assert millions(r["finance_lease_principal"]) == 1_988 - 394 == 1_594
    assert r["finance_lease_principal_basis"] == "derived"
    assert dataset.lease_adjustment is not None
    assert "prepayments" in dataset.lease_adjustment.note
    mapping_note = next(
        r for r in dataset.registry_records if "finance_lease_principal" in r.series_id
    )
    assert mapping_note.notes is not None and "$1.1bn of prepayments" in mapping_note.notes


def test_lease_adjusted_fcf_exists_only_from_the_first_lease_disclosure(
    dataset: CompanyDataset,
) -> None:
    quarterly = dataset.quarterly
    first = quarterly[quarterly["lease_adjusted_fcf"].notna()].iloc[0]
    assert first["fiscal_label"] == "FY24 Q1"
    earlier = quarterly[quarterly["fiscal_year"] < 2024]
    assert earlier["lease_adjusted_fcf"].isna().all()
    assert earlier["base_fcf"].notna().all()  # base FCF is available throughout
    later = quarterly[quarterly["fiscal_year"] >= 2024]
    assert (
        later["lease_adjusted_fcf"] == later["base_fcf"] - later["finance_lease_principal"]
    ).all()


def test_lease_start_is_reported_as_not_disclosed_and_all_checks_pass(
    dataset: CompanyDataset,
) -> None:
    checks = dataset.checks
    assert set(checks["status"]) <= {"pass", "skipped"}
    starts = checks[checks["check"] == "lease_disclosure_starts"].iloc[0]
    assert "FY24 Q1" in starts["detail"] and "not assumed zero" in starts["detail"]


def test_both_revenue_tags_are_used_without_conflicts(dataset: CompanyDataset) -> None:
    revenue = dataset.long[dataset.long["field"] == "revenue"]
    tags = set(revenue["tags"].dropna())
    assert tags <= {
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues; RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerExcludingAssessedTax; Revenues",
    }
    checks = dataset.checks
    assert (checks[checks["check"] == "tag_conflict"]["status"] == "pass").all()


def test_derived_quarters_cite_two_filings(dataset: CompanyDataset) -> None:
    long = dataset.long
    r = long[
        (long["field"] == "cash_capex")
        & (long["fiscal_year"] == 2026)
        & (long["fiscal_quarter"] == 2)
    ].iloc[0]
    components = json.loads(r["components"])
    assert {c["accession"] for c in components} == {"0001652044-26-000071", "0001652044-26-000048"}
    assert r["transformation"] == "six-month year-to-date minus three-month year-to-date"
    assert all("/Archives/edgar/data/1652044/" in c["filing_index_url"] for c in components)


def test_ratios_match_a_hand_calculation(dataset: CompanyDataset) -> None:
    r = row(dataset, 2026, 2)
    assert r["capital_intensity"] == pytest.approx(44_924 / 119_796)
    assert r["cash_reinvestment_rate"] == pytest.approx(44_924 / 39_069)  # above one
    assert r["fcf_margin"] == pytest.approx(-5_855 / 119_796)
    assert r["revenue_yoy_growth"] == pytest.approx(119_796 / 96_428 - 1)
