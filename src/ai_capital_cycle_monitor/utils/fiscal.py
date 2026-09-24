"""Fiscal-calendar helpers: map period-end dates to fiscal periods and classify durations.

A fiscal year is labelled by the calendar year in which it ends, so Microsoft's fiscal 2026 ends
on 30 June 2026. Periods are always derived from dates, never from the fiscal-period fields that
SEC facts carry, because those describe the filing and not the fact.
"""

import calendar
from datetime import date, timedelta

DEFAULT_TOLERANCE_DAYS = 7
_DURATION_DAY_BANDS = {3: (80, 100), 6: (170, 200), 9: (260, 290), 12: (355, 375)}


def _validate(fye_month: int, quarter: int | None = None) -> None:
    if not 1 <= fye_month <= 12:
        raise ValueError(f"fiscal year-end month must be 1-12, got {fye_month}")
    if quarter is not None and quarter not in {1, 2, 3, 4}:
        raise ValueError(f"fiscal quarter must be 1-4, got {quarter}")


def _shift_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def fiscal_year_start(fiscal_year: int, fye_month: int) -> date:
    _validate(fye_month)
    year, month = _shift_months(fiscal_year, fye_month, -11)
    return date(year, month, 1)


def fiscal_quarter_end(fiscal_year: int, quarter: int, fye_month: int) -> date:
    _validate(fye_month, quarter)
    year, month = _shift_months(fiscal_year, fye_month, -3 * (4 - quarter))
    return _month_end(year, month)


def fiscal_quarter_start(fiscal_year: int, quarter: int, fye_month: int) -> date:
    _validate(fye_month, quarter)
    if quarter == 1:
        return fiscal_year_start(fiscal_year, fye_month)
    return fiscal_quarter_end(fiscal_year, quarter - 1, fye_month) + timedelta(days=1)


def is_near(first: date, second: date, tolerance_days: int = DEFAULT_TOLERANCE_DAYS) -> bool:
    return abs((first - second).days) <= tolerance_days


def fiscal_period_for_end(
    period_end: date, fye_month: int, tolerance_days: int = DEFAULT_TOLERANCE_DAYS
) -> tuple[int, int] | None:
    """Return (fiscal_year, fiscal_quarter) whose quarter-end is near `period_end`, else None."""
    _validate(fye_month)
    for fiscal_year in (period_end.year, period_end.year + 1):
        for quarter in (1, 2, 3, 4):
            quarter_end = fiscal_quarter_end(fiscal_year, quarter, fye_month)
            if is_near(period_end, quarter_end, tolerance_days):
                return fiscal_year, quarter
    return None


def duration_months(start: date, end: date) -> int | None:
    """Classify an inclusive period as 3, 6, 9 or 12 months, or None if it fits none."""
    days = (end - start).days + 1
    for months, (low, high) in _DURATION_DAY_BANDS.items():
        if low <= days <= high:
            return months
    return None


def fiscal_label(fiscal_year: int, quarter: int) -> str:
    return f"FY{fiscal_year % 100:02d} Q{quarter}"
