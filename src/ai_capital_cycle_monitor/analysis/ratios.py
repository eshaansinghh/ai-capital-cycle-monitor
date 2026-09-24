"""Ratios following config/metrics.yml. An undefined ratio is missing, never zero or infinite."""

import pandas as pd


def _ratio(numerator: pd.Series, denominator: pd.Series, *, floor: float = 0.0) -> pd.Series:
    """numerator / denominator, missing where the denominator is not above `floor` or is missing."""
    numerator = numerator.astype("Float64")
    denominator = denominator.astype("Float64")
    valid = denominator > floor
    result = numerator / denominator.where(valid)
    return result.where(valid.fillna(False))


def capital_intensity(cash_capex: pd.Series, revenue: pd.Series) -> pd.Series:
    """cash_capex / revenue. Missing when revenue is zero or negative."""
    return _ratio(cash_capex, revenue)


def cash_reinvestment_rate(cash_capex: pd.Series, operating_cash_flow: pd.Series) -> pd.Series:
    """cash_capex / operating_cash_flow. Missing when operating cash flow is zero or negative."""
    return _ratio(cash_capex, operating_cash_flow)


def fcf_margin(fcf: pd.Series, revenue: pd.Series) -> pd.Series:
    """FCF / revenue. Missing when revenue is zero or negative."""
    return _ratio(fcf, revenue)


def year_over_year_growth(current: pd.Series, year_ago: pd.Series) -> pd.Series:
    """current / year_ago - 1. Missing when the year-ago value is zero, negative or missing."""
    return _ratio(current, year_ago) - 1
