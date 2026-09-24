"""Tests for the provenance schema and source-registry loader.

Rows written here are software fixtures (obviously synthetic strings). They exist only inside
pytest temporary directories and never enter project data or outputs.
"""

import csv
from pathlib import Path

import pytest

from ai_capital_cycle_monitor.schemas.provenance import DataBasis, SourceRecord, SourceType
from ai_capital_cycle_monitor.utils.paths import SOURCE_REGISTRY_PATH
from ai_capital_cycle_monitor.utils.registry import load_source_registry

HEADER = list(SourceRecord.model_fields)


def _valid_row() -> dict[str, str]:
    row = dict.fromkeys(HEADER, "")
    row.update(
        series_id="unit-test-series",
        source_name="Unit-test source",
        source_url="https://example.com/unit-test",
        source_type="sec_filing",
        reported_or_estimated="reported",
    )
    return row


def _write(path: Path, rows: list[dict[str, str]], header: list[str] | None = None) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header or HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_committed_registry_header_matches_schema() -> None:
    with SOURCE_REGISTRY_PATH.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == HEADER


def test_committed_registry_validates() -> None:
    load_source_registry()


def test_valid_row_loads_and_blank_cells_stay_missing(tmp_path: Path) -> None:
    (record,) = load_source_registry(_write(tmp_path / "registry.csv", [_valid_row()]))
    assert record.source_type is SourceType.SEC_FILING
    assert record.reported_or_estimated is DataBasis.REPORTED
    assert record.fiscal_year is None
    assert record.retrieved_at_utc is None
    assert record.currency is None


def test_unknown_source_type_is_rejected(tmp_path: Path) -> None:
    row = _valid_row() | {"source_type": "blog_post"}
    with pytest.raises(ValueError, match="row 2 is invalid"):
        load_source_registry(_write(tmp_path / "registry.csv", [row]))


def test_naive_timestamp_is_rejected(tmp_path: Path) -> None:
    row = _valid_row() | {"retrieved_at_utc": "2026-01-01T00:00:00"}
    with pytest.raises(ValueError, match="timezone-aware"):
        load_source_registry(_write(tmp_path / "registry.csv", [row]))


def test_aware_timestamp_is_accepted(tmp_path: Path) -> None:
    row = _valid_row() | {"retrieved_at_utc": "2026-01-01T00:00:00Z"}
    (record,) = load_source_registry(_write(tmp_path / "registry.csv", [row]))
    assert record.retrieved_at_utc is not None
    assert record.retrieved_at_utc.utcoffset() is not None


def test_period_end_before_start_is_rejected(tmp_path: Path) -> None:
    row = _valid_row() | {"period_start": "2026-03-31", "period_end": "2026-01-01"}
    with pytest.raises(ValueError, match="period_end"):
        load_source_registry(_write(tmp_path / "registry.csv", [row]))


def test_invalid_currency_is_rejected(tmp_path: Path) -> None:
    row = _valid_row() | {"currency": "dollars"}
    with pytest.raises(ValueError, match="currency"):
        load_source_registry(_write(tmp_path / "registry.csv", [row]))


def test_wrong_header_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "registry.csv", [], header=["series_id", "source_name"])
    with pytest.raises(ValueError, match="header must be"):
        load_source_registry(path)
