"""Write a verbatim subset of a stored Company Facts snapshot as a real-data test fixture.

Usage: uv run python scripts/make_fixture.py MSFT --since 2017-07-01

Keeps only the tags named in config/xbrl_mappings.yml for the ticker, only 10-K/10-Q entries,
and only entries whose period ends on or after --since. Entries are copied unchanged. A
provenance file records where the data came from so the fixture can be audited and regenerated.
"""

import argparse
import json
from datetime import date

from ai_capital_cycle_monitor.clients.raw_store import RawStore
from ai_capital_cycle_monitor.clients.sec import normalise_cik
from ai_capital_cycle_monitor.pipelines.xbrl import PERIODIC_FORMS
from ai_capital_cycle_monitor.utils.config import load_companies, load_xbrl_mappings
from ai_capital_cycle_monitor.utils.paths import DATA_DIR, PROJECT_ROOT

FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--since", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    company = next(c for c in load_companies() if c.ticker == args.ticker.upper())
    cik = normalise_cik(company.cik or "")
    snapshot = RawStore(DATA_DIR / "raw" / "sec").latest("companyfacts", f"CIK{cik}")
    if snapshot is None:
        raise SystemExit("no stored Company Facts snapshot; run the build first")
    payload = snapshot.read_json()

    subset: dict[str, dict[str, dict]] = {}
    counts: dict[str, int] = {}
    for mapping in load_xbrl_mappings()[company.ticker].values():
        for ref in mapping.candidates:
            body = payload["facts"].get(ref.taxonomy, {}).get(ref.tag)
            if body is None:
                continue
            entries = [
                entry
                for entry in body["units"].get(mapping.unit, [])
                if entry.get("form") in PERIODIC_FORMS
                and "start" in entry
                and date.fromisoformat(entry["end"]) >= args.since
            ]
            subset.setdefault(ref.taxonomy, {})[ref.tag] = {
                "label": body.get("label"),
                "units": {mapping.unit: entries},
            }
            counts[ref.tag] = len(entries)

    stem = f"{company.ticker.lower()}_companyfacts_subset"
    document = {"cik": payload["cik"], "entityName": payload["entityName"], "facts": subset}
    (FIXTURES / f"{stem}.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    provenance = {
        "source_url": snapshot.url,
        "retrieved_at_utc": snapshot.retrieved_at_utc.isoformat(),
        "source_sha256": snapshot.sha256,
        "source_size_bytes": snapshot.size_bytes,
        "filter": f"forms {sorted(PERIODIC_FORMS)}; duration facts with period end >= {args.since}",
        "entries_per_tag": counts,
        "note": "Entries are copied verbatim. Only 'description' and unmapped tags are omitted.",
    }
    (FIXTURES / f"{stem}.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
