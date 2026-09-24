"""Structure-only synthetic fixtures shared by dataset and build tests.

Round numbers for a generic June fiscal year. They exercise code paths and are never company data.
"""

from datetime import UTC, datetime
from pathlib import Path

from ai_capital_cycle_monitor.clients.raw_store import Snapshot
from ai_capital_cycle_monitor.schemas.config import Company
from ai_capital_cycle_monitor.schemas.xbrl import (
    CanonicalField,
    FieldMapping,
    LeaseAdjustment,
    OtherPaymentsTreatment,
    TagRef,
)

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


def entry(start: str, end: str, value: int, n: int) -> dict[str, object]:
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


def cumulative_entries(values: list[int | None]) -> list[dict[str, object]]:
    return [
        entry(FY_START, end, value, n)
        for n, (end, value) in enumerate(zip(ENDS, values, strict=True), start=1)
        if value is not None
    ]


def payload(capex: list[int | None] | None = None) -> dict[str, object]:
    revenue = [
        entry(FY_START, ENDS[0], 100, 1),  # standalone Q1
        entry("2024-10-01", ENDS[1], 110, 2),  # standalone Q2
        entry("2025-01-01", ENDS[2], 120, 3),  # standalone Q3
        entry(FY_START, ENDS[1], 210, 2),  # six-month year-to-date
        entry(FY_START, ENDS[2], 330, 3),  # nine-month year-to-date
        entry(FY_START, ENDS[3], 460, 4),  # fiscal year
    ]
    facts = {
        "Rev": {"units": {"USD": revenue}},
        "Ocf": {"units": {"USD": cumulative_entries([40, 90, 150, 220])}},
        "Capex": {"units": {"USD": cumulative_entries(capex or [10, 25, 45, 70])}},
    }
    return {"facts": {"t": facts}}


LEASE_MAPPINGS = {
    **MAPPINGS,
    CanonicalField.FINANCE_LEASE_PRINCIPAL: FieldMapping(
        statement="cash_flow",
        expect_non_negative=True,
        candidates=[TagRef(taxonomy="t", tag="LeaseP")],
    ),
    CanonicalField.FINANCE_LEASE_ASSETS_ACQUIRED: FieldMapping(
        statement="lease_note",
        expect_non_negative=True,
        candidates=[TagRef(taxonomy="t", tag="LeaseA")],
    ),
}
OTHER_MAPPING = FieldMapping(
    statement="cash_flow",
    expect_non_negative=True,
    candidates=[TagRef(taxonomy="t", tag="OtherPay")],
)
NONE_DISCLOSED = LeaseAdjustment(
    other_infrastructure_financing_payments=OtherPaymentsTreatment.NONE_DISCLOSED,
    note="Reviewed the synthetic cash-flow statement: no such line exists.",
)
MAPPED_OTHER = LeaseAdjustment(
    other_infrastructure_financing_payments=OtherPaymentsTreatment.MAPPED,
    note="Synthetic: a disclosed financing-obligation line is mapped.",
)


def with_lease_facts(
    base: dict[str, object],
    principal: list[int | None] | None = None,
    assets: list[int | None] | None = None,
    other: list[int | None] | None = None,
) -> dict[str, object]:
    """Add cumulative lease facts (year-to-date style) to a payload from payload()."""
    facts = dict(base["facts"]["t"])  # type: ignore[index]
    if principal is not None:
        facts["LeaseP"] = {"units": {"USD": cumulative_entries(principal)}}
    if assets is not None:
        facts["LeaseA"] = {"units": {"USD": cumulative_entries(assets)}}
    if other is not None:
        facts["OtherPay"] = {"units": {"USD": cumulative_entries(other)}}
    return {"facts": {"t": facts}}


def with_prior_year(base: dict[str, object], scale: float = 0.5) -> dict[str, object]:
    """Add a fiscal 2024 (July 2023 to June 2024) copy of every fact, values multiplied by scale."""
    facts: dict[str, object] = {}
    for tag, body in base["facts"]["t"].items():  # type: ignore[index]
        entries = list(body["units"]["USD"])
        for item in list(entries):
            earlier = dict(item)
            for key in ("start", "end"):
                earlier[key] = _minus_year(item[key])
            earlier["val"] = int(item["val"] * scale)
            earlier["accn"] = "0000000000-24-000001"
            entries.append(earlier)
        facts[tag] = {"units": {"USD": entries}}
    return {"facts": {"t": facts}}


def _minus_year(date_text: str) -> str:
    return f"{int(date_text[:4]) - 1}{date_text[4:]}"
