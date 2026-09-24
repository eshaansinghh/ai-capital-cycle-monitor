"""Command-line interface: verify identifiers, audit XBRL tags, and build a company dataset."""

import argparse
import sys
from collections.abc import Sequence

import pandas as pd

from ai_capital_cycle_monitor.clients.raw_store import RawStore
from ai_capital_cycle_monitor.clients.sec import SecClient, SecRequestError
from ai_capital_cycle_monitor.pipelines.audit import coverage_by_fiscal_year, find_tags
from ai_capital_cycle_monitor.pipelines.build import (
    BuildError,
    build_company,
    find_company,
    find_mappings,
    verify_identity,
)
from ai_capital_cycle_monitor.pipelines.financials import DatasetError
from ai_capital_cycle_monitor.utils.paths import DATA_DIR
from ai_capital_cycle_monitor.utils.settings import SettingsError, load_settings

EXPECTED_ERRORS = (BuildError, DatasetError, SecRequestError, SettingsError)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-capital-cycle", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser(
        "verify-identity", help="compare configured identifiers to the SEC"
    )
    verify.add_argument("ticker")
    verify.add_argument("--refresh", action="store_true", help="ignore stored snapshots")

    audit = commands.add_parser("audit-tags", help="show which XBRL tags a company uses")
    audit.add_argument("ticker")
    audit.add_argument("--pattern", help="regex to search all tag names and labels instead")
    audit.add_argument("--refresh", action="store_true", help="ignore stored snapshots")

    build = commands.add_parser("build", help="build the company's quarterly dataset")
    build.add_argument("ticker")
    build.add_argument("--refresh", action="store_true", help="ignore stored snapshots")
    return parser


def _client() -> SecClient:
    return SecClient(load_settings(), RawStore(DATA_DIR / "raw" / "sec"))


def _show(frame: pd.DataFrame) -> None:
    with pd.option_context(
        "display.max_rows", None, "display.max_colwidth", 70, "display.width", 200
    ):
        print(frame.to_string(index=False))


def _verify(args: argparse.Namespace) -> int:
    report = verify_identity(find_company(args.ticker), _client(), refresh=args.refresh)
    print(f"{report.ticker}: SEC name {report.sec_name!r}")
    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        print(f"  [{mark}] {check.name}: configured {check.expected}, SEC {check.found}")
    for key, value in report.informational.items():
        print(f"  info {key}: {value}")
    return 0 if report.passed else 1


def _audit(args: argparse.Namespace) -> int:
    company = find_company(args.ticker)
    if company.cik is None:
        raise BuildError(f"{company.ticker} has no CIK configured")
    payload = _client().company_facts(company.cik, refresh=args.refresh).read_json()
    if args.pattern:
        _show(find_tags(payload, args.pattern))
        return 0
    for field, mapping in find_mappings(company).items():
        print(f"\n{field.value}: candidates {[c.tag for c in mapping.candidates]}")
        _show(coverage_by_fiscal_year(payload, mapping, company.fiscal_year_end_month))
    return 0


def _build(args: argparse.Namespace) -> int:
    dataset = build_company(args.ticker, _client(), DATA_DIR, refresh=args.refresh)
    quarterly = dataset.quarterly
    print(f"{dataset.ticker}: {len(quarterly)} fiscal quarters built")
    print(f"  span: {quarterly['fiscal_label'].iloc[0]} to {quarterly['fiscal_label'].iloc[-1]}")
    print(f"  source: {dataset.source_url}")
    print(f"  retrieved (UTC): {dataset.retrieved_at_utc:%Y-%m-%d %H:%M:%S}")
    print(
        "  checks: "
        + ", ".join(f"{n} {s}" for s, n in dataset.checks["status"].value_counts().items())
    )
    return 0


COMMANDS = {"verify-identity": _verify, "audit-tags": _audit, "build": _build}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except EXPECTED_ERRORS as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
