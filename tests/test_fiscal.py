"""Tests for fiscal-calendar logic: pure date arithmetic with no financial values."""

from datetime import date

import pytest

from ai_capital_cycle_monitor.utils.fiscal import (
    duration_months,
    fiscal_label,
    fiscal_period_for_end,
    fiscal_quarter_end,
    fiscal_quarter_start,
    fiscal_year_start,
    is_near,
)

JUNE = 6  # Microsoft-style fiscal year ending 30 June


def test_june_fiscal_year_boundaries() -> None:
    assert fiscal_year_start(2026, JUNE) == date(2025, 7, 1)
    assert [fiscal_quarter_end(2026, q, JUNE) for q in (1, 2, 3, 4)] == [
        date(2025, 9, 30),
        date(2025, 12, 31),
        date(2026, 3, 31),
        date(2026, 6, 30),
    ]
    assert fiscal_quarter_start(2026, 1, JUNE) == date(2025, 7, 1)
    assert fiscal_quarter_start(2026, 3, JUNE) == date(2026, 1, 1)


def test_calendar_fiscal_year_boundaries() -> None:
    assert fiscal_year_start(2025, 12) == date(2025, 1, 1)
    assert fiscal_quarter_end(2025, 2, 12) == date(2025, 6, 30)


def test_leap_year_february_quarter_end() -> None:
    assert fiscal_quarter_end(2024, 3, JUNE) == date(2024, 3, 31)
    assert fiscal_quarter_end(2024, 2, 8) == date(2024, 2, 29)


@pytest.mark.parametrize(
    ("period_end", "expected"),
    [
        (date(2025, 9, 30), (2026, 1)),
        (date(2025, 12, 31), (2026, 2)),
        (date(2026, 3, 31), (2026, 3)),
        (date(2026, 6, 30), (2026, 4)),
        (date(2025, 6, 30), (2025, 4)),
    ],
)
def test_period_end_maps_to_fiscal_period(period_end: date, expected: tuple[int, int]) -> None:
    assert fiscal_period_for_end(period_end, JUNE) == expected


def test_same_date_maps_differently_under_different_fiscal_calendars() -> None:
    assert fiscal_period_for_end(date(2025, 12, 31), 12) == (2025, 4)
    assert fiscal_period_for_end(date(2025, 12, 31), JUNE) == (2026, 2)


def test_period_end_far_from_any_quarter_end_is_unmapped() -> None:
    assert fiscal_period_for_end(date(2025, 11, 15), JUNE) is None


def test_52_53_week_calendars_match_within_tolerance() -> None:
    assert fiscal_period_for_end(date(2026, 1, 25), 1) == (2026, 4)
    assert fiscal_period_for_end(date(2025, 4, 27), 1) == (2026, 1)
    assert not is_near(date(2025, 4, 20), date(2025, 4, 30))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2025, 7, 1), date(2025, 9, 30), 3),
        (date(2025, 7, 1), date(2025, 12, 31), 6),
        (date(2025, 7, 1), date(2026, 3, 31), 9),
        (date(2025, 7, 1), date(2026, 6, 30), 12),
        (date(2023, 7, 1), date(2024, 6, 30), 12),  # leap-year fiscal year, 366 days
        (date(2025, 7, 1), date(2025, 7, 31), None),
        (date(2025, 7, 1), date(2025, 11, 30), None),
    ],
)
def test_duration_classification(start: date, end: date, expected: int | None) -> None:
    assert duration_months(start, end) == expected


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="1-12"):
        fiscal_year_start(2026, 13)
    with pytest.raises(ValueError, match="1-4"):
        fiscal_quarter_end(2026, 5, JUNE)


def test_fiscal_label() -> None:
    assert fiscal_label(2026, 3) == "FY26 Q3"
    assert fiscal_label(2009, 1) == "FY09 Q1"
