"""Structure-only synthetic fixtures shared by dataset and build tests.

Round numbers for a generic June fiscal year. They exercise code paths and are never company data.
"""

from datetime import UTC, datetime
from pathlib import Path

from ai_capital_cycle_monitor.clients.raw_store import Snapshot
from ai_capital_cycle_monitor.schemas.config import Company
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
