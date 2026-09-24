"""Factories for isolated software unit tests of XBRL logic.

Values are arithmetic-friendly inputs (10, 25, 45, 70) for a generic fiscal year. They exercise
code paths only and are never company data, outputs or screenshots.
"""

from datetime import date

from ai_capital_cycle_monitor.pipelines.xbrl import SelectedFact, XbrlFact

FYE_MONTH = 6
FY_START = "2024-07-01"  # start of a generic fiscal year ending 30 June 2025
QUARTER_ENDS = ("2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30")


def fact(
    start: str,
    end: str,
    value: int | float,
    *,
    tag: str = "TestTag",
    taxonomy: str = "test",
    filed: str = "2030-01-01",
    accession: str = "0000000000-00-000001",
    form: str = "10-Q",
    filing_fiscal_year: int | None = None,
) -> XbrlFact:
    return XbrlFact(
        taxonomy=taxonomy,
        tag=tag,
        unit="USD",
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        value=value,
        accession=accession,
        form=form,
        filed=date.fromisoformat(filed),
        filing_fiscal_year=filing_fiscal_year,
        filing_fiscal_period=None,
        frame=None,
    )


def selected(start: str, end: str, value: int | float, **kwargs: object) -> SelectedFact:
    return SelectedFact(fact(start, end, value, **kwargs))  # type: ignore[arg-type]


def cumulative(values: tuple[int | None, ...] = (10, 25, 45, 70)) -> list[SelectedFact]:
    """Year-to-date facts for a generic fiscal year; None omits that period entirely."""
    return [
        selected(FY_START, end, value, accession=f"0000000000-00-00000{index}")
        for index, (end, value) in enumerate(zip(QUARTER_ENDS, values, strict=True), start=1)
        if value is not None
    ]
