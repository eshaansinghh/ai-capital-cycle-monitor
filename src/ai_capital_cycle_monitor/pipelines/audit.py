"""Reports on XBRL tag usage, so the tag mapping is documented from evidence rather than assumed."""

import re
from typing import Any

import pandas as pd

from ai_capital_cycle_monitor.pipelines.xbrl import PERIODIC_FORMS, extract_facts, select_facts
from ai_capital_cycle_monitor.schemas.xbrl import FieldMapping
from ai_capital_cycle_monitor.utils.fiscal import fiscal_period_for_end


def find_tags(company_facts: dict[str, Any], pattern: str, *, unit: str = "USD") -> pd.DataFrame:
    """List tags whose name or label matches `pattern`, with their duration-fact date span."""
    matcher = re.compile(pattern, re.IGNORECASE)
    rows = []
    for taxonomy, tags in company_facts.get("facts", {}).items():
        for tag, body in tags.items():
            label = body.get("label") or ""
            if not (matcher.search(tag) or matcher.search(label)):
                continue
            entries = [
                entry
                for entry in body.get("units", {}).get(unit, [])
                if entry.get("form") in PERIODIC_FORMS and "start" in entry
            ]
            if entries:
                rows.append(
                    {
                        "taxonomy": taxonomy,
                        "tag": tag,
                        "label": label,
                        "duration_facts": len(entries),
                        "first_end": min(entry["end"] for entry in entries),
                        "last_end": max(entry["end"] for entry in entries),
                    }
                )
    columns = ["taxonomy", "tag", "label", "duration_facts", "first_end", "last_end"]
    return pd.DataFrame(rows, columns=columns).sort_values(["taxonomy", "tag"], ignore_index=True)


def coverage_by_fiscal_year(
    company_facts: dict[str, Any], mapping: FieldMapping, fye_month: int
) -> pd.DataFrame:
    """Count the facts selected under each candidate tag in each fiscal year, and tag conflicts."""
    facts = extract_facts(company_facts, mapping.candidates, unit=mapping.unit)
    rows = []
    for item in select_facts(facts, mapping.candidates):
        period = fiscal_period_for_end(item.fact.end, fye_month)
        if period is None:
            continue
        rows.append(
            {
                "fiscal_year": period[0],
                "tag": item.fact.tag,
                "selected_facts": 1,
                "tag_conflicts": len(item.tag_conflicts),
                "later_revisions": len(item.later_revisions),
            }
        )
    columns = ["fiscal_year", "tag", "selected_facts", "tag_conflicts", "later_revisions"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .groupby(["fiscal_year", "tag"], as_index=False)
        .sum()
        .sort_values(["fiscal_year", "tag"], ignore_index=True)
    )
