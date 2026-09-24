"""Smoke tests: the package and its subpackages import cleanly."""

import importlib

import pytest

import ai_capital_cycle_monitor

SUBPACKAGES = ["clients", "pipelines", "analysis", "charts", "schemas", "utils"]


def test_version_is_set() -> None:
    assert ai_capital_cycle_monitor.__version__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    importlib.import_module(f"ai_capital_cycle_monitor.{name}")
