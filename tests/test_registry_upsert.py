"""Tests for registry upsert. Rows are synthetic software fixtures in pytest temp directories."""

import csv
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ai_capital_cycle_monitor.schemas.provenance import DataBasis, SourceRecord, SourceType
from ai_capital_cycle_monitor.utils.registry import load_source_registry, upsert_source_records

HEADER = list(SourceRecord.model_fields)


def _record(series_id: str, **overrides: object) -> SourceRecord:
    fields: dict[str, object] = {
        "series_id": series_id,
        "source_name": "Unit-test source",
        "source_url": "https://example.com/unit-test",
        "source_type": SourceType.SEC_FILING,
        "reported_or_estimated": DataBasis.REPORTED,
    }
    return SourceRecord.model_validate(fields | overrides)


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.csv"
    path.write_text(",".join(HEADER) + "\n", encoding="utf-8")
    return path


def test_upsert_writes_rows_sorted_by_series_id(registry: Path) -> None:
    upsert_source_records([_record("b.series"), _record("a.series")], registry)
    assert [r.series_id for r in load_source_registry(registry)] == ["a.series", "b.series"]


def test_upsert_replaces_an_existing_series_and_keeps_others(registry: Path) -> None:
    upsert_source_records([_record("a.series"), _record("b.series", notes="old")], registry)
    upsert_source_records([_record("b.series", notes="new")], registry)
    rows = {r.series_id: r for r in load_source_registry(registry)}
    assert set(rows) == {"a.series", "b.series"}
    assert rows["b.series"].notes == "new"


def test_full_record_round_trips_exactly(registry: Path) -> None:
    record = _record(
        "full.series",
        retrieved_at_utc=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        observation_date=date(2026, 1, 1),
        period_start=date(2025, 7, 1),
        period_end=date(2025, 9, 30),
        filed_or_published_date=date(2025, 10, 30),
        fiscal_year=2026,
        fiscal_quarter=1,
        currency="USD",
        unit="USD",
        transformation="a - b",
        notes='note, with comma and "quotes"',
        reported_or_estimated=DataBasis.DERIVED,
    )
    upsert_source_records([record], registry)
    assert load_source_registry(registry) == [record]


def test_blank_fields_are_written_empty_not_as_the_word_none(registry: Path) -> None:
    upsert_source_records([_record("a.series")], registry)
    with registry.open(newline="", encoding="utf-8") as handle:
        (row,) = list(csv.DictReader(handle))
    assert row["currency"] == ""
    assert row["fiscal_year"] == ""
    assert "None" not in registry.read_text(encoding="utf-8")
