"""Tests for ratios. Inputs are trivial arithmetic, not company data."""

import pandas as pd
import pytest

from ai_capital_cycle_monitor.analysis.ratios import (
    capital_intensity,
    cash_reinvestment_rate,
    fcf_margin,
    year_over_year_growth,
)


def _s(values: list[int | float | None]) -> pd.Series:
    return pd.Series(values, dtype="Float64")


def test_capital_intensity_is_capex_over_revenue() -> None:
    result = capital_intensity(_s([20, 5]), _s([100, 50]))
    assert result.tolist() == pytest.approx([0.2, 0.1])
    assert str(result.dtype) == "Float64"


@pytest.mark.parametrize("revenue", [0, -10])
def test_capital_intensity_is_missing_when_revenue_is_not_positive(revenue: int) -> None:
    assert capital_intensity(_s([20]), _s([revenue])).isna().tolist() == [True]


def test_cash_reinvestment_rate_is_missing_when_operating_cash_flow_is_not_positive() -> None:
    result = cash_reinvestment_rate(_s([30, 30, 30, 30]), _s([60, 0, -5, None]))
    assert result.iloc[0] == pytest.approx(0.5)
    assert result.iloc[1:].isna().tolist() == [True, True, True]


def test_capex_above_operating_cash_flow_is_a_ratio_above_one_not_an_error() -> None:
    assert cash_reinvestment_rate(_s([90]), _s([60])).iloc[0] == pytest.approx(1.5)


def test_fcf_margin_allows_negative_fcf_but_needs_positive_revenue() -> None:
    result = fcf_margin(_s([25, -10, 5]), _s([100, 100, 0]))
    assert result.iloc[0] == pytest.approx(0.25)
    assert result.iloc[1] == pytest.approx(-0.1)
    assert pd.isna(result.iloc[2])


def test_missing_inputs_give_missing_results_never_zero() -> None:
    assert capital_intensity(_s([None, 5]), _s([100, None])).isna().tolist() == [True, True]


def test_year_over_year_growth_needs_a_positive_year_ago_value() -> None:
    result = year_over_year_growth(_s([150, 50, 10, 10]), _s([100, 100, 0, None]))
    assert result.iloc[0] == pytest.approx(0.5)
    assert result.iloc[1] == pytest.approx(-0.5)
    assert result.iloc[2:].isna().tolist() == [True, True]


def test_integer_nullable_inputs_are_accepted() -> None:
    capex = pd.Series([10, None], dtype="Int64")
    revenue = pd.Series([100, 100], dtype="Int64")
    result = capital_intensity(capex, revenue)
    assert result.iloc[0] == pytest.approx(0.1)
    assert pd.isna(result.iloc[1])
