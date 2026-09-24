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


def _require_outflow(series: pd.Series, name: str) -> None:
    if (series.dropna() < 0).any():
        raise ValueError(f"{name} must be a positive outflow; negative values found")


def lease_adjusted_fcf(
    base: pd.Series,
    finance_lease_principal: pd.Series,
    other_infrastructure_financing_payments: pd.Series | None = None,
) -> pd.Series:
    """lease_adjusted_fcf = base_fcf - finance_lease_principal - other infrastructure payments.

    Pass `other_infrastructure_financing_payments=None` only when the company's filings were
    reviewed and disclose no such payment. Any other missing input gives a missing result.
    """
    _require_outflow(finance_lease_principal, "finance_lease_principal")
    result = base - finance_lease_principal
    if other_infrastructure_financing_payments is not None:
        _require_outflow(
            other_infrastructure_financing_payments, "other_infrastructure_financing_payments"
        )
        result = result - other_infrastructure_financing_payments
    return result


def capex_including_finance_leases(
    cash_capex: pd.Series, finance_lease_assets_acquired: pd.Series
) -> pd.Series:
    """Supplementary: cash capex plus assets acquired under finance leases (non-cash).

    The lease figure covers every finance-lease asset the company discloses, not only data-centre
    equipment, so this is an upper-bound view of investment, not a like-for-like capex measure.
    """
    _require_outflow(finance_lease_assets_acquired, "finance_lease_assets_acquired")
    return cash_capex + finance_lease_assets_acquired
