"""End-to-end build test with a fake SEC session and a structure-only synthetic payload.

No network is used. This proves orchestration: identity check, fetch into the raw store,
dataset assembly, Parquet output and registry rows. Real-data validation is separate.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ai_capital_cycle_monitor.clients.raw_store import RawStore
from ai_capital_cycle_monitor.clients.sec import (
    COMPANY_TICKERS_URL,
    SecClient,
    company_facts_url,
    submissions_url,
)
from ai_capital_cycle_monitor.pipelines.build import BuildError, build_company, verify_identity
from ai_capital_cycle_monitor.pipelines.datasets import dataset_paths, read_quarterly
from ai_capital_cycle_monitor.schemas.provenance import SourceRecord
from ai_capital_cycle_monitor.utils.registry import load_source_registry
from ai_capital_cycle_monitor.utils.settings import Settings
from synthetic import COMPANY, MAPPINGS, payload

VERIFIED = COMPANY.model_copy(update={"cik_verified": True})
TICKER_MAP = {"0": {"cik_str": 1, "ticker": "TEST", "title": "TEST CO"}}
SUBMISSIONS = {
    "cik": "0000000001",
    "name": "TEST CO",
    "tickers": ["TEST"],
    "exchanges": ["TESTX"],
    "fiscalYearEnd": "0630",
}


@dataclass
class _Response:
    status_code: int
    content: bytes


@dataclass
class _Session:
    bodies: dict[str, object]
    requested: list[str] = field(default_factory=list)

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> _Response:
        self.requested.append(url)
        return _Response(200, json.dumps(self.bodies[url]).encode())


def _client(
    tmp_path: Path, submissions: dict[str, object] | None = None
) -> tuple[SecClient, _Session]:
    session = _Session(
        {
            COMPANY_TICKERS_URL: TICKER_MAP,
            submissions_url("0000000001"): submissions or SUBMISSIONS,
            company_facts_url("0000000001"): payload(),
        }
    )
    client = SecClient(
        Settings(sec_user_agent="Unit Test unit.test@invalid.test"),
        RawStore(tmp_path / "raw" / "sec"),
        session=session,
        min_interval_seconds=0,
    )
    return client, session


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    (tmp_path / "source_registry.csv").write_text(
        ",".join(SourceRecord.model_fields) + "\n", encoding="utf-8"
    )
    return tmp_path


def _build(client: SecClient, data_dir: Path, company=VERIFIED):
    return build_company("test", client, data_dir, companies=[company], mappings={"TEST": MAPPINGS})


def test_build_writes_datasets_registry_rows_and_raw_snapshots(data_dir: Path) -> None:
    client, session = _client(data_dir)
    _build(client, data_dir)

    quarterly = read_quarterly(data_dir, "TEST")
    assert quarterly is not None
    assert quarterly["base_fcf"].tolist() == [30, 35, 40, 45]
    assert dataset_paths(data_dir, "TEST").long.is_file()
    assert dataset_paths(data_dir, "TEST").checks.is_file()

    registry = {r.series_id for r in load_source_registry(data_dir / "source_registry.csv")}
    assert "sec_xbrl.test.base_fcf.quarterly" in registry
    assert registry == {
        f"sec_xbrl.test.{name}.quarterly"
        for name in (
            "revenue",
            "operating_cash_flow",
            "cash_capex",
            "base_fcf",
            "capital_intensity",
            "cash_reinvestment_rate",
            "fcf_margin",
        )
    }  # one synthetic year has no year-ago quarter, so no growth series

    assert session.requested == [
        COMPANY_TICKERS_URL,
        submissions_url("0000000001"),
        company_facts_url("0000000001"),
    ]
    assert (data_dir / "raw" / "sec" / "companyfacts" / "CIK0000000001").is_dir()


def test_second_build_reuses_raw_snapshots(data_dir: Path) -> None:
    client, session = _client(data_dir)
    _build(client, data_dir)
    _build(client, data_dir)
    assert len(session.requested) == 3


def test_unverified_cik_blocks_the_build_before_any_request(data_dir: Path) -> None:
    client, session = _client(data_dir)
    with pytest.raises(BuildError, match="cik_verified"):
        _build(client, data_dir, company=COMPANY)
    assert session.requested == []


def test_identifier_mismatch_blocks_the_build(data_dir: Path) -> None:
    client, _ = _client(data_dir, submissions=SUBMISSIONS | {"fiscalYearEnd": "1231"})
    with pytest.raises(BuildError, match="fiscal_year_end_month"):
        _build(client, data_dir)
    assert read_quarterly(data_dir, "TEST") is None


def test_unknown_ticker_and_missing_mapping_are_reported(data_dir: Path) -> None:
    client, _ = _client(data_dir)
    with pytest.raises(BuildError, match="not in config"):
        build_company("nope", client, data_dir, companies=[VERIFIED], mappings={})
    with pytest.raises(BuildError, match="no XBRL mapping"):
        build_company("test", client, data_dir, companies=[VERIFIED], mappings={})


def test_verify_identity_reports_without_building(data_dir: Path) -> None:
    client, _ = _client(data_dir)
    assert verify_identity(VERIFIED, client).passed
