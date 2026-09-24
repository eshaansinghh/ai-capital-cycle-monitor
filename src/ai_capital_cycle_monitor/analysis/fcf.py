"""Free-cash-flow calculations following the definitions in config/metrics.yml."""

import pandas as pd


def base_fcf(operating_cash_flow: pd.Series, cash_capex: pd.Series) -> pd.Series:
    """base_fcf = operating_cash_flow - cash_capex.

    `cash_capex` is cash purchases of property and equipment as a positive outflow. A negative
    value means the sign convention was misapplied upstream, so it is rejected rather than flipped.
    A missing input gives a missing result, never zero.
    """
    if (cash_capex.dropna() < 0).any():
        raise ValueError("cash_capex must be a positive outflow; negative values found")
    return operating_cash_flow - cash_capex
