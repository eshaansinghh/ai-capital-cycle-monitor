"""Tests for the base free-cash-flow formula. Inputs are trivial arithmetic, not company data."""

import pandas as pd
import pytest

from ai_capital_cycle_monitor.analysis.fcf import base_fcf


def _series(values: list[int | None], name: str) -> pd.Series:
    return pd.Series(values, dtype="Int64", name=name)


def test_base_fcf_is_operating_cash_flow_minus_capex() -> None:
    result = base_fcf(_series([100, 80], "ocf"), _series([30, 90], "capex"))
    assert result.tolist() == [70, -10]


def test_missing_input_gives_missing_result_not_zero() -> None:
    result = base_fcf(_series([100, None, 50], "ocf"), _series([30, 20, None], "capex"))
    assert result.iloc[0] == 70
    assert result.isna().tolist() == [False, True, True]


def test_negative_capex_is_rejected_rather_than_flipped() -> None:
    with pytest.raises(ValueError, match="positive outflow"):
        base_fcf(_series([100], "ocf"), _series([-30], "capex"))


def test_zero_capex_is_valid_and_keeps_operating_cash_flow() -> None:
    assert base_fcf(_series([100], "ocf"), _series([0], "capex")).tolist() == [100]


def test_result_stays_aligned_to_the_index() -> None:
    ocf = pd.Series([100, 80], index=["a", "b"], dtype="Int64")
    capex = pd.Series([30, 10], index=["a", "b"], dtype="Int64")
    assert base_fcf(ocf, capex).to_dict() == {"a": 70, "b": 70}
