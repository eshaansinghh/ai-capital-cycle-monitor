"""Tests for XBRL fact extraction and per-period selection (software fixtures only)."""

import pytest

from ai_capital_cycle_monitor.pipelines.xbrl import extract_facts, select_facts
from ai_capital_cycle_monitor.schemas.xbrl import TagRef
from factories import fact

PRIMARY = TagRef(taxonomy="test", tag="Primary")
SECONDARY = TagRef(taxonomy="test", tag="Secondary")
Q1 = ("2024-07-01", "2024-09-30")


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "start": "2024-07-01",
        "end": "2024-09-30",
        "val": 10,
        "accn": "0000000000-00-000001",
        "fy": 2025,
        "fp": "Q1",
        "form": "10-Q",
        "filed": "2024-10-25",
    }
    return entry | overrides


def _payload(*entries: dict[str, object], tag: str = "Primary") -> dict[str, object]:
    return {"facts": {"test": {tag: {"units": {"USD": list(entries)}}}}}


def test_extract_reads_duration_facts_and_keeps_provenance() -> None:
    (extracted,) = extract_facts(_payload(_entry(frame="CY2024Q3")), [PRIMARY])
    assert (extracted.start.isoformat(), extracted.end.isoformat()) == Q1
    assert extracted.value == 10
    assert extracted.accession == "0000000000-00-000001"
    assert extracted.form == "10-Q"
    assert extracted.filed.isoformat() == "2024-10-25"
    assert extracted.tag == "Primary"
    assert extracted.frame == "CY2024Q3"
    assert extracted.filing_fiscal_year == 2025


def test_extract_skips_instant_facts_other_forms_and_other_units() -> None:
    instant = {k: v for k, v in _entry().items() if k != "start"}
    payload = _payload(instant, _entry(form="8-K"), _entry(form="10-K"))
    assert [f.form for f in extract_facts(payload, [PRIMARY])] == ["10-K"]
    assert extract_facts(payload, [PRIMARY], unit="EUR") == []


def test_extract_ignores_tags_the_company_does_not_report() -> None:
    assert extract_facts({"facts": {}}, [PRIMARY]) == []


def test_earliest_filed_fact_is_chosen_and_identical_restatements_are_ignored() -> None:
    first = fact(*Q1, 10, tag="Primary", filed="2024-10-25", accession="A-1")
    same_again = fact(*Q1, 10, tag="Primary", filed="2025-10-25", accession="A-2")
    (item,) = select_facts([same_again, first], [PRIMARY])
    assert item.fact.accession == "A-1"
    assert item.later_revisions == ()


def test_later_different_value_is_kept_as_a_revision_not_substituted() -> None:
    first = fact(*Q1, 10, tag="Primary", filed="2024-10-25", accession="A-1")
    revised = fact(*Q1, 12, tag="Primary", filed="2025-10-25", accession="A-2")
    (item,) = select_facts([first, revised], [PRIMARY])
    assert item.fact.value == 10
    assert [f.value for f in item.later_revisions] == [12]


def test_primary_tag_wins_and_disagreeing_secondary_is_flagged() -> None:
    primary = fact(*Q1, 10, tag="Primary")
    secondary = fact(*Q1, 11, tag="Secondary", filed="2020-01-01")
    (item,) = select_facts([primary, secondary], [PRIMARY, SECONDARY])
    assert item.fact.tag == "Primary"
    assert [f.tag for f in item.tag_conflicts] == ["Secondary"]


def test_agreeing_secondary_tag_is_not_a_conflict() -> None:
    (item,) = select_facts(
        [fact(*Q1, 10, tag="Primary"), fact(*Q1, 10, tag="Secondary")], [PRIMARY, SECONDARY]
    )
    assert item.tag_conflicts == ()


def test_secondary_tag_is_used_for_periods_the_primary_does_not_report() -> None:
    q2 = ("2024-10-01", "2024-12-31")
    items = select_facts(
        [fact(*Q1, 10, tag="Primary"), fact(*q2, 15, tag="Secondary")], [PRIMARY, SECONDARY]
    )
    assert [(i.fact.tag, i.fact.value) for i in items] == [("Primary", 10), ("Secondary", 15)]
    assert all(i.tag_conflicts == () for i in items)


def test_distinct_periods_are_selected_independently_and_in_order() -> None:
    q2 = ("2024-10-01", "2024-12-31")
    items = select_facts([fact(*q2, 15), fact(*Q1, 10)], [TagRef(taxonomy="test", tag="TestTag")])
    assert [i.fact.value for i in items] == [10, 15]


def test_a_fact_whose_tag_is_not_a_candidate_is_rejected() -> None:
    with pytest.raises(ValueError, match="not among the candidate tags"):
        select_facts([fact(*Q1, 10, tag="Unlisted")], [PRIMARY])
