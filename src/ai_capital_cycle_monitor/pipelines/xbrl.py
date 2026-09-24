"""Extract XBRL facts from the SEC Company Facts payload and select one per period."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from ai_capital_cycle_monitor.schemas.xbrl import TagRef

PERIODIC_FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A"})


@dataclass(frozen=True)
class XbrlFact:
    """One reported value for one period, with the filing it came from.

    `filing_fiscal_year` and `filing_fiscal_period` are the filer's labels for the *filing*. They
    are kept for provenance only, because a comparative fact inherits its filing's labels.
    """

    taxonomy: str
    tag: str
    unit: str
    start: date
    end: date
    value: int | float
    accession: str
    form: str
    filed: date
    filing_fiscal_year: int | None
    filing_fiscal_period: str | None
    frame: str | None


@dataclass(frozen=True)
class SelectedFact:
    """The fact chosen for a period, plus any evidence that the choice was contestable."""

    fact: XbrlFact
    later_revisions: tuple[XbrlFact, ...] = ()
    tag_conflicts: tuple[XbrlFact, ...] = ()


def extract_facts(
    company_facts: dict[str, Any],
    candidates: Sequence[TagRef],
    *,
    unit: str = "USD",
    forms: frozenset[str] = PERIODIC_FORMS,
) -> list[XbrlFact]:
    """Read duration facts for the candidate tags. Instant facts (no start date) are skipped."""
    taxonomies = company_facts.get("facts", {})
    extracted: list[XbrlFact] = []
    for ref in candidates:
        entries = taxonomies.get(ref.taxonomy, {}).get(ref.tag, {}).get("units", {}).get(unit, [])
        for entry in entries:
            if entry.get("form") not in forms or "start" not in entry:
                continue
            extracted.append(
                XbrlFact(
                    taxonomy=ref.taxonomy,
                    tag=ref.tag,
                    unit=unit,
                    start=date.fromisoformat(entry["start"]),
                    end=date.fromisoformat(entry["end"]),
                    value=entry["val"],
                    accession=entry["accn"],
                    form=entry["form"],
                    filed=date.fromisoformat(entry["filed"]),
                    filing_fiscal_year=entry.get("fy"),
                    filing_fiscal_period=entry.get("fp"),
                    frame=entry.get("frame"),
                )
            )
    return extracted


def select_facts(facts: Iterable[XbrlFact], candidates: Sequence[TagRef]) -> list[SelectedFact]:
    """Pick one fact per exact period: best-priority tag, then earliest filed (as first reported).

    Later-filed facts with a different value, and facts under lower-priority tags that disagree,
    are attached to the selection rather than discarded.
    """
    priority = {(ref.taxonomy, ref.tag): rank for rank, ref in enumerate(candidates)}
    by_period: dict[tuple[date, date], list[XbrlFact]] = defaultdict(list)
    for fact in facts:
        by_period[(fact.start, fact.end)].append(fact)

    selected: list[SelectedFact] = []
    for _, group in sorted(by_period.items()):
        by_rank: dict[int, list[XbrlFact]] = defaultdict(list)
        for fact in group:
            key = (fact.taxonomy, fact.tag)
            if key not in priority:
                raise ValueError(f"fact tag {key} is not among the candidate tags")
            by_rank[priority[key]].append(fact)
        for rank_facts in by_rank.values():
            rank_facts.sort(key=lambda fact: (fact.filed, fact.accession))
        primary_rank = min(by_rank)
        chosen, *rest = by_rank[primary_rank]
        later = tuple(fact for fact in rest if fact.value != chosen.value)
        conflicts = tuple(
            by_rank[rank][0]
            for rank in sorted(by_rank)
            if rank != primary_rank and by_rank[rank][0].value != chosen.value
        )
        selected.append(SelectedFact(chosen, later, conflicts))
    return selected
