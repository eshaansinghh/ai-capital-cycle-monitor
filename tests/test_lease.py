"""Tests for lease-adjusted FCF, growth and the lease-configuration rules.

Synthetic structure-only inputs (round numbers, generic June fiscal year). Never company data.
"""

import pandas as pd
import pytest

from ai_capital_cycle_monitor.analysis.fcf import capex_including_finance_leases, lease_adjusted_fcf
from ai_capital_cycle_monitor.pipelines.financials import (
    DatasetError,
    build_company_dataset,
    series_id,
)
from ai_capital_cycle_monitor.schemas.xbrl import CanonicalField
from synthetic import (
    COMPANY,
    LEASE_MAPPINGS,
    MAPPED_OTHER,
    MAPPINGS,
    NONE_DISCLOSED,
    OTHER_MAPPING,
    SNAPSHOT,
    payload,
    with_lease_facts,
    with_prior_year,
)

PRINCIPAL = [2, 5, 9, 14]  # cumulative -> quarters 2, 3, 4, 5
ASSETS = [4, 10, 18, 28]  # cumulative -> quarters 4, 6, 8, 10


def _s(values: list[int | None]) -> pd.Series:
    return pd.Series(values, dtype="Int64")


def _dataset(principal=PRINCIPAL, assets=ASSETS, lease=NONE_DISCLOSED, mappings=LEASE_MAPPINGS):
    facts = with_lease_facts(payload(), principal=principal, assets=assets)
    return build_company_dataset(COMPANY, mappings, facts, SNAPSHOT, lease=lease)


def test_lease_adjusted_fcf_subtracts_principal_and_other_payments() -> None:
    assert lease_adjusted_fcf(_s([30, 20]), _s([2, 3])).tolist() == [28, 17]
    assert lease_adjusted_fcf(_s([30, 20]), _s([2, 3]), _s([1, 1])).tolist() == [27, 16]


def test_a_missing_lease_component_gives_a_missing_result_not_base_fcf() -> None:
    result = lease_adjusted_fcf(_s([30, 20]), _s([2, None]))
    assert result.iloc[0] == 28
    assert pd.isna(result.iloc[1])
    both = lease_adjusted_fcf(_s([30]), _s([2]), _s([None]))
    assert pd.isna(both.iloc[0])


@pytest.mark.parametrize("bad", ["principal", "other", "assets"])
def test_negative_outflows_are_rejected_not_flipped(bad: str) -> None:
    negative = _s([-1])
    with pytest.raises(ValueError, match="positive outflow"):
        if bad == "principal":
            lease_adjusted_fcf(_s([30]), negative)
        elif bad == "other":
            lease_adjusted_fcf(_s([30]), _s([1]), negative)
        else:
            capex_including_finance_leases(_s([10]), negative)


def test_capex_including_finance_leases_adds_assets_acquired() -> None:
    assert capex_including_finance_leases(_s([10, 20]), _s([4, None])).isna().tolist() == [
        False,
        True,
    ]
    assert capex_including_finance_leases(_s([10]), _s([4])).tolist() == [14]


def test_dataset_computes_lease_adjusted_fcf_from_mapped_components() -> None:
    quarterly = _dataset().quarterly
    assert quarterly["base_fcf"].tolist() == [30, 35, 40, 45]
    assert quarterly["finance_lease_principal"].tolist() == [2, 3, 4, 5]
    assert quarterly["lease_adjusted_fcf"].tolist() == [28, 32, 36, 40]
    assert set(quarterly["lease_adjusted_fcf_basis"]) == {"derived"}
    assert quarterly["capex_incl_finance_leases"].tolist() == [14, 21, 28, 35]


def test_a_missing_principal_quarter_leaves_lease_adjusted_fcf_missing_and_warns() -> None:
    dataset = _dataset(principal=[2, 5, None, 14])
    quarterly = dataset.quarterly
    assert quarterly["lease_adjusted_fcf"].isna().tolist() == [False, False, True, True]
    assert quarterly["base_fcf"].notna().all()
    warnings = dataset.checks[
        (dataset.checks["check"] == "lease_adjustment_coverage")
        & (dataset.checks["status"] == "warn")
    ]
    assert warnings["fiscal_quarter"].tolist() == [3, 4]


def test_complete_lease_data_passes_the_coverage_check() -> None:
    checks = _dataset().checks
    row = checks[checks["check"] == "lease_adjustment_coverage"].iloc[0]
    assert row["status"] == "pass"


def test_a_mapped_other_payment_line_is_subtracted() -> None:
    mappings = {
        **LEASE_MAPPINGS,
        CanonicalField.OTHER_INFRASTRUCTURE_FINANCING_PAYMENTS: OTHER_MAPPING,
    }
    facts = with_lease_facts(payload(), principal=PRINCIPAL, assets=ASSETS, other=[1, 3, 6, 10])
    dataset = build_company_dataset(COMPANY, mappings, facts, SNAPSHOT, lease=MAPPED_OTHER)
    assert dataset.quarterly["other_infrastructure_financing_payments"].tolist() == [1, 2, 3, 4]
    assert dataset.quarterly["lease_adjusted_fcf"].tolist() == [27, 30, 33, 36]


def test_company_without_lease_data_has_lease_adjusted_fcf_unavailable_not_base_fcf() -> None:
    dataset = build_company_dataset(COMPANY, MAPPINGS, payload(), SNAPSHOT)
    assert dataset.quarterly["lease_adjusted_fcf"].isna().all()
    assert dataset.quarterly["base_fcf"].notna().all()
    assert dataset.lease_adjustment is None
    records = {r.series_id for r in dataset.registry_records}
    assert series_id("TEST", "lease_adjusted_fcf") not in records


def test_lease_series_are_registered_only_when_they_exist() -> None:
    records = {r.series_id: r for r in _dataset().registry_records}
    lease = records[series_id("TEST", "lease_adjusted_fcf")]
    assert "finance_lease_principal" in lease.transformation
    assert series_id("TEST", "finance_lease_principal") in records
    assert series_id("TEST", "capex_incl_finance_leases") in records


def test_principal_without_a_reviewed_lease_entry_is_refused() -> None:
    with pytest.raises(DatasetError, match="no reviewed lease"):
        _dataset(lease=None)


def test_lease_entry_without_principal_mapping_is_refused() -> None:
    with pytest.raises(DatasetError, match="no principal mapping"):
        build_company_dataset(COMPANY, MAPPINGS, payload(), SNAPSHOT, lease=NONE_DISCLOSED)


def test_declaring_other_payments_mapped_needs_the_mapping_and_vice_versa() -> None:
    with pytest.raises(DatasetError, match="has no mapping"):
        _dataset(lease=MAPPED_OTHER)
    both = {**LEASE_MAPPINGS, CanonicalField.OTHER_INFRASTRUCTURE_FINANCING_PAYMENTS: OTHER_MAPPING}
    facts = with_lease_facts(payload(), principal=PRINCIPAL, assets=ASSETS, other=[1, 3, 6, 10])
    with pytest.raises(DatasetError, match="declares no other payments"):
        build_company_dataset(COMPANY, both, facts, SNAPSHOT, lease=NONE_DISCLOSED)


def test_other_payments_without_principal_are_refused() -> None:
    mappings = {**MAPPINGS, CanonicalField.OTHER_INFRASTRUCTURE_FINANCING_PAYMENTS: OTHER_MAPPING}
    facts = with_lease_facts(payload(), other=[1, 3, 6, 10])
    with pytest.raises(DatasetError, match="without finance-lease principal"):
        build_company_dataset(COMPANY, mappings, facts, SNAPSHOT)


def test_revenue_growth_compares_the_same_fiscal_quarter_a_year_earlier() -> None:
    facts = with_prior_year(payload(), scale=0.5)
    quarterly = build_company_dataset(COMPANY, MAPPINGS, facts, SNAPSHOT).quarterly
    assert sorted(quarterly["fiscal_year"].unique()) == [2024, 2025]
    fy24 = quarterly[quarterly["fiscal_year"] == 2024]
    fy25 = quarterly[quarterly["fiscal_year"] == 2025]
    assert fy24["revenue_yoy_growth"].isna().all()  # no year-ago quarter exists
    assert fy25["revenue_yoy_growth"].tolist() == pytest.approx([1.0, 1.0, 1.0, 1.0])


def test_growth_is_missing_not_shifted_when_the_year_ago_quarter_is_absent() -> None:
    facts = with_prior_year(payload(), scale=0.5)
    # drop the prior-year Q2 revenue facts so that quarter has no comparator
    revenue = [
        e
        for e in facts["facts"]["t"]["Rev"]["units"]["USD"]  # type: ignore[index]
        if not (
            e["start"] == "2023-10-01" or (e["start"] == "2023-07-01" and e["end"] == "2023-12-31")
        )
    ]
    facts["facts"]["t"]["Rev"]["units"]["USD"] = revenue  # type: ignore[index]
    quarterly = build_company_dataset(COMPANY, MAPPINGS, facts, SNAPSHOT).quarterly
    fy25 = quarterly[quarterly["fiscal_year"] == 2025].set_index("fiscal_quarter")
    assert pd.isna(fy25.loc[2, "revenue_yoy_growth"])
    assert fy25.loc[1, "revenue_yoy_growth"] == pytest.approx(1.0)
    assert fy25.loc[3, "revenue_yoy_growth"] == pytest.approx(1.0)


def test_ratio_columns_follow_the_formulas() -> None:
    quarterly = _dataset().quarterly
    assert quarterly["capital_intensity"].tolist() == pytest.approx(
        [10 / 100, 15 / 110, 20 / 120, 25 / 130]
    )
    assert quarterly["cash_reinvestment_rate"].tolist() == pytest.approx(
        [10 / 40, 15 / 50, 20 / 60, 25 / 70]
    )
    assert quarterly["fcf_margin"].tolist() == pytest.approx(
        [30 / 100, 35 / 110, 40 / 120, 45 / 130]
    )


def test_quarters_before_the_first_lease_disclosure_are_not_disclosed_rather_than_defects() -> None:
    base = with_prior_year(payload(), scale=0.5)  # fiscal 2024 and 2025
    facts = with_lease_facts(
        base, principal=PRINCIPAL, assets=ASSETS
    )  # lease facts: fiscal 2025 only
    dataset = build_company_dataset(COMPANY, LEASE_MAPPINGS, facts, SNAPSHOT, lease=NONE_DISCLOSED)
    quarterly = dataset.quarterly
    assert quarterly["finance_lease_principal"].isna().tolist() == [True] * 4 + [False] * 4
    assert quarterly["lease_adjusted_fcf"].isna().tolist() == [True] * 4 + [False] * 4
    assert quarterly["base_fcf"].notna().all()
    checks = dataset.checks
    starts = checks[checks["check"] == "lease_disclosure_starts"].iloc[0]
    assert starts["status"] == "skipped"
    assert "FY25 Q1" in starts["detail"] and "4 earlier quarters" in starts["detail"]
    assert "not assumed zero" in starts["detail"]
    coverage = checks[checks["check"] == "lease_adjustment_coverage"]
    assert coverage["status"].tolist() == ["pass"]
    assert not (checks["status"] == "warn").any()
