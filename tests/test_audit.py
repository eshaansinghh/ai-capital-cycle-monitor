"""Tests for tag-audit reports (structure-only software fixture)."""

from ai_capital_cycle_monitor.pipelines.audit import coverage_by_fiscal_year, find_tags
from ai_capital_cycle_monitor.schemas.xbrl import FieldMapping, TagRef


def _entry(start: str, end: str, value: int, accn: str, form: str = "10-Q") -> dict[str, object]:
    return {
        "start": start,
        "end": end,
        "val": value,
        "accn": accn,
        "fy": 2025,
        "fp": "Q1",
        "form": form,
        "filed": "2025-01-01",
    }


PAYLOAD = {
    "facts": {
        "t": {
            "Old": {
                "label": "Old revenue label",
                "units": {"USD": [_entry("2023-07-01", "2023-09-30", 5, "A-1")]},
            },
            "New": {
                "label": "New revenue label",
                "units": {
                    "USD": [
                        _entry("2024-07-01", "2024-09-30", 6, "A-2"),
                        _entry("2024-07-01", "2024-12-31", 13, "A-3"),
                        _entry("2024-07-01", "2024-09-30", 6, "A-9", form="8-K"),
                    ]
                },
            },
            "Unrelated": {
                "label": "Something else",
                "units": {"USD": [_entry("2024-07-01", "2024-09-30", 1, "A-4")]},
            },
        }
    }
}
MAPPING = FieldMapping(
    statement="income",
    candidates=[TagRef(taxonomy="t", tag="New"), TagRef(taxonomy="t", tag="Old")],
)


def test_find_tags_matches_names_and_labels_and_reports_spans() -> None:
    found = find_tags(PAYLOAD, "revenue")
    assert found["tag"].tolist() == ["New", "Old"]
    new = found[found["tag"] == "New"].iloc[0]
    assert (new["duration_facts"], new["first_end"], new["last_end"]) == (
        2,
        "2024-09-30",
        "2024-12-31",
    )


def test_find_tags_returns_an_empty_table_when_nothing_matches() -> None:
    assert find_tags(PAYLOAD, "nomatch").empty


def test_coverage_shows_which_tag_supplies_each_fiscal_year() -> None:
    coverage = coverage_by_fiscal_year(PAYLOAD, MAPPING, fye_month=6)
    rows = {(r.fiscal_year, r.tag): r.selected_facts for r in coverage.itertuples()}
    assert rows == {(2024, "Old"): 1, (2025, "New"): 2}
    assert coverage["tag_conflicts"].sum() == 0


def test_coverage_is_empty_without_facts() -> None:
    assert coverage_by_fiscal_year({"facts": {}}, MAPPING, fye_month=6).empty
