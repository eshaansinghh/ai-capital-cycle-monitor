"""Tests for dataset assembly and Parquet round-trips.

The payload is a structure-only software fixture with round numbers for a generic June fiscal
year. It exercises code paths and is never company data.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from ai_capital_cycle_monitor.clients.raw_store import Snapshot
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
from ai_capital_cycle_monitor.schemas.config import Company
from ai_capital_cycle_monitor.schemas.provenance import DataBasis
from ai_capital_cycle_monitor.schemas.xbrl import CanonicalField, FieldMapping, TagRef

COMPANY = Company.model_validate(
    {
        "ticker": "TEST",
        "name": "Test Co",
        "role": "hyperscaler",
        "exchange": "TESTX",
        "currency": "USD",
        "filer_type": "domestic_10k",
        "cik": "0000000001",
        "fiscal_year_end_month": 6,
    }
)
SNAPSHOT = Snapshot(
    path=Path("unused"),
    url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json",
    retrieved_at_utc=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    http_status=200,
    sha256="a" * 64,
    size_bytes=1,
)
MAPPINGS = {
    CanonicalField.REVENUE: FieldMapping(
        statement="income", expect_non_negative=True, candidates=[TagRef(taxonomy="t", tag="Rev")]
    ),
    CanonicalField.OPERATING_CASH_FLOW: FieldMapping(
        statement="cash_flow", candidates=[TagRef(taxonomy="t", tag="Ocf")]
    ),
    CanonicalField.CASH_CAPEX: FieldMapping(
        statement="cash_flow",
        expect_non_negative=True,
        candidates=[TagRef(taxonomy="t", tag="Capex")],
    ),
}
FY_START = "2024-07-01"
ENDS = ["2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30"]


def _entry(start: str, end: str, value: int, n: int) -> dict[str, object]:
    return {
        "start": start,
        "end": end,
        "val": value,
        "accn": f"0000000000-25-00000{n}",
        "fy": 2025,
        "fp": "Q1",
        "form": "10-K" if end == ENDS[3] else "10-Q",
        "filed": "2025-08-01" if end == ENDS[3] else "2025-01-15",
    }


def _cumulative(values: list[int | None]) -> list[dict[str, object]]:
    return [
        _entry(FY_START, end, value, n)
        for n, (end, value) in enumerate(zip(ENDS, values, strict=True), start=1)
        if value is not None
    ]


def _payload(capex: list[int | None] | None = None) -> dict[str, object]:
    revenue = [
        _entry(FY_START, ENDS[0], 100, 1),  # standalone Q1
        _entry("2024-10-01", ENDS[1], 110, 2),  # standalone Q2
        _entry("2025-01-01", ENDS[2], 120, 3),  # standalone Q3
        _entry(FY_START, ENDS[1], 210, 2),  # six-month year-to-date
        _entry(FY_START, ENDS[2], 330, 3),  # nine-month year-to-date
        _entry(FY_START, ENDS[3], 460, 4),  # fiscal year
    ]
    facts = {
        "Rev": {"units": {"USD": revenue}},
        "Ocf": {"units": {"USD": _cumulative([40, 90, 150, 220])}},
        "Capex": {"units": {"USD": _cumulative(capex or [10, 25, 45, 70])}},
    }
    return {"facts": {"t": facts}}


def _build(payload: dict[str, object] | None = None, **kwargs: object):
    return build_company_dataset(COMPANY, MAPPINGS, payload or _payload(), SNAPSHOT, **kwargs)


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
    quarterly = _build(_payload(capex=[10, 25, None, 70])).quarterly
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
    payload = _payload()
    payload["facts"]["t"]["Capex"] = {"units": {"USD": []}}  # type: ignore[index]
    with pytest.raises(DatasetError, match="cash_capex"):
        _build(payload)


def test_missing_mapping_or_cik_is_an_error() -> None:
    partial = {CanonicalField.REVENUE: MAPPINGS[CanonicalField.REVENUE]}
    with pytest.raises(DatasetError, match="no XBRL mapping"):
        build_company_dataset(COMPANY, partial, _payload(), SNAPSHOT)
    no_cik = COMPANY.model_copy(update={"cik": None})
    with pytest.raises(DatasetError, match="no CIK"):
        build_company_dataset(no_cik, MAPPINGS, _payload(), SNAPSHOT)


def test_parquet_round_trip_preserves_values_and_missing(tmp_path: Path) -> None:
    dataset = _build(_payload(capex=[10, 25, None, 70]))
    write_dataset(dataset, tmp_path)
    quarterly = read_quarterly(tmp_path, "TEST")
    assert quarterly is not None
    pd.testing.assert_frame_equal(quarterly, dataset.quarterly)
    assert read_checks(tmp_path, "TEST") is not None
    assert read_long(tmp_path, "TEST") is not None
    assert read_quarterly(tmp_path, "OTHER") is None
