"""Tests for dataset assembly and Parquet round-trips.

The payload is a structure-only software fixture with round numbers for a generic June fiscal
year. It exercises code paths and is never company data.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from ai_capital_cycle_monitor.pipelines.datasets import (
    read_checks,
    read_long,
    read_quarterly,
    write_dataset,
)
from ai_capital_cycle_monitor.pipelines.financials import (
    DatasetError,
    build_company_dataset,
    series_id,
)
from ai_capital_cycle_monitor.pipelines.identity import IdentityCheck, IdentityReport
from ai_capital_cycle_monitor.schemas.provenance import DataBasis
from ai_capital_cycle_monitor.schemas.xbrl import CanonicalField
from synthetic import COMPANY, ENDS, FY_START, MAPPINGS, SNAPSHOT, payload


def _build(data: dict[str, object] | None = None, **kwargs: object):
    return build_company_dataset(COMPANY, MAPPINGS, data or payload(), SNAPSHOT, **kwargs)


def test_quarterly_table_has_values_and_standardised_base_fcf() -> None:
    quarterly = _build().quarterly
    assert quarterly["fiscal_label"].tolist() == ["FY25 Q1", "FY25 Q2", "FY25 Q3", "FY25 Q4"]
    assert quarterly["revenue"].tolist() == [100, 110, 120, 130]
    assert quarterly["operating_cash_flow"].tolist() == [40, 50, 60, 70]
    assert quarterly["cash_capex"].tolist() == [10, 15, 20, 25]
    assert quarterly["base_fcf"].tolist() == [30, 35, 40, 45]
    assert str(quarterly["base_fcf"].dtype) == "Int64"


def test_basis_is_kept_per_observation_and_base_fcf_is_derived() -> None:
    quarterly = _build().quarterly
    assert quarterly["revenue_basis"].tolist() == ["reported", "reported", "reported", "derived"]
    assert quarterly["operating_cash_flow_basis"].tolist() == ["reported"] + ["derived"] * 3
    assert set(quarterly["base_fcf_basis"]) == {"derived"}


def test_missing_component_gives_missing_base_fcf_not_zero() -> None:
    quarterly = _build(payload(capex=[10, 25, None, 70])).quarterly
    assert quarterly["cash_capex"].isna().tolist() == [False, False, True, True]
    assert quarterly["base_fcf"].isna().tolist() == [False, False, True, True]
    assert quarterly["base_fcf_basis"].isna().tolist() == [False, False, True, True]
    assert quarterly["operating_cash_flow"].tolist() == [40, 50, 60, 70]


def test_long_table_preserves_provenance_for_every_observation() -> None:
    long = _build().long
    row = long[(long["field"] == "operating_cash_flow") & (long["fiscal_quarter"] == 3)].iloc[0]
    assert row["series_id"] == series_id("TEST", "operating_cash_flow")
    assert row["tags"] == "Ocf"
    assert row["transformation"] == "nine-month year-to-date minus six-month year-to-date"
    assert row["unit"] == "USD"
    assert row["source_url"] == SNAPSHOT.url
    assert row["source_sha256"] == SNAPSHOT.sha256
    assert row["retrieved_at_utc"] == SNAPSHOT.retrieved_at_utc
    components = json.loads(row["components"])
    assert [c["end"] for c in components] == [ENDS[2], ENDS[1]]
    assert components[0]["accession"] == "0000000000-25-000003"
    assert components[0]["filing_index_url"].endswith(
        "/000000000025000003/0000000000-25-000003-index.htm"
    )
    assert row["filed_latest"] == pd.Timestamp("2025-01-15")


def test_registry_records_cover_each_field_and_base_fcf() -> None:
    records = {r.series_id: r for r in _build().registry_records}
    assert set(records) == {
        series_id("TEST", name)
        for name in ("revenue", "operating_cash_flow", "cash_capex", "base_fcf")
    }
    assert records[series_id("TEST", "base_fcf")].reported_or_estimated is DataBasis.DERIVED
    revenue = records[series_id("TEST", "revenue")]
    assert revenue.reported_or_estimated is DataBasis.DERIVED  # Q4 is a difference
    assert "Rev" in (revenue.notes or "")
    assert revenue.currency == "USD"
    assert str(revenue.period_start) == FY_START
    assert str(revenue.period_end) == ENDS[3]


def test_identity_results_are_recorded_as_checks() -> None:
    report = IdentityReport(
        "TEST", "TEST CO", (IdentityCheck("cik_in_submissions", "0000000001", "0000000001"),), {}
    )
    checks = _build(identity=report).checks
    row = checks[checks["check"] == "identity_cik_in_submissions"].iloc[0]
    assert (row["field"], row["status"]) == ("company", "pass")


def test_checks_table_has_typed_columns() -> None:
    checks = _build().checks
    assert str(checks["fiscal_year"].dtype) == "Int64"
    assert str(checks["expected"].dtype) == "Float64"
    assert set(checks["status"]) <= {"pass", "skipped"}


def test_field_without_observations_is_an_error() -> None:
    data = payload()
    data["facts"]["t"]["Capex"] = {"units": {"USD": []}}  # type: ignore[index]
    with pytest.raises(DatasetError, match="cash_capex"):
        _build(data)


def test_missing_mapping_or_cik_is_an_error() -> None:
    partial = {CanonicalField.REVENUE: MAPPINGS[CanonicalField.REVENUE]}
    with pytest.raises(DatasetError, match="no XBRL mapping"):
        build_company_dataset(COMPANY, partial, payload(), SNAPSHOT)
    no_cik = COMPANY.model_copy(update={"cik": None})
    with pytest.raises(DatasetError, match="no CIK"):
        build_company_dataset(no_cik, MAPPINGS, payload(), SNAPSHOT)


def test_parquet_round_trip_preserves_values_and_missing(tmp_path: Path) -> None:
    dataset = _build(payload(capex=[10, 25, None, 70]))
    write_dataset(dataset, tmp_path)
    quarterly = read_quarterly(tmp_path, "TEST")
    assert quarterly is not None
    pd.testing.assert_frame_equal(quarterly, dataset.quarterly)
    assert read_checks(tmp_path, "TEST") is not None
    assert read_long(tmp_path, "TEST") is not None
    assert read_quarterly(tmp_path, "OTHER") is None


def test_first_fiscal_year_drops_earlier_periods_and_keeps_the_rest() -> None:
    later = payload()["facts"]["t"]  # type: ignore[index]
    shifted = {"facts": {"t": {}}}
    for name, body in later.items():
        entries = list(body["units"]["USD"])
        for entry in list(entries):  # add a prior fiscal year with a different shape of numbers
            entries.append(
                {
                    **entry,
                    "start": entry["start"].replace("2024", "2023").replace("2025", "2024"),
                    "end": entry["end"].replace("2024", "2023").replace("2025", "2024"),
                }
            )
        shifted["facts"]["t"][name] = {"units": {"USD": entries}}
    both = build_company_dataset(COMPANY, MAPPINGS, shifted, SNAPSHOT).quarterly
    assert sorted(both["fiscal_year"].unique()) == [2024, 2025]

    windowed = {
        field: mapping.model_copy(update={"first_fiscal_year": 2025})
        for field, mapping in MAPPINGS.items()
    }
    only_2025 = build_company_dataset(COMPANY, windowed, shifted, SNAPSHOT).quarterly
    assert sorted(only_2025["fiscal_year"].unique()) == [2025]
    assert only_2025["base_fcf"].tolist() == [30, 35, 40, 45]
